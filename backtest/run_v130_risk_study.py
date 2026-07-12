"""Run the preregistered v1.30 development gate without opening blind frames.

This first runner deliberately supports only the already-mined FTMO split.  A
separate, one-time unlock will be added only if unchanged R2 passes development;
there is no CLI flag here capable of opening confirmation or holdout data.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "V130_RISK_POLICY_SPEC_2026-07-11.md"
OUTPUT = HERE / "v130_mined_edge_results.json"
PROTOCOL_SHA256 = "8f2043af550df082e493a3d295f305d014c4083115b96bfbdfe61855f860e30a"
PATHS = 100_000

from freeze_ftmo_v130_blind import verify_manifest, verify_protocol_hash
from v130_coupled import (
    D0_TOUCH,
    F1_PER_BAR,
    F2_STRICT_ASK,
    F2_STRICT_ASK_2X,
    assert_mode_identity,
    ea_server_day,
    load_ftmo_split,
    run_coupled,
    to_account_tape,
)
from v130_risk_policy import (
    BootstrapSpec,
    EquityMode,
    RiskPolicy,
    SimulationConfig,
    paired_run_delta_lower,
    run_monte_carlo,
)


MODES = (F1_PER_BAR, F2_STRICT_ASK, F2_STRICT_ASK_2X)
EXECUTION_MODES = (D0_TOUCH, *MODES)
POLICIES = (
    RiskPolicy("C0", 0.0030, 0.0030),
    RiskPolicy("R1", 0.0020, 0.0020),
    RiskPolicy("R2", 0.0020, 0.0010),
    RiskPolicy("R3", 0.0025, 0.00125),
)
STUDY_FILES = (
    "docs/V130_RISK_POLICY_SPEC_2026-07-11.md",
    "backtest/parity_engine.py",
    "backtest/parity_regression.py",
    "backtest/test_parity_hooks.py",
    "backtest/v130_coupled.py",
    "backtest/v130_fidelity.py",
    "backtest/v130_risk_policy.py",
    "backtest/run_v130_risk_study.py",
    "backtest/ftmo_v130_blind_20260711.manifest.sha256",
)


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def require_committed_clean_runner() -> str:
    head = git_output("rev-parse", "HEAD")
    missing = []
    for relative in STUDY_FILES:
        try:
            subprocess.check_call(
                ["git", "cat-file", "-e", f"HEAD:{relative}"],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            missing.append(relative)
    if missing:
        raise RuntimeError(f"study files are not committed at HEAD: {missing}")
    dirty = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *STUDY_FILES], cwd=ROOT
    ).returncode
    if dirty:
        raise RuntimeError("study file working tree differs from committed HEAD")
    return head


def quarter_key(epoch: int) -> str:
    stamp = pd.Timestamp(int(epoch), unit="s", tz="UTC")
    return f"{stamp.year}Q{stamp.quarter}"


def tape_summary(tape, frame_end_epoch: int) -> dict:
    trades = list(tape.trades)
    if not trades:
        return {
            "n": 0,
            "expectancy": None,
            "win_rate": None,
            "per_symbol": {},
            "per_quarter": {},
            "last_four_complete_quarters": [],
            "last_four_expectancy": None,
            "delete_symbol_expectancy": {},
        }

    rows = [
        {
            "symbol": trade.sym,
            "epoch": int(trade.ep_sig),
            "quarter": quarter_key(trade.ep_sig),
            "r": float(trade.r),
        }
        for trade in trades
    ]
    r_all = np.asarray([row["r"] for row in rows], dtype=float)
    per_symbol = {}
    symbols = sorted({row["symbol"] for row in rows})
    for symbol in symbols:
        values = np.asarray([row["r"] for row in rows if row["symbol"] == symbol])
        per_symbol[symbol] = {
            "n": int(len(values)),
            "expectancy": float(values.mean()),
            "win_rate": float(np.mean(values > 0.0)),
        }
    quarters = sorted({row["quarter"] for row in rows})
    per_quarter = {}
    for quarter in quarters:
        values = np.asarray([row["r"] for row in rows if row["quarter"] == quarter])
        per_quarter[quarter] = {
            "n": int(len(values)),
            "expectancy": float(values.mean()),
            "win_rate": float(np.mean(values > 0.0)),
        }
    frame_end = pd.Timestamp(int(frame_end_epoch), unit="s", tz="UTC")
    current_quarter = f"{frame_end.year}Q{frame_end.quarter}"
    complete = [quarter for quarter in quarters if quarter < current_quarter]
    last_four = complete[-4:]
    last_values = np.asarray(
        [row["r"] for row in rows if row["quarter"] in set(last_four)], dtype=float
    )
    delete_symbol = {}
    for symbol in symbols:
        values = np.asarray([row["r"] for row in rows if row["symbol"] != symbol])
        delete_symbol[symbol] = float(values.mean()) if len(values) else None
    return {
        "n": int(len(r_all)),
        "expectancy": float(r_all.mean()),
        "win_rate": float(np.mean(r_all > 0.0)),
        "per_symbol": per_symbol,
        "per_quarter": per_quarter,
        "last_four_complete_quarters": last_four,
        "last_four_expectancy": float(last_values.mean()) if len(last_values) else None,
        "delete_symbol_expectancy": delete_symbol,
    }


def cross_ea_midnight_count(tape) -> int:
    entry_days = {}
    count = 0
    for event in tape.events:
        key = event["trade_key"]
        if event["kind"] == "entry_fill":
            entry_days[key] = ea_server_day(int(event["epoch"]))
        elif event["kind"] == "final_exit":
            if key not in entry_days:
                raise AssertionError(f"{key}: final without entry in midnight audit")
            count += int(entry_days.pop(key) != ea_server_day(int(event["epoch"])))
    if entry_days:
        raise AssertionError(f"orphan entries in midnight audit: {sorted(entry_days)}")
    return count


def edge_gate(execution: dict[str, dict]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for mode in MODES:
        summary = execution[mode]["summary"]
        expectancy = summary["expectancy"]
        if expectancy is None or expectancy <= 0.0:
            failures.append(f"{mode}: pooled expectancy <= 0")
        if len(summary["last_four_complete_quarters"]) < 4:
            failures.append(f"{mode}: fewer than four complete quarters")
        last_four = summary["last_four_expectancy"]
        if last_four is None or last_four <= 0.0:
            failures.append(f"{mode}: last-four-quarter expectancy <= 0")
        for symbol, stats in summary["per_symbol"].items():
            if stats["expectancy"] < 0.0:
                failures.append(f"{mode}/{symbol}: symbol expectancy < 0")
        for deleted, value in summary["delete_symbol_expectancy"].items():
            if value is None or value <= 0.0:
                failures.append(f"{mode}/without-{deleted}: pooled expectancy <= 0")
        if execution[mode]["cross_ea_server_midnight_trades"] != 0:
            failures.append(f"{mode}: cross-server-midnight streak semantics differ from EA")
    return not failures, failures


def mc_payload(runs) -> dict:
    summaries = {name: _json_ready(asdict(run.summary())) for name, run in runs.items()}
    hashes = {name: run.sha256() for name, run in runs.items()}
    paired = paired_run_delta_lower(runs["R2"], runs["C0"])
    divergence = {}
    divergence_fields = (
        "min_lot_rejections",
        "skipped_daily_halt",
        "skipped_fill_cap",
        "skipped_consecutive",
        "sign_mismatches",
    )
    for name, run in runs.items():
        totals = {field: 0 for field in divergence_fields}
        divergent_paths = 0
        for outcome in run.outcomes:
            path_total = 0
            for phase in (outcome.phase1, outcome.phase2):
                for field in divergence_fields:
                    value = int(getattr(phase.counters, field))
                    totals[field] += value
                    path_total += value
            divergent_paths += int(path_total > 0)
        divergence[name] = {**totals, "divergent_paths": divergent_paths}
    return {
        "summaries": summaries,
        "outcome_sha256": hashes,
        "paired_R2_minus_C0": {
            "lower": float(paired[0]),
            "n10_R2_only": int(paired[1]),
            "n01_C0_only": int(paired[2]),
            "p10_R2_only_lower": float(paired[3]),
            "p01_C0_only_upper": float(paired[4]),
        },
        "policy_tape_divergence": divergence,
    }


def mandatory_mc_gate(primary: dict[str, dict]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for mode in MODES:
        payload = primary[mode]
        r2 = payload["summaries"]["R2"]
        c0 = payload["summaries"]["C0"]
        if r2["both_wilson_lower"] <= 0.88:
            failures.append(f"{mode}/R2: both-phase Wilson lower <= 88%")
        if payload["paired_R2_minus_C0"]["lower"] <= 0.0:
            failures.append(f"{mode}: paired R2-C0 lower <= 0")
        if r2["timeout_probability"] > 0.01:
            failures.append(f"{mode}/R2: timeout > 1%")
        p90 = r2["p90_total_days_success"]
        if p90 is None or not math.isfinite(float(p90)) or float(p90) > 1825:
            failures.append(f"{mode}/R2: P90 completion > 1825 days")
        if r2["firm_breach_wilson_upper"] > c0["firm_breach_wilson_upper"]:
            failures.append(f"{mode}/R2: breach upper bound worse than C0")
        for policy, counts in payload["policy_tape_divergence"].items():
            if counts["divergent_paths"] != 0:
                failures.append(f"{mode}/{policy}: policy-neutral tape divergence")
    return not failures, failures


def sensitivity_divergence_failures(label: str, payloads: dict[str, dict]) -> list[str]:
    failures = []
    for mode, payload in payloads.items():
        for policy, counts in payload["policy_tape_divergence"].items():
            if counts["divergent_paths"] != 0:
                failures.append(f"{label}/{mode}/{policy}: policy-neutral tape divergence")
    return failures


def run_mc_scenario(calendar, metas, equity_mode: EquityMode, bootstrap_mode: str):
    config = SimulationConfig(equity_mode=equity_mode, cost_multiplier=1.0)
    bootstrap = BootstrapSpec(mode=bootstrap_mode, block_length=20)
    return run_monte_carlo(
        calendar,
        metas,
        POLICIES,
        paths=PATHS,
        bootstrap=bootstrap,
        config=config,
    )


def run_attribution(calendar, metas) -> dict:
    """Primary-MBB attribution, reached only after the mandatory gate passes."""
    per_symbol = {}
    symbols = sorted({trade.symbol for trade in calendar.trades})
    for symbol in symbols:
        filtered = calendar.filter_symbols([symbol])
        per_symbol[symbol] = mc_payload(
            run_mc_scenario(filtered, metas, EquityMode.TWO_STOP, "moving_block")
        )
    quarters = sorted(
        {
            (trade.owner_day.year, (trade.owner_day.month - 1) // 3 + 1)
            for trade in calendar.trades
        }
    )
    leave_one_quarter_out = {}
    for year, quarter in quarters:
        label = f"{year}Q{quarter}"
        filtered = calendar.without_owner_quarter(year, quarter)
        leave_one_quarter_out[label] = mc_payload(
            run_mc_scenario(filtered, metas, EquityMode.TWO_STOP, "moving_block")
        )
    return {
        "per_symbol": per_symbol,
        "leave_one_calendar_quarter_out": leave_one_quarter_out,
    }


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _json_ready(value):
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def run_development_edge() -> dict:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite existing result: {OUTPUT}")
    verify_protocol_hash()
    verify_manifest()
    commit = require_committed_clean_runner()
    inputs = load_ftmo_split("mined")
    frame_end = max(int(symbol.ep[-1]) for symbol in inputs.symbols)
    execution: dict[str, dict] = {}
    coupled = {}

    for mode in EXECUTION_MODES:
        first = run_coupled(inputs, mode)
        second = run_coupled(inputs, mode)
        if first.normalized_sha256 != second.normalized_sha256 or first.trades != second.trades:
            raise AssertionError(f"{mode}: deterministic rerun mismatch")
        coupled[mode] = first
        summary = tape_summary(first, frame_end)
        execution[mode] = {
            "event_sha256": first.normalized_sha256,
            "deterministic_rerun_sha256": second.normalized_sha256,
            "event_count": len(first.events),
            "census": asdict(first.census),
            "cross_ea_server_midnight_trades": cross_ea_midnight_count(first),
            "summary": summary,
        }
        exp_text = "NA" if summary["expectancy"] is None else f"{summary['expectancy']:+.10f}"
        win_text = "NA" if summary["win_rate"] is None else f"{summary['win_rate']:.10f}"
        print(
            f"EXECUTION mode={mode} n={summary['n']} exp={exp_text} "
            f"win={win_text} event_sha256={first.normalized_sha256}",
            flush=True,
        )
    assert_mode_identity(coupled[F2_STRICT_ASK], coupled[F2_STRICT_ASK_2X])
    edge_pass, edge_failures = edge_gate(execution)

    result = {
        "provenance": {
            "classification": "MEASURED",
            "command": "python backtest/run_v130_risk_study.py --development-edge",
            "commit": commit,
            "protocol_sha256": PROTOCOL_SHA256,
            "frame": "mined",
            "paths_run": 0,
            "registered_mc_paths": PATHS,
            "created_utc": datetime.now(timezone.utc).isoformat(),
        },
        "execution": execution,
        "edge_gate": {"pass": edge_pass, "failures": edge_failures},
        "mc": {},
        "ledger": {
            "start": 209,
            "charged_cells": [],
            "end": 209,
        },
    }

    result["mc"] = {
        "status": (
            "NOT_RUN_DUE_TO_EDGE_GATE"
            if not edge_pass
            else "NOT_RUN_EDGE_ONLY; 100000-PATH ENGINE REQUIRES OPTIMIZED CONTINUATION"
        )
    }
    result["verdict"] = "KILLED_AT_EDGE_GATE" if not edge_pass else "EDGE_PASS_MC_PENDING"
    atomic_json(OUTPUT, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--development-edge",
        action="store_true",
        help="run deterministic execution/edge gates without a policy MC cell",
    )
    args = parser.parse_args()
    if not args.development_edge:
        parser.error("only --development-edge is supported; blind frames have no CLI unlock")
    result = run_development_edge()
    print(f"RESULT_FILE={OUTPUT}")
    print(f"VERDICT={result['verdict']}")


if __name__ == "__main__":
    main()
