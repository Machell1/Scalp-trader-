"""Run the preregistered H1 XAUUSD dynamic-risk sleeve study.

Spec: docs/XAUUSD_RISK_SLEEVE_SPEC_2026-07-15.md (committed 3efe9fa before this
file). Mirrors run_h1_usdjpy_risk.py with the control redefined as the DEPLOYED
v1.31 book (US30/US100/JP225 at 0.30% + USDJPY at 0.05%) and XAUUSD as the
candidate sleeve.
"""
from __future__ import annotations

from dataclasses import asdict
import gc
import hashlib
import json
from pathlib import Path

import numpy as np

from build_h1_universe_tape import build_h1_universe_tape, ftmo_metas
from run_h1_universe_account import BASE_SOURCES, common_bootstrap, configure_symbols
import v130_pass_policy_csharp as csharp_engine
from v130_pass_policy import (
    BootstrapSpec,
    CompactRun,
    EquityMode,
    RiskPolicy,
    SimulationConfig,
    run_monte_carlo,
)


HERE = Path(__file__).resolve().parent
RESULT = HERE / "h1_xauusd_risk_results.json"
SPEC = HERE.parent / "docs" / "XAUUSD_RISK_SLEEVE_SPEC_2026-07-15.md"
CONTROL_SOURCES = BASE_SOURCES + ("USDJPY",)
SOURCES = CONTROL_SOURCES + ("XAUUSD",)
RISKS = (0.0005, 0.0010, 0.0015, 0.0020, 0.0025)
USDJPY_RISK = 0.0005
BOOT_SEED = 13020260711
BLOCK = 20
SCREEN_PATHS = 20_000
CONFIRM_PATHS = 100_000
CHUNK = 500
ABSOLUTE_GATE = 0.78887


def policy_for(symbols: tuple[str, ...], name: str, xauusd_risk: float) -> RiskPolicy:
    mapping = {}
    for symbol in symbols:
        if symbol == "USDJPY":
            mapping[symbol] = USDJPY_RISK
        elif symbol == "XAUUSD":
            mapping[symbol] = xauusd_risk
        else:
            mapping[symbol] = 0.0030
    return RiskPolicy(name, mapping, mapping)


def exact_path0(tape, metas, policies, boot: BootstrapSpec) -> dict:
    reference = run_monte_carlo(
        tape,
        metas,
        policies,
        paths=1,
        path_start=0,
        bootstrap=boot,
        config=SimulationConfig(equity_mode=EquityMode.TWO_STOP),
    )
    actual = csharp_engine.run_csharp_monte_carlo(
        tape, metas, policies, paths=1, path_start=0, bootstrap=boot
    )
    rows = {}
    for policy in policies:
        same = reference[policy.name].rows.tobytes() == actual[policy.name].rows.tobytes()
        if not same:
            raise RuntimeError(f"Python/C# path-0 mismatch: {policy.name}")
        rows[policy.name] = actual[policy.name].rows.tolist()
    return {"exact": True, "rows": rows}


def run_chunks(tape, metas, policies, boot, paths: int, label: str) -> dict[str, CompactRun]:
    rows = {policy.name: [] for policy in policies}
    for start in range(0, paths, CHUNK):
        count = min(CHUNK, paths - start)
        chunk = csharp_engine.run_csharp_monte_carlo(
            tape,
            metas,
            policies,
            paths=count,
            path_start=start,
            bootstrap=boot,
        )
        for policy in policies:
            rows[policy.name].append(chunk[policy.name].rows)
        done = start + count
        if done % 5_000 == 0 or done == paths:
            print(f"MC_PROGRESS {label} {done}/{paths}", flush=True)
    return {
        policy.name: CompactRun(policy, np.concatenate(rows[policy.name]))
        for policy in policies
    }


def paired(candidate: CompactRun, control: CompactRun) -> dict:
    lower, n10, n01, estimate, p_value = candidate.paired_delta_lower(control)
    return {
        "lower": lower,
        "n10": n10,
        "n01": n01,
        "estimate": estimate,
        "p_value": p_value,
    }


def gates(summary: dict, comparison: dict, control: dict) -> tuple[bool, list[str]]:
    failures = []
    if summary["both_probability"] < ABSOLUTE_GATE:
        failures.append("BOTH_POINT_LT_78_887PCT")
    if summary["both_wilson_lower"] < ABSOLUTE_GATE:
        failures.append("BOTH_WILSON_LOWER_LT_78_887PCT")
    if comparison["lower"] <= 0:
        failures.append("PAIRED_LOWER_NOT_POSITIVE")
    if summary["hard_probability"] > 0.01:
        failures.append("HARD_HALT_GT_1PCT")
    if summary["timeout_probability"] > control["timeout_probability"]:
        failures.append("TIMEOUT_WORSE_THAN_CONTROL")
    return not failures, failures


