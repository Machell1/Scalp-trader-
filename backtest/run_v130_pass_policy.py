"""Run the preregistered v1.30 FTMO pass-policy development cell.

Only the mined/development frame is exposed by this runner.  Confirmation and
holdout unlocks require a later committed passing artifact and are deliberately
not represented by a command-line flag here.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "V130_FTMO_PASS_POLICY_CHUNK_SPEC_2026-07-12.md"
AUDIT = HERE / "v130_cost_audit_results.json"
RESULT = HERE / "v130_pass_policy_chunk_results.json"
NPZ = HERE / "v130_pass_policy_chunk_paths.npz"
PROTOCOL_SHA256 = "57f465900d0f0d04033f850d50802bac10d61c22276b48c8db43f40c074669b0"
PATHS = 100_000
CHUNK_SIZE = 5_000
WORKERS = 2
BLOCK_LENGTH = 20
MODES = ("E1_MEASURED", "E2_STRESS")

sys.path.insert(0, str(HERE))

from freeze_ftmo_v130_blind import verify_manifest as verify_blind_manifest
from v130_coupled import load_ftmo_split
from v130_cost_ledger import run_cost_coupled
from v130_pass_adapter import compile_cost_tape
from v130_pass_policy import (
    C0,
    C1,
    P1,
    POLICIES,
    BootstrapSpec,
    CompactRun,
    EquityMode,
    InputInvariantError,
    run_monte_carlo,
)


def _git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _protocol_hash() -> str:
    raw = subprocess.check_output(
        ["git", "show", f"HEAD:{SPEC.relative_to(ROOT).as_posix()}"], cwd=ROOT
    )
    if b"\r" in raw:
        raise RuntimeError("committed pass-policy protocol is not canonical UTF-8/LF")
    marker = b"**PRE-REGISTRATION ENDS \xe2\x80\x94 hash all UTF-8/LF bytes through this line, including its newline.**\n"
    boundary = raw.find(marker)
    if boundary < 0:
        raise RuntimeError("pass-policy protocol marker missing")
    actual = hashlib.sha256(raw[: boundary + len(marker)]).hexdigest()
    if actual != PROTOCOL_SHA256:
        raise RuntimeError(f"pass-policy protocol hash mismatch: {actual}")
    return actual


def _clean_dependency_check() -> str:
    tracked = (
        "docs/V130_FTMO_PASS_POLICY_SPEC_2026-07-12.md",
        "docs/V130_FTMO_PASS_POLICY_REPAIR_SPEC_2026-07-12.md",
        "docs/V130_FTMO_PASS_POLICY_REPAIR2_SPEC_2026-07-12.md",
        "docs/V130_FTMO_PASS_POLICY_RESTART3_SPEC_2026-07-12.md",
        "docs/V130_FTMO_PASS_POLICY_RESTART4_SPEC_2026-07-12.md",
        "docs/V130_FTMO_PASS_POLICY_CHUNK_SPEC_2026-07-12.md",
        "backtest/parity_engine.py",
        "backtest/test_parity_hooks.py",
        "backtest/v130_coupled.py",
        "backtest/v130_cost_ledger.py",
        "backtest/v130_risk_policy.py",
        "backtest/v130_pass_policy.py",
        "backtest/v130_pass_adapter.py",
        "backtest/run_v130_pass_policy.py",
        "backtest/ftmo_v130_blind_20260711.manifest.sha256",
    )
    missing = []
    for rel in tracked:
        if subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel}"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode:
            missing.append(rel)
    if missing:
        raise RuntimeError(f"study files are not committed at HEAD: {missing}")
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *tracked], cwd=ROOT).returncode:
        raise RuntimeError("pass-policy study files differ from committed HEAD")
    return _git_output("rev-parse", "HEAD")


def _run_command(command: list[str]) -> str:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    output = completed.stdout.rstrip("\n")
    if output:
        print(output, flush=True)
    return output


def _preflight() -> dict[str, Any]:
    protocol = _protocol_hash()
    print(f"verified pass-policy protocol SHA256 {protocol}", flush=True)
    blind = _run_command([sys.executable, "backtest/freeze_ftmo_v130_blind.py", "--verify"])
    canonical = _run_command([sys.executable, "backtest/verify_data.py"])
    _run_command([sys.executable, "backtest/parity_regression.py"])
    _run_command([sys.executable, "backtest/test_parity_hooks.py"])
    _run_command([sys.executable, "backtest/v130_cost_ledger.py"])
    _run_command([sys.executable, "backtest/v130_coupled.py"])
    _run_command([sys.executable, "backtest/v130_risk_policy.py", "--self-test"])
    from v130_pass_policy import self_test as policy_self_test
    from v130_pass_adapter import self_test as adapter_self_test

    policy_checks = policy_self_test()
    adapter_checks = adapter_self_test()
    print(f"v130 pass-policy synthetic checks: {len(policy_checks)} passed", flush=True)
    print(f"v130 pass-adapter synthetic checks: {adapter_checks['passed']} passed", flush=True)
    return {
        "protocol_sha256": protocol,
        "blind_verify_stdout": blind,
        "canonical_verify_stdout": canonical,
        "policy_synthetic_checks": list(policy_checks),
        "adapter_synthetic_checks": adapter_checks,
    }


def _audit_hashes() -> dict[str, dict[str, str]]:
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    return {
        mode: {
            "event_sha256": str(payload["execution"][mode]["event_sha256"]),
            "diagnostics_sha256": str(payload["execution"][mode]["diagnostics_sha256"]),
        }
        for mode in MODES
    }


def _weighted_edge(compiled) -> dict[str, Any]:
    weights = {"US30.cash": 0.2, "US100.cash": 1.0, "JP225.cash": 1.0}
    rows = [
        {
            "symbol": str(row.symbol),
            "owner_day": date.fromisoformat(str(row.owner_day)),
            "r": float(row.total_r),
        }
        for row in compiled.lifecycles
        if row.completed
    ]
    if not rows:
        raise RuntimeError("compiled policy tape has no completed trades")
    first_day = date.fromisoformat(compiled.first_day)
    last_day = date.fromisoformat(compiled.last_day)

    def qkey(day: date) -> tuple[int, int]:
        return day.year, (day.month - 1) // 3 + 1

    def qstart(q: tuple[int, int]) -> date:
        return date(q[0], (q[1] - 1) * 3 + 1, 1)

    def qend(q: tuple[int, int]) -> date:
        year, quarter = q
        if quarter == 4:
            next_start = date(year + 1, 1, 1)
        else:
            next_start = date(year, quarter * 3 + 1, 1)
        return next_start.fromordinal(next_start.toordinal() - 1)

    quarters = sorted({qkey(row["owner_day"]) for row in rows})
    complete = [q for q in quarters if qstart(q) >= first_day and qend(q) <= last_day]

    def calc(subset: list[dict[str, Any]]) -> dict[str, Any]:
        numerator = sum(weights[row["symbol"]] * row["r"] for row in subset)
        denominator = sum(weights[row["symbol"]] for row in subset)
        return {
            "n": len(subset),
            "weighted_total_r": numerator,
            "weighted_expectancy": numerator / denominator if denominator else None,
        }

    pooled = calc(rows)
    last_four_rows = [row for row in rows if qkey(row["owner_day"]) in set(complete[-4:])]
    per_symbol: dict[str, Any] = {}
    for symbol in weights:
        values = [row for row in rows if row["symbol"] == symbol]
        per_symbol[symbol] = {
            **calc(values),
            "raw_expectancy": sum(row["r"] for row in values) / len(values),
        }
    deleted = {
        symbol: calc([row for row in rows if row["symbol"] != symbol])
        for symbol in weights
    }
    leave_quarter = {
        f"{year}Q{quarter}": calc(
            [row for row in rows if qkey(row["owner_day"]) != (year, quarter)]
        )
        for year, quarter in complete
    }
    failures: list[str] = []
    for label, value in ((f"{compiled.mode} weighted pooled", pooled["weighted_expectancy"]),):
        if value is None or value <= 0.0:
            failures.append(f"{label} <= 0")
    for label, value in ((f"{compiled.mode} weighted last-four", calc(last_four_rows)["weighted_expectancy"]),):
        if value is None or value <= 0.0:
            failures.append(f"{label} <= 0")
    if len(complete) < 4:
        failures.append("fewer than four complete quarters")
    for symbol, stats in per_symbol.items():
        if stats["n"] < 250:
            failures.append(f"{symbol}: fewer than 250 trades")
        if symbol in {"JP225.cash", "US100.cash"} and stats["raw_expectancy"] <= 0.0:
            failures.append(f"{symbol}: raw expectancy <= 0")
    for symbol, stats in deleted.items():
        if stats["weighted_expectancy"] is None or stats["weighted_expectancy"] <= 0.0:
            failures.append(f"weighted without-{symbol} <= 0")
    for quarter, stats in leave_quarter.items():
        if stats["weighted_expectancy"] is None or stats["weighted_expectancy"] <= 0.0:
            failures.append(f"weighted without-{quarter} <= 0")
    us30_loss = abs(min(0.0, per_symbol["US30.cash"]["weighted_total_r"]))
    for core in ("JP225.cash", "US100.cash"):
        if us30_loss >= per_symbol[core]["weighted_total_r"]:
            failures.append(f"US30 weighted loss not smaller than {core} contribution")
    return {
        "weights": weights,
        "n": len(rows),
        "first_day": first_day.isoformat(),
        "last_day": last_day.isoformat(),
        "complete_quarters": [f"{year}Q{quarter}" for year, quarter in complete],
        "pooled": pooled,
        "last_four": calc(last_four_rows),
        "per_symbol": per_symbol,
        "delete_symbol": deleted,
        "leave_one_quarter": leave_quarter,
        "failures": failures,
        "pass": not failures,
    }


def _summary_json(run) -> dict[str, Any]:
    summary = asdict(run.summary())
    summary["outcome_sha256"] = run.sha256()
    counters = {}
    for name in run.rows.dtype.names or ():
        if name.startswith("p1_") or name.startswith("p2_"):
            if name.endswith(("entries", "completed", "min_lot_rejections", "min_lot_substitutions", "partial_executed", "partial_skipped_rounding", "skipped_daily_halt", "skipped_fill_cap", "skipped_consecutive", "sign_mismatches")):
                counters[name] = int(run.rows[name].sum())
    summary["counter_totals"] = counters
    summary["path_rows"] = int(len(run.rows))
    return summary


def _gate(results: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for mode, payload in results["mc"].items():
        candidate = payload["summaries"]["P1"]
        if candidate["both_wilson_lower"] <= 0.88:
            failures.append(f"{mode}/P1 Wilson lower <= 88%")
        if candidate["timeout_wilson_upper"] > 0.01:
            failures.append(f"{mode}/P1 timeout upper > 1%")
        if not math.isfinite(candidate["p90_total_days_success"]) or candidate["p90_total_days_success"] > 1825:
            failures.append(f"{mode}/P1 P90 completion > 1825 days")
        for control in ("C0", "C1"):
            delta = payload["paired"][control]
            if delta["lower"] <= 0.0:
                failures.append(f"{mode}/P1-{control} paired lower <= 0")
            if candidate["firm_wilson_upper"] > payload["summaries"][control]["firm_wilson_upper"]:
                failures.append(f"{mode}/P1 firm-breach upper worse than {control}")
            if candidate["hard_wilson_upper"] > payload["summaries"][control]["hard_wilson_upper"]:
                failures.append(f"{mode}/P1 hard-halt upper worse than {control}")
        div = payload["divergence"]["P1"]
        rounding_keys = tuple(
            key for key in div
            if "min_lot_rejections" in key
            or "min_lot_substitutions" in key
            or "partial_skipped_rounding" in key
        )
        if any(div[key] for key in rounding_keys):
            failures.append(f"{mode}/P1 broker rounding divergence")
    return not failures, failures


def _mc_chunk(args):
    """Top-level pickle-safe deterministic path chunk worker."""
    tape, metas, start, count = args
    runs = run_monte_carlo(
        tape, metas, POLICIES,
        paths=count,
        path_start=start,
        bootstrap=BootstrapSpec(seed=13020260711, block_length=BLOCK_LENGTH),
        config=__import__("v130_pass_policy").SimulationConfig(equity_mode=EquityMode.TWO_STOP),
    )
    return start, {name: run.rows for name, run in runs.items()}


def _chunk_file(mode: str, start: int) -> Path:
    return HERE / f"v130_pass_policy_chunk_{mode}_{start:06d}.npz"


def _chunked_monte_carlo(mode: str, tape, metas) -> dict[str, CompactRun]:
    starts = tuple(range(0, PATHS, CHUNK_SIZE))
    chunks: dict[int, dict[str, np.ndarray]] = {}
    pending = []
    for start in starts:
        path = _chunk_file(mode, start)
        count = min(CHUNK_SIZE, PATHS - start)
        if path.exists():
            with np.load(path, allow_pickle=False) as saved:
                rows = {name: saved[name] for name in ("C0", "C1", "P1")}
            expected = np.arange(start, start + count)
            if any(not np.array_equal(rows[name]["path_id"], expected) for name in rows):
                raise RuntimeError(f"invalid checkpoint path IDs: {path}")
            chunks[start] = rows
            print(f"MC_CHUNK_REUSED mode={mode} start={start} count={count}", flush=True)
        else:
            pending.append((tape, metas, start, count))
    if pending:
        with ProcessPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(_mc_chunk, item): item[2] for item in pending}
            for future in as_completed(futures):
                start, rows = future.result()
                np.savez_compressed(_chunk_file(mode, start), **rows)
                chunks[start] = rows
                print(
                    f"MC_CHUNK_DONE mode={mode} start={start} "
                    f"count={len(next(iter(rows.values())))} completed={len(chunks)}/{len(starts)}",
                    flush=True,
                )
    policy_by_name = {policy.name: policy for policy in POLICIES}
    return {
        name: CompactRun(policy_by_name[name], np.concatenate([chunks[start][name] for start in starts]))
        for name in ("C0", "C1", "P1")
    }


def run_development() -> dict[str, Any]:
    if RESULT.exists() or NPZ.exists():
        raise RuntimeError("refusing to overwrite existing pass-policy result")
    preflight = _preflight()
    commit = _clean_dependency_check()
    inputs = load_ftmo_split("mined")
    expected = _audit_hashes()
    tapes = {}
    edge = {}
    for mode in MODES:
        first = run_cost_coupled(inputs, mode)
        second = run_cost_coupled(inputs, mode)
        if first.normalized_sha256 != second.normalized_sha256 or first.diagnostics_sha256 != second.diagnostics_sha256:
            raise RuntimeError(f"{mode}: deterministic cost tape mismatch")
        if first.normalized_sha256 != expected[mode]["event_sha256"] or first.diagnostics_sha256 != expected[mode]["diagnostics_sha256"]:
            raise RuntimeError(f"{mode}: cost-audit source hash mismatch")
        compiled = compile_cost_tape(inputs, first)
        policy_tape, metas = compiled.to_policy_inputs()
        if compiled.eligible_block_starts != tuple(policy_tape.eligible_flat_block_starts(BLOCK_LENGTH)):
            raise RuntimeError(f"{mode}: adapter/policy block eligibility mismatch")
        tapes[mode] = {"compiled": compiled, "tape": policy_tape, "metas": metas}
        edge[mode] = _weighted_edge(compiled)
        print(
            f"EDGE mode={mode} n={edge[mode]['n']} "
            f"weighted_exp={edge[mode]['pooled']['weighted_expectancy']:+.10f} "
            f"last4={edge[mode]['last_four']['weighted_expectancy']:+.10f} "
            f"pass={edge[mode]['pass']}",
            flush=True,
        )
    edge_failures = [f"{mode}: {failure}" for mode, value in edge.items() for failure in value["failures"]]
    result: dict[str, Any] = {
        "provenance": {
            "classification": "MEASURED",
            "command": "python backtest/run_v130_pass_policy.py --development",
            "commit": commit,
            "protocol_sha256": PROTOCOL_SHA256,
            "frame": "mined",
            "confirmation_accessed": False,
            "holdout_accessed": False,
            "paths_run": 0,
            "registered_paths": PATHS,
            "created_utc": datetime.now(timezone.utc).isoformat(),
        },
        "preflight": preflight,
        "source": {
            mode: {
                "event_sha256": tapes[mode]["compiled"].source_event_sha256,
                "diagnostics_sha256": tapes[mode]["compiled"].source_diagnostics_sha256,
                "compiled_sha256": tapes[mode]["compiled"].compiled_sha256,
                "eligible_blocks": len(tapes[mode]["compiled"].eligible_block_starts),
                "pre_account_summary": tapes[mode]["compiled"].pre_account_summary,
            }
            for mode in MODES
        },
        "edge": edge,
        "mc": {},
        "ledger": {"start": 211, "charged_cells": ["repair_same_development_cells"], "end": 211},
    }
    if edge_failures:
        result["edge_gate"] = {"pass": False, "failures": edge_failures}
        result["verdict"] = "KILLED_AT_WEIGHTED_EDGE_GATE"
        result["mc_status"] = "NOT_RUN_DUE_TO_EDGE_GATE"
        RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        return result

    arrays: dict[str, np.ndarray] = {}
    for mode in MODES:
        print(f"MC_START mode={mode} paths={PATHS}", flush=True)
        runs = _chunked_monte_carlo(mode, tapes[mode]["tape"], tapes[mode]["metas"])
        arrays.update({f"{mode}__{name}": run.rows for name, run in runs.items()})
        mode_payload = {
            "summaries": {name: _summary_json(run) for name, run in runs.items()},
            "hashes": {name: run.sha256() for name, run in runs.items()},
            "paired": {
                control: {
                    "lower": runs["P1"].paired_delta_lower(runs[control])[0],
                    "n10": runs["P1"].paired_delta_lower(runs[control])[1],
                    "n01": runs["P1"].paired_delta_lower(runs[control])[2],
                }
                for control in ("C0", "C1")
            },
            "divergence": {
                name: {
                    field: int(run.rows[field].sum())
                    for field in ("p1_min_lot_rejections", "p2_min_lot_rejections", "p1_min_lot_substitutions", "p2_min_lot_substitutions", "p1_partial_skipped_rounding", "p2_partial_skipped_rounding")
                    if field in run.rows.dtype.names
                }
                for name, run in runs.items()
            },
        }
        result["mc"][mode] = mode_payload
        print(f"MC_DONE mode={mode}", flush=True)
    np.savez_compressed(NPZ, **arrays)
    result["npz_sha256"] = hashlib.sha256(NPZ.read_bytes()).hexdigest()
    result["edge_gate"] = {"pass": True, "failures": []}
    result["mc_gate"], result["mc_failures"] = _gate(result)
    result["verdict"] = "P1_PASS_DEVELOPMENT" if result["mc_gate"] else "KILLED_AT_MC_GATE"
    result["provenance"]["paths_run"] = PATHS
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    if not args.development:
        parser.error("only --development is supported; blind frames have no CLI unlock")
    result = run_development()
    print(f"RESULT_FILE={RESULT}")
    print(f"VERDICT={result['verdict']}")


if __name__ == "__main__":
    main()
