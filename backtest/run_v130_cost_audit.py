"""Run the preregistered v1.30 executable-price cost-ledger development audit.

Only the already-consumed ``mined`` FTMO split is reachable.  This module has
no confirmation/holdout option and never initializes MetaTrader5.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "V130_COST_LEDGER_SPEC_2026-07-12.md"
OUTPUT = HERE / "v130_cost_audit_results.json"
CONTROL = HERE / "v130_mined_edge_results.json"
PROTOCOL_SHA256 = "271a12f4ce46717f15871aaf0c54321780484442709b82d628b047a2132d97a4"
MARKER = b"**PRE-REGISTRATION ENDS "

from freeze_ftmo_v130_blind import verify_manifest
from v130_coupled import (
    F1_PER_BAR,
    F2_STRICT_ASK,
    F2_STRICT_ASK_2X,
    PARTIAL_FRACTION,
    ea_server_day,
    load_ftmo_split,
    run_coupled,
)
from v130_cost_ledger import (
    COST_MODES,
    E0_EXECUTABLE,
    E1_MEASURED,
    E2_STRESS,
    FIXED_SLIPPAGE_R,
    SWAP_MULTIPLIER,
    run_cost_coupled,
    self_test as cost_ledger_self_test,
)


CONTROL_MODES = (F1_PER_BAR, F2_STRICT_ASK, F2_STRICT_ASK_2X)
STUDY_FILES = (
    "docs/V130_COST_LEDGER_SPEC_2026-07-12.md",
    "docs/V130_RISK_POLICY_SPEC_2026-07-11.md",
    "backtest/freeze_ftmo_v130_blind.py",
    "backtest/parity_engine.py",
    "backtest/parity_regression.py",
    "backtest/test_parity_hooks.py",
    "backtest/scalper_backtest.py",
    "backtest/scalper_confluence.py",
    "backtest/experiment.py",
    "backtest/walkforward_dsr.py",
    "backtest/v130_coupled.py",
    "backtest/v130_cost_ledger.py",
    "backtest/run_v130_cost_audit.py",
    "backtest/verify_data.py",
    "backtest/v130_mined_edge_results.json",
    "backtest/ftmo_v130_blind_20260711.manifest.sha256",
    "backtest/data/MANIFEST.sha256",
    "mql5/MomentumPullbackEA.mq5",
)


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def protocol_prefix_hash(body: bytes) -> str:
    start = body.find(MARKER)
    if start < 0:
        raise RuntimeError("cost-ledger protocol marker not found")
    end = body.find(b"\n", start)
    if end < 0:
        raise RuntimeError("cost-ledger protocol marker has no LF terminator")
    prefix = body[: end + 1]
    if b"\r\n" in prefix:
        raise RuntimeError("cost-ledger protocol prefix is not canonical UTF-8/LF")
    return hashlib.sha256(prefix).hexdigest()


def verify_protocol() -> None:
    relative = SPEC.relative_to(ROOT).as_posix()
    if subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", relative], cwd=ROOT
    ).returncode:
        raise RuntimeError("working cost-ledger protocol differs from committed HEAD")
    try:
        body = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("cost-ledger protocol is not committed at HEAD") from exc
    if b"\r" in body:
        raise RuntimeError("committed cost-ledger protocol is not canonical UTF-8/LF")
    actual = protocol_prefix_hash(body)
    if actual != PROTOCOL_SHA256:
        raise RuntimeError(
            f"cost-ledger protocol hash mismatch: {actual} != {PROTOCOL_SHA256}"
        )
    text = body.decode("utf-8")
    recorded = f"**Recorded protocol SHA256:** `{PROTOCOL_SHA256}`"
    if recorded not in text:
        raise RuntimeError("recorded cost-ledger protocol hash is absent")
    print(f"verified cost-ledger protocol SHA256 {actual}", flush=True)


def require_committed_clean_runner() -> str:
    head = git_output("rev-parse", "HEAD")
    missing: list[str] = []
    for relative in STUDY_FILES:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{relative}"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode:
            missing.append(relative)
    if missing:
        raise RuntimeError(f"cost-audit files are not committed at HEAD: {missing}")
    if subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *STUDY_FILES], cwd=ROOT
    ).returncode:
        raise RuntimeError("cost-audit working files differ from committed HEAD")
    return head


def run_checked(command: list[str], required_line: str | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = completed.stdout
    if output:
        print(output, end="" if output.endswith("\n") else "\n", flush=True)
    if completed.returncode:
        raise RuntimeError(
            f"preflight command failed ({completed.returncode}): {' '.join(command)}"
        )
    if required_line is not None and required_line not in output.splitlines():
        raise RuntimeError(
            f"preflight command missing exact line {required_line!r}: {' '.join(command)}"
        )
    return output


def preflight() -> str:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite existing result: {OUTPUT}")
    commit = require_committed_clean_runner()
    verify_protocol()
    verify_manifest()
    run_checked(
        [sys.executable, str(HERE / "verify_data.py")],
        "verified 46 OK, 0 missing, 0 mismatched",
    )
    run_checked(
        [sys.executable, str(HERE / "test_parity_hooks.py")],
        "parity hook synthetic checks: 9 passed",
    )
    cost_tests = cost_ledger_self_test()
    print(
        f"v130 cost-ledger synthetic tests: {cost_tests['passed']} passed",
        flush=True,
    )
    if int(cost_tests["passed"]) != 49:
        raise RuntimeError("cost-ledger synthetic test count differs from registration")
    run_checked(
        [sys.executable, str(HERE / "parity_regression.py")],
        "Golden regression: 46 identical, 0 failed, 134626 trades compared across 46 files.",
    )
    return commit


def quarter_key(epoch: int) -> str:
    stamp = pd.Timestamp(int(epoch), unit="s", tz="UTC")
    return f"{stamp.year}Q{stamp.quarter}"


def _trade_key(trade) -> tuple[str, int, int]:
    return str(trade.sym), int(trade.sig), int(trade.side)


def _group_stats(rows: list[dict], field: str) -> dict:
    result = {}
    for key in sorted({str(row[field]) for row in rows}):
        values = np.asarray(
            [float(row["r"]) for row in rows if str(row[field]) == key], dtype=float
        )
        result[key] = {
            "n": int(len(values)),
            "expectancy": float(values.mean()),
            "win_rate": float(np.mean(values > 0.0)),
            "total_r": float(values.sum()),
        }
    return result


def tape_summary(tape, frame_end_epoch: int) -> dict:
    partial_keys = {
        (str(event["symbol"]), int(event["signal_bar"]), int(event["side"]))
        for event in tape.events
        if event["kind"] == "partial_fill"
    }
    rows = [
        {
            "symbol": str(trade.sym),
            "epoch": int(trade.ep_sig),
            "quarter": quarter_key(trade.ep_sig),
            "side": "long" if int(trade.side) > 0 else "short",
            "reason": str(trade.reason),
            "partial": "partial" if _trade_key(trade) in partial_keys else "no_partial",
            "r": float(trade.r),
        }
        for trade in tape.trades
    ]
    if not rows:
        return {
            "n": 0,
            "expectancy": None,
            "win_rate": None,
            "total_r": 0.0,
            "per_symbol": {},
            "per_quarter": {},
            "per_side": {},
            "per_reason": {},
            "per_partial_state": {},
            "last_four_complete_quarters": [],
            "last_four_expectancy": None,
            "delete_symbol_expectancy": {},
        }
    values = np.asarray([row["r"] for row in rows], dtype=float)
    per_symbol = _group_stats(rows, "symbol")
    per_quarter = _group_stats(rows, "quarter")
    frame_end = pd.Timestamp(int(frame_end_epoch), unit="s", tz="UTC")
    current_quarter = f"{frame_end.year}Q{frame_end.quarter}"
    complete = [quarter for quarter in sorted(per_quarter) if quarter < current_quarter]
    last_four = complete[-4:]
    last_values = np.asarray(
        [row["r"] for row in rows if row["quarter"] in set(last_four)], dtype=float
    )
    delete_symbol = {}
    for symbol in sorted(per_symbol):
        kept = np.asarray(
            [row["r"] for row in rows if row["symbol"] != symbol], dtype=float
        )
        delete_symbol[symbol] = float(kept.mean()) if len(kept) else None
    return {
        "n": int(len(values)),
        "expectancy": float(values.mean()),
        "win_rate": float(np.mean(values > 0.0)),
        "total_r": float(values.sum()),
        "per_symbol": per_symbol,
        "per_quarter": per_quarter,
        "per_side": _group_stats(rows, "side"),
        "per_reason": _group_stats(rows, "reason"),
        "per_partial_state": _group_stats(rows, "partial"),
        "last_four_complete_quarters": last_four,
        "last_four_expectancy": float(last_values.mean()) if len(last_values) else None,
        "delete_symbol_expectancy": delete_symbol,
    }


def legacy_summary_view(summary: dict) -> dict:
    """Project the expanded summary onto the exact committed control schema."""
    fields = (
        "n",
        "expectancy",
        "win_rate",
        "per_symbol",
        "per_quarter",
        "last_four_complete_quarters",
        "last_four_expectancy",
        "delete_symbol_expectancy",
    )
    projected = {field: summary[field] for field in fields}
    for groups in (projected["per_symbol"], projected["per_quarter"]):
        for value in groups.values():
            value.pop("total_r", None)
    return projected


def cross_ea_midnight_count(tape) -> int:
    entries = {}
    count = 0
    for event in tape.events:
        key = event["trade_key"]
        if event["kind"] == "entry_fill":
            entries[key] = ea_server_day(int(event["epoch"]))
        elif event["kind"] == "final_exit":
            if key not in entries:
                raise AssertionError(f"{key}: final without entry")
            count += int(entries.pop(key) != ea_server_day(int(event["epoch"])))
    if entries:
        raise AssertionError(f"orphan entries: {sorted(entries)}")
    return count


def control_payload(tape, rerun, frame_end: int) -> dict:
    return {
        "census": asdict(tape.census),
        "cross_ea_server_midnight_trades": cross_ea_midnight_count(tape),
        "deterministic_rerun_sha256": rerun.normalized_sha256,
        "event_count": len(tape.events),
        "event_sha256": tape.normalized_sha256,
        "summary": legacy_summary_view(tape_summary(tape, frame_end)),
    }


def assert_exact(label: str, actual, expected) -> None:
    left = json.dumps(_json_ready(actual), sort_keys=True, separators=(",", ":"))
    right = json.dumps(_json_ready(expected), sort_keys=True, separators=(",", ":"))
    if left != right:
        raise AssertionError(f"{label}: exact committed control mismatch")


def diagnostic_rows(tape) -> list[dict]:
    rows = []
    for value in tape.diagnostics:
        if is_dataclass(value):
            value = asdict(value)
        rows.append(_json_ready(dict(value)))
    return rows


def _diag_key(row: dict) -> tuple:
    if "trade_key" in row:
        return (str(row["trade_key"]),)
    return (
        str(row.get("symbol")),
        int(row.get("signal_bar", -1)),
        int(row.get("side", 0)),
    )


def summarize_diagnostics(rows: list[dict]) -> dict:
    numeric = (
        "legacy_debit_removed_r",
        "short_time_correction_r",
        "slippage_r",
        "swap_r",
        "loss_classification_r",
    )
    totals = {
        field: float(sum(float(row.get(field, 0.0)) for row in rows)) for field in numeric
    }
    swaps = [row for row in rows if row.get("swap_events")]
    grouped_rollovers: dict[str, dict] = {}
    for row in rows:
        side = "long" if int(row.get("side", 0)) > 0 else "short"
        symbol = str(row.get("symbol"))
        for event in row.get("swap_events", []):
            cadence = "triple" if int(event["triple_multiplier"]) == 3 else "ordinary"
            key = f"{symbol}|{side}|{cadence}"
            group = grouped_rollovers.setdefault(
                key,
                {
                    "symbol": symbol,
                    "side": side,
                    "cadence": cadence,
                    "events": 0,
                    "open_fraction_sum": 0.0,
                    "open_fraction_min": None,
                    "open_fraction_max": None,
                    "conservative_base_r": 0.0,
                    "applied_r": 0.0,
                    "positive_credits_suppressed": 0,
                },
            )
            fraction = float(event["open_fraction"])
            group["events"] += 1
            group["open_fraction_sum"] += fraction
            group["open_fraction_min"] = (
                fraction if group["open_fraction_min"] is None
                else min(float(group["open_fraction_min"]), fraction)
            )
            group["open_fraction_max"] = (
                fraction if group["open_fraction_max"] is None
                else max(float(group["open_fraction_max"]), fraction)
            )
            group["conservative_base_r"] += float(event["conservative_base_r"])
            group["applied_r"] += float(event["applied_r"])
            group["positive_credits_suppressed"] += int(
                bool(event["positive_credit_suppressed"])
            )
    return {
        "n": len(rows),
        "totals": totals,
        "rollover_trades": len(swaps),
        "rollover_events": int(
            sum(len(row.get("swap_events", [])) for row in rows)
        ),
        "rollover_by_symbol_side_cadence": grouped_rollovers,
        "rows": rows,
    }


def compare_modes(left_tape, right_tape, left_diag: list[dict], right_diag: list[dict]) -> dict:
    left_trades = {_trade_key(trade): trade for trade in left_tape.trades}
    right_trades = {_trade_key(trade): trade for trade in right_tape.trades}
    shared = sorted(set(left_trades) & set(right_trades))
    sign_flips = []
    for key in shared:
        left_r = float(left_trades[key].r)
        right_r = float(right_trades[key].r)
        if (left_r > 0) != (right_r > 0) or (left_r < 0) != (right_r < 0):
            sign_flips.append(
                {"key": list(key), "left_r": left_r, "right_r": right_r}
            )
    left_rejects = {
        str(event["trade_key"])
        for event in left_tape.events
        if event["kind"] == "signal_rejection"
        and event["reason"] == "consecutive_loss_day_stop"
    }
    right_rejects = {
        str(event["trade_key"])
        for event in right_tape.events
        if event["kind"] == "signal_rejection"
        and event["reason"] == "consecutive_loss_day_stop"
    }
    left_diag_map = {_diag_key(row): row for row in left_diag}
    right_diag_map = {_diag_key(row): row for row in right_diag}
    return {
        "shared_trades": len(shared),
        "left_only_trades": [list(key) for key in sorted(set(left_trades) - set(right_trades))],
        "right_only_trades": [list(key) for key in sorted(set(right_trades) - set(left_trades))],
        "sign_flips": sign_flips,
        "left_only_consecutive_rejections": sorted(left_rejects - right_rejects),
        "right_only_consecutive_rejections": sorted(right_rejects - left_rejects),
        "shared_diagnostics": len(set(left_diag_map) & set(right_diag_map)),
    }


def policy_neutral_projection(e0_rows: list[dict], mode: str) -> dict:
    """Apply E1/E2 cash overlays to the frozen E0-admission cohort."""
    if mode not in (E1_MEASURED, E2_STRESS):
        raise ValueError(f"policy-neutral projection does not support {mode}")
    slip = float(FIXED_SLIPPAGE_R[mode])
    swap_multiplier = float(SWAP_MULTIPLIER[mode])
    rows = []
    for source in e0_rows:
        base_swap = float(
            sum(float(event["conservative_base_r"]) for event in source.get("swap_events", []))
        )
        projected_r = float(source["e0_price_r"]) - slip + swap_multiplier * base_swap
        rows.append(
            {
                "trade_key": str(source["trade_key"]),
                "symbol": str(source["symbol"]),
                "side": "long" if int(source["side"]) > 0 else "short",
                "reason": str(source["reason"]),
                "partial": "partial" if bool(source["partial"]) else "no_partial",
                "r": projected_r,
                "slippage_r": -slip,
                "swap_r": swap_multiplier * base_swap,
                "swap_events": source.get("swap_events", []),
                "remaining_fraction": float(source["remaining_fraction"]),
            }
        )
    values = np.asarray([row["r"] for row in rows], dtype=float)
    return {
        "mode": mode,
        "cohort": E0_EXECUTABLE,
        "n": int(len(rows)),
        "expectancy": float(values.mean()) if len(values) else None,
        "win_rate": float(np.mean(values > 0.0)) if len(values) else None,
        "total_r": float(values.sum()) if len(values) else 0.0,
        "per_symbol": _group_stats(rows, "symbol") if rows else {},
        "per_side": _group_stats(rows, "side") if rows else {},
        "per_reason": _group_stats(rows, "reason") if rows else {},
        "per_partial_state": _group_stats(rows, "partial") if rows else {},
        "rows": rows,
    }


def assert_projection_on_shared(
    label: str, projection: dict, independently_scheduled_rows: list[dict]
) -> dict:
    projected = {str(row["trade_key"]): row for row in projection["rows"]}
    independent = {str(row["trade_key"]): row for row in independently_scheduled_rows}
    shared = sorted(set(projected) & set(independent))
    mismatches = []
    event_checks = 0
    max_event_r_delta = 0.0
    for key in shared:
        delta = abs(float(projected[key]["r"]) - float(independent[key]["total_r"]))
        source_events = projected[key].get("swap_events", [])
        actual_events = independent[key].get("swap_events", [])
        event_error = None
        if len(source_events) != len(actual_events):
            event_error = "swap event count"
        else:
            for source, actual in zip(source_events, actual_events):
                event_checks += 1
                invariant_fields = (
                    "rollover_epoch",
                    "rollover_local",
                    "preceding_local_date",
                    "triple_multiplier",
                    "open_fraction",
                    "swap_points",
                    "raw_cash_per_lot",
                    "full_stop_risk_cash_per_lot",
                    "raw_full_position_r",
                    "conservative_base_r",
                    "positive_credit_suppressed",
                )
                if any(source[field] != actual[field] for field in invariant_fields):
                    event_error = "swap event geometry"
                    break
                expected_applied = (
                    float(source["conservative_base_r"])
                    * float(SWAP_MULTIPLIER[projection["mode"]])
                )
                event_delta = abs(expected_applied - float(actual["applied_r"]))
                max_event_r_delta = max(max_event_r_delta, event_delta)
                if event_delta > 1e-12:
                    event_error = "swap event applied R"
                    break
        slip = float(FIXED_SLIPPAGE_R[projection["mode"]])
        partial_fraction = PARTIAL_FRACTION if projected[key]["partial"] == "partial" else 0.0
        remaining = float(projected[key]["remaining_fraction"])
        slip_error = (
            abs(float(independent[key]["partial_slippage_debit_r"]) + slip * partial_fraction)
            > 1e-12
            or abs(float(independent[key]["final_slippage_debit_r"]) + slip * remaining)
            > 1e-12
        )
        if delta > 1e-12 or event_error is not None or slip_error:
            mismatches.append(
                {
                    "trade_key": key,
                    "abs_r_delta": delta,
                    "event_error": event_error,
                    "slippage_decomposition_error": slip_error,
                }
            )
    if mismatches:
        raise AssertionError(f"{label}: policy-neutral cash projection mismatch")
    return {
        "shared": len(shared),
        "projected_only": sorted(set(projected) - set(independent)),
        "independently_scheduled_only": sorted(set(independent) - set(projected)),
        "max_abs_r_delta": 0.0,
        "swap_events_checked": event_checks,
        "max_swap_event_abs_r_delta": max_event_r_delta,
    }


def compare_control_f2_geometry(control_tape, e0_tape, e0_rows: list[dict]) -> dict:
    """Prove inherited F2 geometry until an attributable loss-gate divergence."""
    control = {_trade_key(trade): trade for trade in control_tape.trades}
    executable = {_trade_key(trade): trade for trade in e0_tape.trades}
    diagnostics = {
        (str(row["symbol"]), int(row["signal_bar"]), int(row["side"])): row
        for row in e0_rows
    }
    shared = sorted(set(control) & set(executable))
    def lifecycles(tape):
        result: dict[str, dict] = {}
        for event in tape.events:
            if event["kind"] not in {"entry_fill", "partial_fill", "bar_mark", "final_exit"}:
                continue
            row = result.setdefault(
                str(event["trade_key"]),
                {"entry": None, "partials": [], "marks": [], "final": None},
            )
            kind = event["kind"]
            if kind == "entry_fill":
                row["entry"] = event
            elif kind == "partial_fill":
                row["partials"].append(event)
            elif kind == "bar_mark":
                row["marks"].append(event)
            else:
                row["final"] = event
        return result

    def verdicts(tape):
        result = {}
        for event in tape.events:
            if event["kind"] == "pending_placement":
                verdict = "placed"
            elif event["kind"] == "signal_rejection":
                verdict = f"reject:{event['reason']}"
            else:
                continue
            key = str(event["trade_key"])
            value = {"epoch": int(event["epoch"]), "verdict": verdict}
            if key in result and result[key] != value:
                raise AssertionError(f"conflicting signal verdicts for {key}")
            result[key] = value
        return result

    control_lifecycle = lifecycles(control_tape)
    e0_lifecycle = lifecycles(e0_tape)
    mismatches = []
    max_base_r_delta = 0.0
    short_time_price_exceptions = 0
    for key in shared:
        left = control[key]
        right = executable[key]
        geometry_equal = (
            int(left.entry_bar) == int(right.entry_bar)
            and int(left.exit_bar) == int(right.exit_bar)
            and int(left.side) == int(right.side)
            and str(left.reason) == str(right.reason)
        )
        row = diagnostics[key]
        trade_key = str(row["trade_key"])
        left_life = control_lifecycle[trade_key]
        right_life = e0_lifecycle[trade_key]
        if left_life["entry"] is None or right_life["entry"] is None:
            raise AssertionError(f"{trade_key}: missing entry event")
        if left_life["final"] is None or right_life["final"] is None:
            raise AssertionError(f"{trade_key}: missing final event")
        entry_equal = all(
            left_life["entry"][field] == right_life["entry"][field]
            for field in ("signal_bar", "entry_bar", "side", "price")
        )
        partials_equal = [
            (event["bar"], event["price"], event["r_component"])
            for event in left_life["partials"]
        ] == [
            (event["bar"], event["price"], event["r_component"])
            for event in right_life["partials"]
        ]
        marks_equal = [
            (event["bar"], event["price"], event["reason"])
            for event in left_life["marks"]
        ] == [
            (event["bar"], event["price"], event["reason"])
            for event in right_life["marks"]
        ]
        left_final = left_life["final"]
        right_final = right_life["final"]
        final_shape_equal = all(
            left_final[field] == right_final[field]
            for field in ("bar", "entry_bar", "exit_bar", "side", "reason")
        )
        short_time = int(left.side) < 0 and str(left.reason) == "TIME"
        final_price_equal = left_final["price"] == right_final["price"]
        if short_time and not final_price_equal:
            short_time_price_exceptions += 1
            final_price_equal = True
        r_delta = abs(float(left.r) - float(row["base_f2_total_r"]))
        max_base_r_delta = max(max_base_r_delta, r_delta)
        if not (
            geometry_equal
            and entry_equal
            and partials_equal
            and marks_equal
            and final_shape_equal
            and final_price_equal
        ) or r_delta > 1e-12:
            mismatches.append(
                {
                    "key": list(key),
                    "geometry_equal": geometry_equal,
                    "entry_equal": entry_equal,
                    "partials_equal": partials_equal,
                    "marks_equal": marks_equal,
                    "final_shape_equal": final_shape_equal,
                    "final_price_equal_or_registered_short_time": final_price_equal,
                    "base_f2_abs_r_delta": r_delta,
                }
            )
    if mismatches:
        raise AssertionError("C0_F2/E0 inherited raw geometry mismatch")
    control_verdicts = verdicts(control_tape)
    e0_verdicts = verdicts(e0_tape)
    verdict_differences = []
    for trade_key in set(control_verdicts) | set(e0_verdicts):
        left = control_verdicts.get(trade_key)
        right = e0_verdicts.get(trade_key)
        if left != right:
            epoch_candidates = [
                item["epoch"] for item in (left, right) if item is not None
            ]
            verdict_differences.append(
                {
                    "trade_key": trade_key,
                    "epoch": min(epoch_candidates),
                    "control": None if left is None else left["verdict"],
                    "e0": None if right is None else right["verdict"],
                }
            )
    verdict_differences.sort(key=lambda row: (row["epoch"], row["trade_key"]))
    control_only = sorted(set(control) - set(executable))
    e0_only = sorted(set(executable) - set(control))
    first_divergence = verdict_differences[0] if verdict_differences else None
    if verdict_differences and (
        first_divergence is None
        or "reject:consecutive_loss_day_stop"
        not in {first_divergence["control"], first_divergence["e0"]}
    ):
        raise AssertionError(
            "C0_F2/E0 admission divergence is not first-attributed to the loss-day gate"
        )
    return {
        "shared_trades": len(shared),
        "control_only_trades": [list(key) for key in control_only],
        "e0_only_trades": [list(key) for key in e0_only],
        "max_base_f2_abs_r_delta": max_base_r_delta,
        "short_time_exit_price_exceptions": short_time_price_exceptions,
        "geometry_mismatches": [],
        "first_admission_divergence": first_divergence,
        "admission_verdict_differences": verdict_differences,
    }


def edge_gate(execution: dict[str, dict]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for mode in (E1_MEASURED, E2_STRESS):
        expectancy = execution[mode]["summary"]["expectancy"]
        if expectancy is None or expectancy <= 0.0:
            failures.append(f"{mode}: pooled expectancy <= 0")
    stress = execution[E2_STRESS]["summary"]
    if len(stress["last_four_complete_quarters"]) < 4:
        failures.append(f"{E2_STRESS}: fewer than four complete quarters")
    if stress["last_four_expectancy"] is None or stress["last_four_expectancy"] <= 0.0:
        failures.append(f"{E2_STRESS}: last-four expectancy <= 0")
    for symbol, stats in stress["per_symbol"].items():
        if stats["expectancy"] < 0.0:
            failures.append(f"{E2_STRESS}/{symbol}: symbol expectancy < 0")
        if stats["n"] < 250:
            failures.append(f"{E2_STRESS}/{symbol}: fewer than 250 trades")
    for symbol, expectancy in stress["delete_symbol_expectancy"].items():
        if expectancy is None or expectancy <= 0.0:
            failures.append(f"{E2_STRESS}/without-{symbol}: expectancy <= 0")
    return not failures, failures


def atomic_json(path: Path, payload: dict) -> None:
    body = json.dumps(_json_ready(payload), indent=2, sort_keys=True, allow_nan=False) + "\n"
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
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def run_development() -> dict:
    commit = preflight()
    controls_expected = json.loads(CONTROL.read_text(encoding="utf-8"))["execution"]
    inputs = load_ftmo_split("mined")
    frame_end = max(int(symbol.ep[-1]) for symbol in inputs.symbols)

    controls = {}
    controls_expanded = {}
    control_tapes = {}
    for mode in CONTROL_MODES:
        first = run_coupled(inputs, mode)
        second = run_coupled(inputs, mode)
        if first.trades != second.trades or first.normalized_sha256 != second.normalized_sha256:
            raise AssertionError(f"{mode}: control determinism mismatch")
        payload = control_payload(first, second, frame_end)
        assert_exact(mode, payload, controls_expected[mode])
        controls[mode] = payload
        controls_expanded[mode] = tape_summary(first, frame_end)
        control_tapes[mode] = first
        print(
            f"CONTROL mode={mode} n={payload['summary']['n']} "
            f"exp={payload['summary']['expectancy']:+.10f} "
            f"sha256={payload['event_sha256']}",
            flush=True,
        )

    execution = {}
    tapes = {}
    diagnostics = {}
    for mode in COST_MODES:
        first = run_cost_coupled(inputs, mode)
        second = run_cost_coupled(inputs, mode)
        if (
            first.trades != second.trades
            or first.normalized_sha256 != second.normalized_sha256
            or first.diagnostics_sha256 != second.diagnostics_sha256
        ):
            raise AssertionError(f"{mode}: deterministic rerun mismatch")
        first_diag = diagnostic_rows(first)
        second_diag = diagnostic_rows(second)
        assert_exact(f"{mode}/diagnostics", first_diag, second_diag)
        summary = tape_summary(first, frame_end)
        tapes[mode] = first
        diagnostics[mode] = first_diag
        execution[mode] = {
            "event_sha256": first.normalized_sha256,
            "deterministic_rerun_sha256": second.normalized_sha256,
            "diagnostics_sha256": first.diagnostics_sha256,
            "deterministic_diagnostics_sha256": second.diagnostics_sha256,
            "event_count": len(first.events),
            "census": asdict(first.census),
            "cross_ea_server_midnight_trades": cross_ea_midnight_count(first),
            "summary": summary,
            "diagnostics": summarize_diagnostics(first_diag),
        }
        print(
            f"EXECUTABLE mode={mode} n={summary['n']} "
            f"exp={summary['expectancy']:+.10f} win={summary['win_rate']:.10f} "
            f"sha256={first.normalized_sha256}",
            flush=True,
        )

    policy_neutral = {
        E1_MEASURED: policy_neutral_projection(diagnostics[E0_EXECUTABLE], E1_MEASURED),
        E2_STRESS: policy_neutral_projection(diagnostics[E0_EXECUTABLE], E2_STRESS),
    }
    projection_checks = {
        E1_MEASURED: assert_projection_on_shared(
            E1_MEASURED, policy_neutral[E1_MEASURED], diagnostics[E1_MEASURED]
        ),
        E2_STRESS: assert_projection_on_shared(
            E2_STRESS, policy_neutral[E2_STRESS], diagnostics[E2_STRESS]
        ),
    }
    comparisons = {
        f"{F2_STRICT_ASK}_vs_{E0_EXECUTABLE}_raw_geometry": compare_control_f2_geometry(
            control_tapes[F2_STRICT_ASK], tapes[E0_EXECUTABLE], diagnostics[E0_EXECUTABLE]
        ),
        f"{E0_EXECUTABLE}_vs_{E1_MEASURED}": compare_modes(
            tapes[E0_EXECUTABLE], tapes[E1_MEASURED],
            diagnostics[E0_EXECUTABLE], diagnostics[E1_MEASURED],
        ),
        f"{E0_EXECUTABLE}_vs_{E2_STRESS}": compare_modes(
            tapes[E0_EXECUTABLE], tapes[E2_STRESS],
            diagnostics[E0_EXECUTABLE], diagnostics[E2_STRESS],
        ),
    }
    passed, failures = edge_gate(execution)
    result = {
        "provenance": {
            "classification": "MEASURED",
            "command": "python backtest/run_v130_cost_audit.py --development",
            "commit": commit,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "frame": "mined",
            "protocol_sha256": PROTOCOL_SHA256,
            "confirmation_accessed": False,
            "holdout_accessed": False,
            "mc_paths_run": 0,
        },
        "controls": controls,
        "controls_expanded": controls_expanded,
        "execution": execution,
        "policy_neutral_e0_admission_replay": policy_neutral,
        "policy_neutral_projection_checks": projection_checks,
        "comparisons": comparisons,
        "edge_gate": {"pass": passed, "failures": failures},
        "ledger": {"start": 209, "charged_cells": [], "end": 209},
        "verdict": "ROBUST_EDGE_PASS_RISK_STUDY_AUTHORIZED" if passed else "KILLED_AT_EDGE_GATE",
    }
    atomic_json(OUTPUT, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--development",
        action="store_true",
        help="run only the frozen mined development audit; no blind unlock exists",
    )
    args = parser.parse_args()
    if not args.development:
        parser.error("only --development is supported; blind frames have no CLI unlock")
    result = run_development()
    print(f"RESULT_FILE={OUTPUT}")
    print(f"VERDICT={result['verdict']}")


if __name__ == "__main__":
    main()