def evaluate(
    control: CompactRun,
    candidates: dict[str, CompactRun],
    policies: tuple[RiskPolicy, ...],
) -> list[dict]:
    control_summary = asdict(control.summary())
    cells = []
    for policy in policies:
        run = candidates[policy.name]
        summary = asdict(run.summary())
        comparison = paired(run, control)
        passed, failures = gates(summary, comparison, control_summary)
        risk = dict(policy.phase1)["XAUUSD"]
        row = {
            "policy": policy.name,
            "xauusd_risk_fraction": risk,
            "xauusd_risk_percent": 100.0 * risk,
            "summary": summary,
            "paired": comparison,
            "pass": passed,
            "failures": failures,
            "rows_sha256": run.sha256(),
        }
        cells.append(row)
        print(
            "RISK_RESULT",
            policy.name,
            "PASS" if passed else "FAIL",
            f"both={summary['both_probability']:.6f}",
            f"lower={summary['both_wilson_lower']:.6f}",
            f"hard={summary['hard_probability']:.6f}",
            f"timeout={summary['timeout_probability']:.6f}",
            f"paired_lower={comparison['lower']:.6f}",
            ",".join(failures) if failures else "none",
            flush=True,
        )
    return cells


def run_stage(
    control_tape,
    candidate_tape,
    metas,
    policies: tuple[RiskPolicy, ...],
    boot,
    paths: int,
    label: str,
) -> dict:
    # control policy spans all configured symbols (USDJPY runner convention);
    # XAUUSD has no events on the control tape, so its entry is inert there
    control_policy = policy_for(tuple(metas), "CONTROL_V131", 0.0030)
    path0_control = exact_path0(control_tape, metas, (control_policy,), boot)
    path0_candidates = exact_path0(candidate_tape, metas, policies, boot)
    control = run_chunks(
        control_tape, metas, (control_policy,), boot, paths, f"{label}:CONTROL"
    )[control_policy.name]
    candidates = run_chunks(
        candidate_tape, metas, policies, boot, paths, f"{label}:CANDIDATES"
    )
    cells = evaluate(control, candidates, policies)
    result = {
        "paths": paths,
        "path0_control": path0_control,
        "path0_candidates": path0_candidates,
        "control_summary": asdict(control.summary()),
        "control_rows_sha256": control.sha256(),
        "cells": cells,
    }
    del control, candidates
    gc.collect()
    return result


def write_result(output: dict) -> None:
    RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    control_tape, control_counts = build_h1_universe_tape(CONTROL_SOURCES, stress=True)
    candidate_tape, candidate_counts = build_h1_universe_tape(SOURCES, stress=True)
    metas = ftmo_metas(SOURCES)
    symbols = tuple(metas)
    configure_symbols(symbols)
    policies = tuple(
        policy_for(symbols, f"XAUUSD_{int(risk * 10000):03d}", risk) for risk in RISKS
    )
    boot = common_bootstrap(control_tape, candidate_tape)
    output = {
        "spec": str(SPEC.relative_to(HERE.parent)),
        "spec_sha256": hashlib.sha256(SPEC.read_bytes()).hexdigest(),
        "absolute_gate": ABSOLUTE_GATE,
        "stress": "E2_STRESS",
        "seed": BOOT_SEED,
        "block_length": BLOCK,
        "usdjpy_risk_fraction": USDJPY_RISK,
        "common_eligible_blocks": len(boot.eligible_block_starts or ()),
        "control_counts": control_counts,
        "candidate_counts": candidate_counts,
        "screen": None,
        "confirmation": None,
        "selected": None,
        "verdict": "INCOMPLETE",
    }
    write_result(output)
    output["screen"] = run_stage(
        control_tape,
        candidate_tape,
        metas,
        policies,
        boot,
        SCREEN_PATHS,
        "SCREEN",
    )
    write_result(output)
    passing = [row for row in output["screen"]["cells"] if row["pass"]]
    if not passing:
        output["verdict"] = "NO_ADMISSION"
        write_result(output)
        print("FINAL NO_ADMISSION no screen cell passed", flush=True)
        return
    selected = sorted(
        passing,
        key=lambda row: (-row["summary"]["both_probability"], row["xauusd_risk_fraction"]),
    )[0]
    output["selected"] = selected["policy"]
    selected_policy = next(policy for policy in policies if policy.name == selected["policy"])
    output["confirmation"] = run_stage(
        control_tape,
        candidate_tape,
        metas,
        (selected_policy,),
        boot,
        CONFIRM_PATHS,
        "CONFIRM",
    )
    confirmed = output["confirmation"]["cells"][0]["pass"]
    output["verdict"] = "ADMIT_XAUUSD" if confirmed else "NO_ADMISSION"
    write_result(output)
    print("FINAL", output["verdict"], output["selected"], flush=True)
    print(f"RESULT_FILE {RESULT}", flush=True)


if __name__ == "__main__":
    main()
