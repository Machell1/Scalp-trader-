"""Run Stage B of the preregistered H1 universe-admission study."""
from __future__ import annotations

from dataclasses import asdict
import gc
import hashlib
import json
from pathlib import Path

import numpy as np

from build_h1_universe_tape import build_h1_universe_tape, ftmo_metas
from run_h1_ftmo_account import metas as legacy_metas
import v130_pass_policy as policy_engine
import v130_pass_policy_csharp as csharp_engine
from v130_pass_policy import (
    BootstrapSpec,
    CompactRun,
    EquityMode,
    SimulationConfig,
    run_monte_carlo,
)


HERE = Path(__file__).resolve().parent
SCREEN = HERE / "h1_universe_screen_results.json"
LEGACY_RESULT = HERE / "h1_ftmo_account_results.json"
LEGACY_PATHS = HERE / "h1_ftmo_account_paths.npz"
RESULT = HERE / "h1_universe_account_results.json"
BASE_SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225")
BOOT_SEED = 13020260711
BLOCK = 20
SCREEN_PATHS = 20_000
CONFIRM_PATHS = 100_000
CHUNK = 500


def configure_symbols(symbols: tuple[str, ...]) -> None:
    policy_engine.SYMBOLS = tuple(symbols)
    csharp_engine.SYMBOLS = tuple(symbols)


def make_policy(symbols: tuple[str, ...]):
    configure_symbols(symbols)
    return policy_engine.RiskPolicy("C0_030", 0.0030, 0.0030)


def exact_path0(tape, metas, policy, boot: BootstrapSpec) -> dict:
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
    same = reference.rows.tobytes() == actual.rows.tobytes()
    if not same:
        raise RuntimeError("Python/C# path-0 mismatch")
    return {"exact": True, "row": actual.rows.tolist()}


