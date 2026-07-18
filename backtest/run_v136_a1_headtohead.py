"""Run the preregistered v1.33-C1 control versus v1.36-A1 confirmation."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import gc
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy.stats import binomtest

from build_h1_universe_tape import build_h1_universe_tape, ftmo_metas
from run_h1_universe_account import common_bootstrap, configure_symbols
import v130_pass_policy as policy_engine
import v130_pass_policy_csharp as csharp_engine
from v130_pass_policy import (
    AccountEventKind,
    BootstrapSpec,
    CompactRun,
    COUNTER_FIELDS,
    EquityMode,
    RiskPolicy,
    SimulationConfig,
    run_monte_carlo,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "V136_A1_CORRECTED_HEADTOHEAD_SPEC_2026-07-18.md"
SPEC_HASH_FILE = SPEC.with_suffix(".sha256")
RESULT = HERE / "v136_a1_headtohead_results.json"
SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
BOOT_SEED = 13020260711
BLOCK = 20
SCREEN_PATHS = 20_000
CONFIRM_PATHS = 100_000
CHUNK = 500
LEGACY_EVENTS_SHA256 = "3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f"
CONTROL_EVENTS_SHA256 = "b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187"
EXPECTED_CANDIDATE_EA_SHA256 = "397ece9d1c8b841bbe3ed763ef2a6d8ddb3cd207f9ea69244d8857f162feef82"
DATA_OK = "verified 46 OK, 0 missing, 0 mismatched"

GATES = {
    "hard_no_greater_than": 0.003700,
    "paired_lower_strictly_greater": 0.0,
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        text=True, capture_output=True,
    ).stdout.strip()


def verify_data() -> str:
    run = subprocess.run(
        [sys.executable, str(HERE / "verify_data.py")], cwd=ROOT,
        text=True, capture_output=True,
    )
    output = (run.stdout + run.stderr).strip()
    print("DATA_VERIFY", output, flush=True)
    if run.returncode != 0 or output != DATA_OK:
        raise RuntimeError(f"data verification failed verbatim: {output}")
    return output


def event_payload(tape) -> bytes:
    return json.dumps(
        [asdict(event) for event in tape.events],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def tape_record(tape, counts: dict[str, int], parameters: dict) -> dict:
    kinds = Counter(str(event.kind) for event in tape.events)
    grouped: dict[str, list] = {}
    for event in tape.events:
        grouped.setdefault(event.trade_id, []).append(event)
    same_bar_partials = 0
    partial_trades = 0
    skipped_by_source_tape = 0
    for rows in grouped.values():
        partial = next(
            (row for row in rows if row.normalized_kind() is AccountEventKind.PARTIAL),
            None,
        )
        if partial is None:
            skipped_by_source_tape += 1
            continue
        partial_trades += 1
        final = next(
            row for row in rows if row.normalized_kind() is AccountEventKind.FINAL
        )
        same_bar_partials += int(partial.epoch == final.epoch)
    return {
        "parameters": parameters,
        "n_days": tape.n_days,
        "events": len(tape.events),
        "trades": len(tape.trades),
        "accepted_trades_by_symbol": counts,
        "event_kinds": dict(sorted(kinds.items())),
        "trades_with_partial_source_event": partial_trades,
        "trades_without_partial_source_event": skipped_by_source_tape,
        "same_bar_partial_and_final": same_bar_partials,
        "events_sha256": hashlib.sha256(event_payload(tape)).hexdigest(),
    }


def legacy_regression() -> dict:
    tape, counts = build_h1_universe_tape(SOURCES, stress=True)
    actual = hashlib.sha256(event_payload(tape)).hexdigest()
    passed = actual == LEGACY_EVENTS_SHA256
    print(
        "LEGACY_DEFAULT_REGRESSION",
        "PASS" if passed else "FAIL",
        f"expected={LEGACY_EVENTS_SHA256}",
        f"actual={actual}",
        f"events={len(tape.events)}",
        f"trades={len(tape.trades)}",
        flush=True,
    )
    if not passed:
        raise RuntimeError("additive builder changed legacy default event bytes")
    return {
        "pass": passed,
        "expected_events_sha256": LEGACY_EVENTS_SHA256,
        "actual_events_sha256": actual,
        "events": len(tape.events),
        "trades": len(tape.trades),
        "counts": counts,
    }


def exact_path0(tape, metas, policy: RiskPolicy, boot: BootstrapSpec) -> dict:
    reference = run_monte_carlo(
        tape,
        metas,
        (policy,),
        paths=1,
        path_start=0,
        bootstrap=boot,
        config=SimulationConfig(equity_mode=EquityMode.TWO_STOP),
    )[policy.name]
    actual = csharp_engine.run_csharp_monte_carlo(
        tape, metas, (policy,), paths=1, path_start=0, bootstrap=boot
    )[policy.name]
    mismatches = [
        name for name in (reference.rows.dtype.names or ())
        if reference.rows[name].tobytes() != actual.rows[name].tobytes()
    ]
    if mismatches:
        raise RuntimeError(f"Python/C# path-0 mismatch fields: {mismatches}")
    row = {}
    for name in actual.rows.dtype.names or ():
        value = actual.rows[name][0].item()
        row[name] = None if isinstance(value, float) and not math.isfinite(value) else value
    return {
        "exact": True,
        "row": row,
        "row_sha256": actual.sha256(),
    }


def run_chunks(
    tape, metas, policy: RiskPolicy, boot: BootstrapSpec, paths: int, label: str,
) -> CompactRun:
    rows = []
    for start in range(0, paths, CHUNK):
        count = min(CHUNK, paths - start)
        part = csharp_engine.run_csharp_monte_carlo(
            tape,
            metas,
            (policy,),
            paths=count,
            path_start=start,
            bootstrap=boot,
        )[policy.name]
        rows.append(part.rows)
        done = start + count
        if done % 5_000 == 0 or done == paths:
            print(f"MC_PROGRESS {label} {done}/{paths}", flush=True)
    return CompactRun(policy, np.concatenate(rows))


def counter_totals(run: CompactRun) -> dict:
    output = {}
    for phase in ("p1", "p2"):
        output[phase] = {
            name: int(run.rows[f"{phase}_{name}"].sum()) for name in COUNTER_FIELDS
        }
    return output


def reason_counts(run: CompactRun) -> dict:
    output = {}
    for phase in ("p1", "p2"):
        values, counts = np.unique(run.rows[f"{phase}_reason"], return_counts=True)
        output[phase] = {
            str(int(value)): int(count) for value, count in zip(values, counts)
        }
    return output


def paired(candidate: CompactRun, control: CompactRun) -> dict:
    lower, n10, n01, p10_lower, p01_upper = candidate.paired_delta_lower(control)
    discordant = n10 + n01
    point_delta = (n10 - n01) / len(candidate.rows)
    p_value = (
        float(binomtest(n10, discordant, 0.5, alternative="greater").pvalue)
        if discordant else 1.0
    )
    return {
        "lower": lower,
        "n10_candidate_only_pass": n10,
        "n01_control_only_pass": n01,
        "point_delta": point_delta,
        "p10_clopper_pearson_lower": p10_lower,
        "p01_clopper_pearson_upper": p01_upper,
        "mcnemar_exact_one_sided_p_value": p_value,
    }


def gate_result(candidate_summary: dict, comparison: dict) -> tuple[bool, list[str]]:
    failures = []
    if candidate_summary["hard_probability"] > GATES["hard_no_greater_than"]:
        failures.append("HARD_GT_0_3700PCT")
    if comparison["lower"] <= GATES["paired_lower_strictly_greater"]:
        failures.append("PAIRED_LOWER_NOT_POSITIVE")
    return not failures, failures


def run_record(run: CompactRun) -> dict:
    return {
        "summary": asdict(run.summary()),
        "row_sha256": run.sha256(),
        "counter_totals": counter_totals(run),
        "reason_counts": reason_counts(run),
    }


def run_stage(control_tape, candidate_tape, metas, policy, boot, paths, label) -> dict:
    control = run_chunks(
        control_tape, metas, policy, boot, paths, f"{label}:V133_C1_CONTROL"
    )
    candidate = run_chunks(
        candidate_tape, metas, policy, boot, paths, f"{label}:V136_A1"
    )
    control_record = run_record(control)
    candidate_record = run_record(candidate)
    comparison = paired(candidate, control)
    passed, failures = gate_result(candidate_record["summary"], comparison)
    deltas = {
        key: candidate_record["summary"][key] - control_record["summary"][key]
        for key in (
            "phase1_probability",
            "phase2_conditional_probability",
            "both_probability",
            "both_wilson_lower",
            "hard_probability",
            "timeout_probability",
            "median_total_days_success",
            "p90_total_days_success",
        )
    }
    print(
        "STAGE_RESULT",
        label,
        "PASS" if passed else "FAIL",
        f"control_both={control_record['summary']['both_probability']:.6f}",
        f"candidate_both={candidate_record['summary']['both_probability']:.6f}",
        f"candidate_lower={candidate_record['summary']['both_wilson_lower']:.6f}",
        f"candidate_hard={candidate_record['summary']['hard_probability']:.6f}",
        f"candidate_timeout={candidate_record['summary']['timeout_probability']:.6f}",
        f"paired_delta={comparison['point_delta']:.6f}",
        f"paired_lower={comparison['lower']:.6f}",
        ",".join(failures) if failures else "none",
        flush=True,
    )
    return {
        "paths": paths,
        "control": control_record,
        "candidate": candidate_record,
        "candidate_minus_control": deltas,
        "paired": comparison,
        "pass": passed,
        "failures": failures,
    }


def write_result(output: dict) -> None:
    RESULT.write_text(
        json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    commit = git_commit()
    data_output = verify_data()
    spec_sha256 = sha256_file(SPEC)
    registered_sha256 = SPEC_HASH_FILE.read_text(encoding="utf-8").split()[0]
    if spec_sha256 != registered_sha256:
        raise RuntimeError(
            f"spec hash mismatch: {spec_sha256} != {registered_sha256}"
        )
    candidate_ea = ROOT / "mql5" / "MomentumPullbackEA_v136_A1.mq5"
    candidate_ea_sha256 = sha256_file(candidate_ea)
    if candidate_ea_sha256 != EXPECTED_CANDIDATE_EA_SHA256:
        raise RuntimeError(
            "candidate EA hash mismatch: "
            f"{candidate_ea_sha256} != {EXPECTED_CANDIDATE_EA_SHA256}"
        )
    legacy = legacy_regression()

    control_tape, control_counts = build_h1_universe_tape(
        SOURCES,
        stress=True,
        partial_fraction=0.75,
        target_atr=1.5,
        reference_same_bar_partial=True,
        momentum_atr_mult=2.0,
    )
    candidate_tape, candidate_counts = build_h1_universe_tape(
        SOURCES,
        stress=True,
        partial_fraction=0.75,
        target_atr=1.5,
        reference_same_bar_partial=True,
        momentum_atr_mult=3.0,
    )
    metas = ftmo_metas(SOURCES)
    symbols = tuple(metas)
    configure_symbols(symbols)
    risk_map = {
        symbol: (0.0005 if symbol == "USDJPY" else 0.0030)
        for symbol in symbols
    }
    policy = RiskPolicy("V136_A1_DYNAMIC_RISK", risk_map, risk_map)
    boot = common_bootstrap(control_tape, candidate_tape)
    common_blocks = len(boot.eligible_block_starts or ())
    if common_blocks <= 0:
        raise RuntimeError("common eligible block discrepancy: no eligible blocks")
    path0 = {
        "control": exact_path0(control_tape, metas, policy, boot),
        "candidate": exact_path0(candidate_tape, metas, policy, boot),
    }
    print("PATH0_PARITY PASS control=exact candidate=exact", flush=True)

    code_files = (
        HERE / "build_h1_universe_tape.py",
        HERE / "run_v136_a1_headtohead.py",
        HERE / "v130_pass_policy.py",
        HERE / "v130_pass_policy_csharp.py",
        HERE / "v130_pass_policy_kernel.cs",
        HERE / "v130_risk_policy.py",
        candidate_ea,
    )
    control_record = tape_record(
        control_tape,
        control_counts,
        {
            "momentum_atr_mult": 2.0,
            "partial_fraction": 0.75,
            "partial_at_r": 1.0,
            "target_atr": 1.5,
            "reference_same_bar_partial": True,
        },
    )
    if (
        control_record["trades"] != 1684
        or control_record["events"] != 7145
        or control_record["events_sha256"] != CONTROL_EVENTS_SHA256
    ):
        raise RuntimeError(
            "v1.33-C1 control tape regression failed: "
            f"trades={control_record['trades']} events={control_record['events']} "
            f"sha256={control_record['events_sha256']}"
        )
    candidate_record = tape_record(
        candidate_tape,
        candidate_counts,
        {
            "momentum_atr_mult": 3.0,
            "partial_fraction": 0.75,
            "partial_at_r": 1.0,
            "target_atr": 1.5,
            "reference_same_bar_partial": True,
        },
    )
    output = {
        "verdict": "INCOMPLETE",
        "tested_commit": commit,
        "spec": str(SPEC.relative_to(ROOT)),
        "spec_sha256": spec_sha256,
        "data_verification": data_output,
        "stress": "E2_STRESS",
        "seed": BOOT_SEED,
        "block_length": BLOCK,
        "chunk_size": CHUNK,
        "common_eligible_blocks": common_blocks,
        "candidate_ea_implementation": {
            "path": str(candidate_ea.relative_to(ROOT)),
            "sha256": candidate_ea_sha256,
        },
        "risk_fraction_by_symbol_both_phases": risk_map,
        "gates": GATES,
        "trial_charge": {"confirmatory_cells": 1, "discovery_cells": 0},
        "legacy_default_regression": legacy,
        "path0_python_csharp": path0,
        "tapes": {
            "control": control_record,
            "candidate": candidate_record,
        },
        "code_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in code_files
        },
        "screen": None,
        "confirmation": None,
    }
    write_result(output)
    output["screen"] = run_stage(
        control_tape,
        candidate_tape,
        metas,
        policy,
        boot,
        SCREEN_PATHS,
        "SCREEN",
    )
    write_result(output)
    if not output["screen"]["pass"]:
        output["verdict"] = "A1_SCREEN_REJECTED"
        write_result(output)
        print("FINAL A1_SCREEN_REJECTED screen gate failed", flush=True)
        print(f"RESULT_FILE {RESULT}", flush=True)
        return

    gc.collect()
    output["confirmation"] = run_stage(
        control_tape,
        candidate_tape,
        metas,
        policy,
        boot,
        CONFIRM_PATHS,
        "CONFIRMATION",
    )
    output["verdict"] = (
        "A1_CONFIRMED_BEATS_V133_C1"
        if output["confirmation"]["pass"] else "A1_CONFIRMATION_REJECTED"
    )
    write_result(output)
    print("FINAL", output["verdict"], flush=True)
    print(f"RESULT_FILE {RESULT}", flush=True)


if __name__ == "__main__":
    main()