def legacy_regression() -> dict:
    configure_symbols(("US30.cash", "US100.cash", "JP225.cash"))
    tape, counts = build_h1_universe_tape(
        BASE_SOURCES, stress=True, cost_mode="legacy_source"
    )
    policy = policy_engine.RiskPolicy("C0", 0.0030, 0.0030)
    boot = BootstrapSpec(seed=BOOT_SEED, block_length=BLOCK)
    gate = exact_path0(tape, legacy_metas(), policy, boot)
    recorded = json.loads(LEGACY_RESULT.read_text(encoding="utf-8"))
    expected_hash = recorded["npz_sha256"]
    actual_hash = hashlib.sha256(LEGACY_PATHS.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise RuntimeError(f"legacy NPZ hash mismatch: {actual_hash} != {expected_hash}")
    with np.load(LEGACY_PATHS, allow_pickle=False) as saved:
        expected_row = saved["E2_STRESS__C0"][:1]
    actual = csharp_engine.run_csharp_monte_carlo(
        tape, legacy_metas(), (policy,), paths=1, path_start=0, bootstrap=boot
    )[policy.name]
    if expected_row.tobytes() != actual.rows.tobytes():
        raise RuntimeError("legacy stored C0 path-0 mismatch")
    summary = recorded["modes"]["E2_STRESS"]["summaries"]["C0"]
    print(
        "LEGACY_CONTROL PASS",
        counts,
        f"both={summary['both_probability']:.6f}",
        f"lower={summary['both_wilson_lower']:.6f}",
        flush=True,
    )
    return {
        "counts": counts,
        "path0": gate,
        "npz_sha256": actual_hash,
        "recorded_100k_summary": summary,
    }


def common_bootstrap(control, candidate) -> BootstrapSpec:
    left = set(control.eligible_flat_block_starts(BLOCK))
    right = set(candidate.eligible_flat_block_starts(BLOCK))
    eligible = tuple(sorted(left & right))
    if not eligible:
        raise RuntimeError("no common flat bootstrap blocks")
    return BootstrapSpec(
        seed=BOOT_SEED,
        block_length=BLOCK,
        eligible_block_starts=eligible,
    )


def run_chunks(tape, metas, policy, boot, paths: int, label: str) -> CompactRun:
    rows = []
    for start in range(0, paths, CHUNK):
        count = min(CHUNK, paths - start)
        run = csharp_engine.run_csharp_monte_carlo(
            tape,
            metas,
            (policy,),
            paths=count,
            path_start=start,
            bootstrap=boot,
        )[policy.name]
        rows.append(run.rows)
        if (start + count) % 5_000 == 0 or start + count == paths:
            print(f"MC_PROGRESS {label} {start + count}/{paths}", flush=True)
    return CompactRun(policy, np.concatenate(rows))


def gate(summary: dict, paired: dict, control: dict) -> tuple[bool, list[str]]:
    failures = []
    if summary["both_probability"] < 0.80:
        failures.append("BOTH_POINT_LT_80PCT")
    if summary["both_wilson_lower"] < 0.80:
        failures.append("BOTH_WILSON_LOWER_LT_80PCT")
    if paired["lower"] <= 0:
        failures.append("PAIRED_LOWER_NOT_POSITIVE")
    if summary["hard_probability"] > 0.01:
        failures.append("HARD_HALT_GT_1PCT")
    if summary["timeout_probability"] > control["timeout_probability"]:
        failures.append("TIMEOUT_WORSE_THAN_CONTROL")
    return not failures, failures


def compare_portfolio(current_sources, candidate_source, paths: int, step: int) -> dict:
    expanded_sources = tuple(current_sources) + (candidate_source,)
    control_tape, control_counts = build_h1_universe_tape(tuple(current_sources), stress=True)
    candidate_tape, candidate_counts = build_h1_universe_tape(expanded_sources, stress=True)
    symbols = tuple(ftmo_metas(expanded_sources))
    metas = ftmo_metas(expanded_sources)
    policy = make_policy(symbols)
    boot = common_bootstrap(control_tape, candidate_tape)
    exact_control = exact_path0(control_tape, metas, policy, boot)
    exact_candidate = exact_path0(candidate_tape, metas, policy, boot)
    ftmo_symbol = next(iter(set(candidate_counts) - set(control_counts)))
    control = run_chunks(
        control_tape, metas, policy, boot, paths, f"S{step}:{ftmo_symbol}:CONTROL"
    )
    candidate = run_chunks(
        candidate_tape, metas, policy, boot, paths, f"S{step}:{ftmo_symbol}:CANDIDATE"
    )
    control_summary = asdict(control.summary())
    candidate_summary = asdict(candidate.summary())
    paired_value = candidate.paired_delta_lower(control)
    paired = {
        "lower": paired_value[0], "n10": paired_value[1], "n01": paired_value[2],
        "estimate": paired_value[3], "p_value": paired_value[4],
    }
    passed, failures = gate(candidate_summary, paired, control_summary)
    print(
        "PORTFOLIO_RESULT",
        ftmo_symbol,
        "PASS" if passed else "FAIL",
        f"candidate={candidate_summary['both_probability']:.6f}",
        f"lower={candidate_summary['both_wilson_lower']:.6f}",
        f"control={control_summary['both_probability']:.6f}",
        f"paired_lower={paired['lower']:.6f}",
        ",".join(failures) if failures else "none",
        flush=True,
    )
    result = {
        "candidate_source": candidate_source,
        "candidate_symbol": ftmo_symbol,
        "paths": paths,
        "common_eligible_blocks": len(boot.eligible_block_starts or ()),
        "control_counts": control_counts,
        "candidate_counts": candidate_counts,
        "path0_control": exact_control,
        "path0_candidate": exact_candidate,
        "control_summary": control_summary,
        "candidate_summary": candidate_summary,
        "paired": paired,
        "pass": passed,
        "failures": failures,
    }
    del control_tape, candidate_tape, control, candidate
    gc.collect()
    return result


def main() -> None:
    screen = json.loads(SCREEN.read_text(encoding="utf-8"))
    passers = sorted(
        source for source, row in screen["symbols"].items() if row["stage_a_pass"]
    )
    output = {
        "risk_fraction": 0.003,
        "stress": "E2_STRESS",
        "seed": BOOT_SEED,
        "block_length": BLOCK,
        "legacy_regression": legacy_regression(),
        "stage_a_passers": passers,
        "steps": [],
        "admitted_sources": [],
    }
    RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    current = list(BASE_SOURCES)
    remaining = list(passers)
    step = 1
    while remaining:
        screened = []
        for source in remaining:
            row = compare_portfolio(current, source, SCREEN_PATHS, step)
            screened.append(row)
            output["steps"].append({"step": step, "stage": "screen", **row})
            RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        ranked = sorted(
            (row for row in screened if row["pass"]),
            key=lambda row: (-row["paired"]["lower"], row["candidate_symbol"]),
        )
        admitted = None
        for row in ranked:
            confirmation = compare_portfolio(current, row["candidate_source"], CONFIRM_PATHS, step)
            output["steps"].append({"step": step, "stage": "confirmation", **confirmation})
            RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if confirmation["pass"]:
                admitted = row["candidate_source"]
                break
        if admitted is None:
            break
        current.append(admitted)
        remaining.remove(admitted)
        output["admitted_sources"].append(admitted)
        output["final_sources"] = current
        RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        step += 1
    output.setdefault("final_sources", current)
    output["verdict"] = "ADMIT" if output["admitted_sources"] else "NO_ADMISSION"
    RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("FINAL", output["verdict"], output["admitted_sources"], flush=True)
    print(f"RESULT_FILE {RESULT}", flush=True)


if __name__ == "__main__":
    main()
