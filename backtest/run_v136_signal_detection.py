"""Run the preregistered v1.36-A1 signal-detection challenge.

This runner is intentionally narrow: A1 plus the three cells frozen in
``V136_SIGNAL_DETECTION_CHALLENGE_SPEC_2026-07-18.md``.  Placebos rebuild the
whole pending/seat lifecycle; no completed-trade post-filtering is used.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import traceback
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from build_h1_universe_tape import (
    _m15_component_lookup,
    build_h1_universe_tape,
    ftmo_metas,
)
from run_h1_universe_account import configure_symbols
from run_h1_universe_screen import load_symbol
import v130_pass_policy as policy_engine
import v130_pass_policy_csharp as csharp_engine
import v130_risk_policy as risk_engine
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
from walkforward_dsr import dsr_hurdle, psr


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "V136_SIGNAL_DETECTION_CHALLENGE_SPEC_2026-07-18.md"
SPEC_HASH_FILE = SPEC.with_suffix(".sha256")
RESULT = HERE / "v136_signal_detection_results.json"
RESULT_HASH = RESULT.with_suffix(".sha256")
CHECKPOINTS = HERE / "v136_signal_detection_checkpoints"
FAILURE_JOURNAL = HERE / "v136_signal_detection_failures.jsonl"

SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
CELL_ORDER = ("R_STRUCT", "S_ZSEAT", "R_DRIVE")
BOOT_SEED = 13020260711
PLACEBO_SEED = 20260711
BLOCK = 20
PLACEBOS = 200
SCREEN_PATHS = 20_000
CONFIRM_PATHS = 100_000
CHUNK = 500
DSR_TRIALS = 300
DATA_OK = "verified 46 OK, 0 missing, 0 mismatched"
LEGACY_SHA = "3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f"
C1_SHA = "b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187"
A1_SHA = "3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573"
P_LIMIT = 0.0166666667

# This is the complete registered execution surface.  Every path must be a
# tracked blob whose checkout bytes exactly match HEAD before data or research
# cells are touched.  Unrelated untracked deployment backups are intentionally
# outside this list and therefore do not block a research run.
EXPERIMENT_FILES = (
    SPEC,
    SPEC_HASH_FILE,
    HERE / "run_v136_signal_detection.py",
    HERE / "test_v136_signal_detection.py",
    HERE / "build_h1_universe_tape.py",
    HERE / "parity_engine.py",
    HERE / "verify_data.py",
    HERE / "h1_universe_broker_meta.json",
    HERE / "snapshot_h1_universe_meta.py",
    HERE / "run_h1_universe_screen.py",
    HERE / "run_h1_universe_account.py",
    HERE / "run_h1_timeframe_screen.py",
    HERE / "scalper_backtest.py",
    HERE / "experiment.py",
    HERE / "walkforward_dsr.py",
    HERE / "v130_pass_policy.py",
    HERE / "v130_pass_policy_csharp.py",
    HERE / "v130_pass_policy_kernel.cs",
    HERE / "v130_risk_policy.py",
    HERE / "data" / "MANIFEST.sha256",
)
ACTIVE_BUNDLE_SHA256: str | None = None
ACTIVE_SYMBOL_CACHE: dict[str, object] | None = None
ACTIVE_M15_CACHE: dict[str, dict] | None = None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        text=True, capture_output=True,
    ).stdout.strip()


def experiment_bundle() -> dict:
    """Require registered experiment bytes to be tracked and identical to HEAD."""
    records = []
    digest = hashlib.sha256()
    for path in EXPERIMENT_FILES:
        relative = path.relative_to(ROOT).as_posix()
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=ROOT, text=True, capture_output=True,
        )
        if tracked.returncode != 0:
            raise RuntimeError(f"experiment file is not tracked at HEAD: {relative}")
        head_blob = subprocess.run(
            ["git", "rev-parse", f"HEAD:{relative}"], cwd=ROOT,
            text=True, capture_output=True,
        )
        index_blob = subprocess.run(
            ["git", "rev-parse", f":{relative}"], cwd=ROOT,
            text=True, capture_output=True,
        )
        working_blob = subprocess.run(
            ["git", "hash-object", "--path", relative, str(path)], cwd=ROOT,
            text=True, capture_output=True,
        )
        if head_blob.returncode != 0 or index_blob.returncode != 0 or working_blob.returncode != 0:
            raise RuntimeError(f"cannot hash experiment file against HEAD: {relative}")
        if head_blob.stdout.strip() != index_blob.stdout.strip():
            raise RuntimeError(f"experiment file has staged bytes differing from HEAD: {relative}")
        if head_blob.stdout.strip() != working_blob.stdout.strip():
            raise RuntimeError(f"experiment file differs from HEAD: {relative}")
        head = subprocess.run(
            ["git", "show", f"HEAD:{relative}"], cwd=ROOT, capture_output=True,
        )
        if head.returncode != 0:
            raise RuntimeError(
                f"cannot read experiment file from HEAD: {relative}: "
                f"{head.stderr.decode(errors='replace').strip()}"
            )
        working = path.read_bytes()
        canonical = head.stdout
        file_sha = hashlib.sha256(canonical).hexdigest()
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(canonical).to_bytes(8, "big"))
        digest.update(canonical)
        records.append({
            "path": relative, "canonical_head_sha256": file_sha,
            "working_raw_sha256": hashlib.sha256(working).hexdigest(),
            "git_blob": head_blob.stdout.strip(), "index_blob": index_blob.stdout.strip(),
            "canonical_bytes": len(canonical),
        })
    bundle = {"sha256": digest.hexdigest(), "files": records}
    print("EXPERIMENT_BUNDLE PASS", bundle["sha256"], f"files={len(records)}", flush=True)
    return bundle


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


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return [json_safe(v) for v in sorted(value, key=repr)]
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def atomic_write_text(path: Path, value: str) -> None:
    """Replace one checkpoint atomically without exposing a partial JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def write_result(output: dict) -> None:
    atomic_write_text(
        RESULT,
        json.dumps(json_safe(output), indent=2, sort_keys=True, allow_nan=False) + "\n",
    )


def append_failure_journal(exc: BaseException) -> None:
    """Append a verbatim failure record; this journal is never rewritten."""
    record = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
        "experiment_bundle_sha256": ACTIVE_BUNDLE_SHA256,
    }
    try:
        record["commit"] = git_commit()
    except Exception as commit_exc:  # failure logging must survive Git failures
        record["commit_error"] = repr(commit_exc)
    FAILURE_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with FAILURE_JOURNAL.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(json_safe(record), sort_keys=True, allow_nan=False) + "\n")


def event_payload(tape) -> bytes:
    return json.dumps(
        [asdict(event) for event in tape.events],
        sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")


def tape_sha(tape) -> str:
    return hashlib.sha256(event_payload(tape)).hexdigest()


def preload_market_caches() -> dict:
    global ACTIVE_SYMBOL_CACHE, ACTIVE_M15_CACHE
    meta = json.loads((HERE / "h1_universe_broker_meta.json").read_text(encoding="utf-8"))
    ACTIVE_SYMBOL_CACHE = {source: load_symbol(source, meta) for source in SOURCES}
    ACTIVE_M15_CACHE = {source: _m15_component_lookup(source) for source in SOURCES}
    record = {
        "symbols": {
            source: {
                "h1_bars": len(ACTIVE_SYMBOL_CACHE[source].h1),
                "m15_unique_timestamps": len(ACTIVE_M15_CACHE[source]),
            }
            for source in SOURCES
        }
    }
    print("MARKET_CACHES PRELOADED", json.dumps(record, sort_keys=True), flush=True)
    return record


def build_registered(*, use_cache: bool = True, **overrides):
    params = {
        "stress": True,
        "partial_fraction": 0.75,
        "target_atr": 1.5,
        "reference_same_bar_partial": True,
        "momentum_atr_mult": 3.0,
        "signal_detection": "none",
        "seat_policy": "fixed",
        "return_diagnostics": True,
    }
    if use_cache:
        if ACTIVE_SYMBOL_CACHE is None or ACTIVE_M15_CACHE is None:
            raise RuntimeError("registered market caches have not been preloaded")
        params["symbol_cache"] = ACTIVE_SYMBOL_CACHE
        params["m15_cache"] = ACTIVE_M15_CACHE
    params.update(overrides)
    result = build_h1_universe_tape(SOURCES, **params)
    if len(result) != 3:
        raise RuntimeError("diagnostic builder did not return tape, counts, diagnostics")
    return result


def assert_tape(name: str, tape, trades: int, events: int, digest: str) -> dict:
    actual = tape_sha(tape)
    passed = len(tape.trades) == trades and len(tape.events) == events and actual == digest
    print(
        f"{name}_REGRESSION", "PASS" if passed else "FAIL",
        f"trades={len(tape.trades)}", f"events={len(tape.events)}", f"sha256={actual}",
        flush=True,
    )
    if not passed:
        raise RuntimeError(
            f"{name} tape regression failed: trades={len(tape.trades)} "
            f"events={len(tape.events)} sha256={actual}"
        )
    return {"pass": True, "trades": trades, "events": events, "events_sha256": actual}


def protected_regressions() -> tuple[dict, tuple]:
    legacy_tape, legacy_counts = build_h1_universe_tape(SOURCES, stress=True)
    legacy = assert_tape("LEGACY_DEFAULT", legacy_tape, 1645, 7317, LEGACY_SHA)
    legacy["counts"] = legacy_counts
    c1_tape, c1_counts = build_h1_universe_tape(
        SOURCES, stress=True, partial_fraction=0.75, target_atr=1.5,
        reference_same_bar_partial=True, momentum_atr_mult=2.0,
        signal_detection="none", seat_policy="fixed",
    )
    c1 = assert_tape("V133_C1", c1_tape, 1684, 7145, C1_SHA)
    c1["counts"] = c1_counts
    a1_uncached = build_registered(use_cache=False)
    a1_uncached_record = assert_tape("V136_A1_UNCACHED", a1_uncached[0], 662, 2819, A1_SHA)
    a1_cached = build_registered(use_cache=True)
    a1_record = assert_tape("V136_A1_CACHED", a1_cached[0], 662, 2819, A1_SHA)
    if event_payload(a1_uncached[0]) != event_payload(a1_cached[0]) or a1_uncached[1] != a1_cached[1]:
        raise RuntimeError("cached A1 is not byte-identical to uncached A1")
    a1_record["counts"] = a1_cached[1]
    a1_record["cache_vs_uncached_exact"] = True
    a1_record["uncached_events_sha256"] = a1_uncached_record["events_sha256"]
    return {"legacy_default": legacy, "v133_c1": c1, "v136_a1": a1_record}, a1_cached


def synthetic_self_tests() -> dict:
    pass_names = list(policy_engine.self_test())
    risk_names = list(risk_engine.synthetic_fidelity_tests())
    print(
        f"SYNTHETIC_SELF_TESTS PASS pass_policy={len(pass_names)} risk_policy={len(risk_names)}",
        flush=True,
    )
    return {"pass_policy": pass_names, "risk_policy": risk_names, "pass": True}


def enrich_rows(diagnostics: dict) -> list[dict]:
    rows = []
    for original in diagnostics["raw_signals"]:
        row = dict(original)
        stamp = pd.Timestamp(row["signal_time"])
        row["quarter"] = str(stamp.to_period("Q"))
        row["oos"] = int(row["bar_index"]) >= int(row["oos_start"])
        row["key"] = (row["source"], int(row["bar_index"]))
        rows.append(row)
    return rows


def raw_lookup(diagnostics: dict) -> dict[str, dict]:
    return {row["trade_id"]: row for row in enrich_rows(diagnostics)}


def realized_r_by_trade(tape) -> dict[str, float]:
    grouped: dict[str, list] = defaultdict(list)
    for event in tape.events:
        grouped[event.trade_id].append(event)
    output = {}
    for trade_id, events in grouped.items():
        events.sort(key=lambda event: (event.epoch, event.sequence))
        entry = next(
            (event for event in events if event.normalized_kind() is AccountEventKind.ENTRY),
            None,
        )
        if entry is None:
            continue
        remaining = 1.0
        value = -float(entry.fixed_slippage_r)
        for event in events:
            kind = event.normalized_kind()
            if kind not in {AccountEventKind.PARTIAL, AccountEventKind.FINAL}:
                continue
            new_remaining = float(event.remaining_fraction)
            closed = remaining - new_remaining
            if closed < -1e-12:
                raise RuntimeError(f"remaining fraction increased for {trade_id}")
            value += closed * entry.side * (event.price - entry.price) / entry.stop_distance
            remaining = new_remaining
        if abs(remaining) > 1e-9:
            raise RuntimeError(f"filled lifecycle did not close: {trade_id}")
        output[trade_id] = float(value)
    return output


def census(tape, diagnostics: dict) -> dict:
    rows = enrich_rows(diagnostics)
    accepted = set(diagnostics["accepted_trade_ids"])
    accepted_filled = set(diagnostics["filled_trade_ids"])
    local_selected = set(diagnostics["locally_selected_trade_ids"])
    local_filled = set(diagnostics["locally_filled_trade_ids"])
    fields = (
        "raw_base", "raw_a1_w2", "raw_marginal_w2",
        "marginal_feature_positive", "predicate_admitted", "local_selected",
        "portfolio_accepted", "local_fill", "accepted_fill", "cancel", "events",
    )
    groups: dict[tuple[str, int], dict] = {}
    for row in rows:
        key = (row["symbol"], int(row["side"]))
        rec = groups.setdefault(
            key, {"symbol": row["symbol"], "side": int(row["side"]), **{field: 0 for field in fields}},
        )
        rec["raw_base"] += 1
        rec["raw_a1_w2"] += int(row["quality"] == "a1" and row["w2_pass"])
        rec["raw_marginal_w2"] += int(row["quality"] == "marginal" and row["w2_pass"])
        rec["marginal_feature_positive"] += int(
            row["quality"] == "marginal" and row["w2_pass"] and bool(row["feature_decision"])
        )
        rec["predicate_admitted"] += int(bool(row["signal_admitted"]))
        rec["local_selected"] += int(row["trade_id"] in local_selected)
        if row["trade_id"] in accepted:
            rec["portfolio_accepted"] += 1
        rec["local_fill"] += int(row["trade_id"] in local_filled)
        rec["accepted_fill"] += int(row["trade_id"] in accepted_filled)
        rec["cancel"] += int(row["trade_id"] in accepted - accepted_filled)
    for event in tape.events:
        key = (event.symbol, int(event.side))
        if key not in groups:
            groups[key] = {"symbol": event.symbol, "side": int(event.side), **{field: 0 for field in fields}}
        groups[key]["events"] += 1
    totals = {field: sum(row[field] for row in groups.values()) for field in fields}
    return {
        "by_symbol_side": sorted(groups.values(), key=lambda r: (r["symbol"], r["side"])),
        "totals": totals,
        "missing_m15_constituents": int(diagnostics["missing_m15_constituents"]),
        "contention_epochs": int(diagnostics["contention_epochs"]),
        "contention_claimants": int(diagnostics["contention_claimants"]),
        "seat_rejections": diagnostics["seat_rejections"],
    }


def quarter_completeness(diagnostics: dict) -> dict:
    """Classify OOS calendar edges independently for each source/symbol."""
    if ACTIVE_SYMBOL_CACHE is None:
        raise RuntimeError("symbol cache unavailable for quarter classification")
    rows = enrich_rows(diagnostics)
    source_symbol = {row["source"]: row["symbol"] for row in rows}
    complete = []
    partial = []
    for source in SOURCES:
        h1 = ACTIVE_SYMBOL_CACHE[source].h1
        cut = int(len(h1) * 0.70)
        quarters = sorted({str(pd.Timestamp(value).to_period("Q")) for value in h1.iloc[cut:]["time"]})
        symbol = source_symbol[source]
        partial_names = {quarters[0], quarters[-1]} if len(quarters) >= 3 else set()
        for quarter in quarters:
            row = {"source": source, "symbol": symbol, "quarter": quarter}
            (partial if quarter in partial_names else complete).append(row)
    return {
        "rule": "per-symbol first/last OOS calendar quarters partial when >=3",
        "complete_symbol_quarters": complete,
        "partial_symbol_quarters": partial,
        "complete_calendar_quarters": sorted({row["quarter"] for row in complete}),
    }


def oos_distribution(tape, diagnostics: dict) -> tuple[np.ndarray, list[dict]]:
    lookup = raw_lookup(diagnostics)
    outcomes = realized_r_by_trade(tape)
    records = []
    for trade_id, value in outcomes.items():
        row = lookup.get(trade_id)
        if row is None or not row["oos"]:
            continue
        records.append({**row, "r": float(value)})
    return np.asarray([row["r"] for row in records], dtype=float), records


def discovery_summary(tape, diagnostics: dict, quarter_policy: dict) -> dict:
    values, records = oos_distribution(tape, diagnostics)
    by_symbol = {}
    for symbol in sorted({row["symbol"] for row in enrich_rows(diagnostics)}):
        subset = [row["r"] for row in records if row["symbol"] == symbol]
        by_symbol[symbol] = {
            "n": len(subset), "expectancy": float(np.mean(subset)) if subset else None,
        }
    complete_pairs = {
        (row["symbol"], row["quarter"])
        for row in quarter_policy["complete_symbol_quarters"]
    }
    partial_pairs = {
        (row["symbol"], row["quarter"])
        for row in quarter_policy["partial_symbol_quarters"]
    }
    by_quarter = {}
    for quarter in quarter_policy["complete_calendar_quarters"]:
        subset = [
            row["r"] for row in records
            if row["quarter"] == quarter and (row["symbol"], row["quarter"]) in complete_pairs
        ]
        by_quarter[quarter] = {
            "n": len(subset), "expectancy": float(np.mean(subset)) if subset else None,
        }
    partial_results = []
    for symbol, quarter in sorted(partial_pairs):
        subset = [row["r"] for row in records if row["symbol"] == symbol and row["quarter"] == quarter]
        partial_results.append({
            "symbol": symbol, "quarter": quarter, "n": len(subset),
            "expectancy": float(np.mean(subset)) if subset else None,
        })
    sr0 = dsr_hurdle(n_trials=DSR_TRIALS, n_obs=len(values))
    dsr = psr(values, sr0) if len(values) >= 3 else float("nan")
    return {
        "oos_n": len(values),
        "oos_expectancy": float(values.mean()) if len(values) else None,
        "oos_win_rate": float((values > 0).mean()) if len(values) else None,
        "oos_r": values.tolist(),
        "dsr_trials": DSR_TRIALS,
        "dsr_hurdle": float(sr0),
        "dsr": float(dsr),
        "by_symbol": by_symbol,
        "complete_quarters": by_quarter,
        "partial_symbol_quarters": partial_results,
    }


def arm_summary(tape, diagnostics: dict, *, marginal_decision: bool = True) -> dict:
    lookup = raw_lookup(diagnostics)
    outcomes = realized_r_by_trade(tape)
    values = []
    ids = []
    for trade_id, value in outcomes.items():
        row = lookup.get(trade_id)
        if row is None or not row["oos"] or row["quality"] != "marginal":
            continue
        if bool(row["feature_decision"]) is marginal_decision:
            values.append(float(value))
            ids.append(trade_id)
    return {
        "filled_oos_n": len(values),
        "filled_oos_expectancy": float(np.mean(values)) if values else None,
        "filled_trade_ids_sha256": sha256_json(sorted(ids)),
    }


def delta_breadth(candidate: dict, control: dict) -> dict:
    symbols = {}
    for symbol, base in control["by_symbol"].items():
        cand = candidate["by_symbol"].get(symbol, {"n": 0, "expectancy": None})
        delta = (
            cand["expectancy"] - base["expectancy"]
            if cand["expectancy"] is not None and base["expectancy"] is not None else None
        )
        symbols[symbol] = {"candidate": cand, "control": base, "delta": delta}
    symbol_nonnegative = sum(row["delta"] is not None and row["delta"] >= 0 for row in symbols.values())
    quarters = {}
    for quarter, base in control["complete_quarters"].items():
        cand = candidate["complete_quarters"].get(quarter, {"n": 0, "expectancy": None})
        delta = (
            cand["expectancy"] - base["expectancy"]
            if cand["expectancy"] is not None and base["expectancy"] is not None else None
        )
        quarters[quarter] = {"candidate": cand, "control": base, "delta": delta}
    q_nonnegative = sum(row["delta"] is not None and row["delta"] >= 0 for row in quarters.values())
    return {
        "symbols": symbols,
        "symbol_nonnegative": symbol_nonnegative,
        "symbol_total": len(symbols),
        "quarters": quarters,
        "quarter_nonnegative": q_nonnegative,
        "quarter_total": len(quarters),
        "quarter_nonnegative_fraction": q_nonnegative / len(quarters) if quarters else 0.0,
    }


def retention(candidate_diag: dict, control_diag: dict) -> dict:
    c_rows = raw_lookup(candidate_diag)
    base_rows = raw_lookup(control_diag)
    base_accepted = set(control_diag["accepted_trade_ids"])
    base_filled = set(control_diag["filled_trade_ids"])
    cand_accepted = set(candidate_diag["accepted_trade_ids"])
    cand_filled = set(candidate_diag["filled_trade_ids"])
    a1_ids = {trade_id for trade_id, row in c_rows.items() if row["quality"] == "a1" and row["w2_pass"]}
    admitted_kept = len(base_accepted & cand_accepted & a1_ids)
    filled_kept = len(base_filled & cand_filled & a1_ids)
    by_symbol_side = []
    groups = sorted({(row["symbol"], int(row["side"])) for row in base_rows.values()})
    for symbol, side in groups:
        group_ids = {
            trade_id for trade_id, row in base_rows.items()
            if row["symbol"] == symbol and int(row["side"]) == side
        }
        group_admitted = base_accepted & group_ids
        group_filled = base_filled & group_ids
        kept_admitted = group_admitted & cand_accepted & a1_ids
        kept_filled = group_filled & cand_filled & a1_ids
        by_symbol_side.append({
            "symbol": symbol, "side": side,
            "control_admitted": len(group_admitted),
            "retained_admitted": len(kept_admitted),
            "admitted_fraction": (
                len(kept_admitted) / len(group_admitted) if group_admitted else None
            ),
            "control_filled": len(group_filled),
            "retained_filled": len(kept_filled),
            "filled_fraction": len(kept_filled) / len(group_filled) if group_filled else None,
        })
    return {
        "control_admitted": len(base_accepted), "retained_admitted": admitted_kept,
        "admitted_fraction": admitted_kept / len(base_accepted) if base_accepted else 0.0,
        "control_filled": len(base_filled), "retained_filled": filled_kept,
        "filled_fraction": filled_kept / len(base_filled) if base_filled else 0.0,
        "by_symbol_side": by_symbol_side,
    }


def causality_fixtures(candidates: dict[str, tuple]) -> dict:
    if ACTIVE_SYMBOL_CACHE is None or ACTIVE_M15_CACHE is None:
        raise RuntimeError("market caches unavailable for causality fixtures")
    output = {}
    struct_rows = [r for r in enrich_rows(candidates["R_STRUCT"][2]) if r["quality"] == "marginal"]
    struct_checked = 0
    h1_cache = {source: ACTIVE_SYMBOL_CACHE[source].h1 for source in SOURCES}
    for row in struct_rows:
        h1 = h1_cache[row["source"]]
        i, side = int(row["bar_index"]), int(row["side"])
        close = h1["close"].to_numpy(float)
        expected = False
        if i >= 20:
            prior = close[i - 20:i]
            expected = bool(close[i] > prior.max()) if side > 0 else bool(close[i] < prior.min())
        truncated = close[:i + 1]
        check = False
        if i >= 20:
            prior = truncated[i - 20:i]
            check = bool(truncated[i] > prior.max()) if side > 0 else bool(truncated[i] < prior.min())
        if expected != check or expected != bool(row["feature_decision"]):
            raise RuntimeError(f"R_STRUCT causality mismatch {row['key']}")
        struct_checked += 1
    output["R_STRUCT"] = {"pass": True, "sampled_signal_closes": struct_checked}

    drive_checked = missing = 0
    for row in [r for r in enrich_rows(candidates["R_DRIVE"][2]) if r["quality"] == "marginal"]:
        source = row["source"]
        lookup = ACTIVE_M15_CACHE[source]
        start = pd.Timestamp(row["signal_time"])
        allowed = [start + pd.Timedelta(minutes=15 * k) for k in range(4)]
        builder_timestamps = tuple(
            pd.Timestamp(value) for value in row["feature_value"]["m15_timestamps"]
        )
        if builder_timestamps != tuple(allowed):
            raise RuntimeError(f"R_DRIVE builder timestamp mismatch {row['key']}")
        constituents = [lookup.get(timestamp) for timestamp in allowed]
        exact = all(item is not None and item[0] == 1 for item in constituents)
        if not exact:
            missing += int(bool(row["w2_pass"]))
            expected_k = None
            decision = False
        else:
            bodies = int(row["side"]) * (
                np.asarray([item[2] for item in constituents], dtype=float)
                - np.asarray([item[1] for item in constituents], dtype=float)
            )
            expected_k = int(np.argmax(bodies))
            decision = expected_k <= 1
            truncated_lookup = {key: value for key, value in lookup.items() if key <= allowed[-1]}
            check_rows = [truncated_lookup.get(timestamp) for timestamp in allowed]
            if not all(item is not None and item[0] == 1 for item in check_rows):
                raise RuntimeError(f"R_DRIVE truncated constituent mismatch {row['key']}")
            check_bodies = int(row["side"]) * (
                np.asarray([item[2] for item in check_rows], dtype=float)
                - np.asarray([item[1] for item in check_rows], dtype=float)
            )
            if int(np.argmax(check_bodies)) != expected_k:
                raise RuntimeError(f"R_DRIVE truncation mismatch {row['key']}")
        if bool(row["m15_complete"]) != exact or row["k_star"] != expected_k:
            raise RuntimeError(f"R_DRIVE diagnostic mismatch {row['key']}")
        if bool(row["feature_decision"]) != decision:
            raise RuntimeError(f"R_DRIVE decision mismatch {row['key']}")
        drive_checked += 1
    expected_missing = int(candidates["R_DRIVE"][2]["missing_m15_constituents"])
    if missing != expected_missing:
        raise RuntimeError(f"R_DRIVE missing count mismatch: {missing} != {expected_missing}")
    output["R_DRIVE"] = {
        "pass": True, "sampled_signal_closes": drive_checked,
        "exact_four_timestamp_assertions": drive_checked,
        "builder_accessed_next_m15_bar": any(
            pd.Timestamp(value) >= pd.Timestamp(row["signal_time"]) + pd.Timedelta(hours=1)
            for row in [r for r in enrich_rows(candidates["R_DRIVE"][2]) if r["quality"] == "marginal"]
            for value in row["feature_value"]["m15_timestamps"]
        ),
        "missing_constituents": missing,
    }
    print(
        f"CAUSALITY_FIXTURES PASS struct={struct_checked} drive={drive_checked} missing={missing}",
        flush=True,
    )
    return output


def mask_from_keys(keys: Iterable[tuple[str, int]]) -> dict[str, set[int]]:
    output: dict[str, set[int]] = {source: set() for source in SOURCES}
    for source, bar in keys:
        output[source].add(int(bar))
    return output


def placebo_cache_path(cell: str) -> Path:
    return CHECKPOINTS / f"{cell.lower()}_placebos.json"


def load_placebo_cache(cell: str, fingerprint: str) -> list[dict]:
    path = placebo_cache_path(cell)
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return value["rows"] if value.get("fingerprint") == fingerprint else []


def save_placebo_cache(cell: str, fingerprint: str, rows: list[dict]) -> None:
    CHECKPOINTS.mkdir(exist_ok=True)
    atomic_write_text(
        placebo_cache_path(cell),
        json.dumps(json_safe({"fingerprint": fingerprint, "rows": rows}), indent=2, sort_keys=True) + "\n",
    )


def matched_masks(candidate_diag: dict) -> tuple[list[dict[str, set[int]]], dict]:
    rows = [
        row for row in enrich_rows(candidate_diag)
        if row["quality"] == "marginal" and row["w2_pass"]
    ]
    observed_outside = {row["key"] for row in rows if not row["oos"] and row["feature_decision"]}
    pools: dict[tuple[str, int, str], list[tuple[str, int]]] = defaultdict(list)
    wanted = Counter()
    for row in rows:
        if not row["oos"]:
            continue
        stratum = (row["symbol"], int(row["side"]), row["quarter"])
        pools[stratum].append(row["key"])
        wanted[stratum] += int(bool(row["feature_decision"]))
    rng = np.random.default_rng(PLACEBO_SEED)
    masks = []
    for _ in range(PLACEBOS):
        chosen = set(observed_outside)
        for stratum in sorted(pools):
            pool = sorted(pools[stratum])
            count = wanted[stratum]
            if count:
                indexes = rng.choice(len(pool), size=count, replace=False)
                chosen.update(pool[int(index)] for index in np.atleast_1d(indexes))
        masks.append(mask_from_keys(chosen))
    return masks, {
        "seed": PLACEBO_SEED,
        "strata": [
            {"symbol": key[0], "side": key[1], "quarter": key[2],
             "pool": len(pools[key]), "selected": wanted[key]}
            for key in sorted(pools)
        ],
    }


def run_readmission_placebos(
    cell: str, candidate_diag: dict, fingerprint: str, quarter_policy: dict,
) -> tuple[list[dict], dict]:
    masks, matching = matched_masks(candidate_diag)
    rows = load_placebo_cache(cell, fingerprint)
    if len(rows) > PLACEBOS:
        rows = []
    for index in range(len(rows), PLACEBOS):
        mask = masks[index]
        tape, _, diag = build_registered(signal_detection="mask", marginal_admit=mask)
        row = {
            "index": index,
            "mask_sha256": sha256_json({key: sorted(value) for key, value in mask.items()}),
            "arm": arm_summary(tape, diag),
            "full_oos": discovery_summary(tape, diag, quarter_policy),
            "tape_sha256": tape_sha(tape),
        }
        rows.append(row)
        save_placebo_cache(cell, fingerprint, rows)
        if (index + 1) % 20 == 0:
            print(f"PLACEBO_PROGRESS {cell} {index + 1}/{PLACEBOS}", flush=True)
    return rows, matching


def run_seat_placebos(fingerprint: str, quarter_policy: dict) -> list[dict]:
    cell = "S_ZSEAT"
    rows = load_placebo_cache(cell, fingerprint)
    rng = np.random.default_rng(PLACEBO_SEED)
    seeds = [int(x) for x in rng.integers(0, 2**63 - 1, size=PLACEBOS, dtype=np.int64)]
    for index in range(len(rows), PLACEBOS):
        tape, _, diag = build_registered(seat_policy="random", seat_seed=seeds[index])
        rows.append({
            "index": index, "seat_seed": seeds[index], "tape_sha256": tape_sha(tape),
            "full_oos": discovery_summary(tape, diag, quarter_policy),
        })
        save_placebo_cache(cell, fingerprint, rows)
        if (index + 1) % 20 == 0:
            print(f"PLACEBO_PROGRESS {cell} {index + 1}/{PLACEBOS}", flush=True)
    return rows


def negative_readmission_keys(cell: str, candidate_diag: dict) -> set[tuple[str, int]]:
    if cell not in {"R_STRUCT", "R_DRIVE"}:
        raise ValueError(f"no readmission negative control for {cell}")
    return {
        row["key"] for row in enrich_rows(candidate_diag)
        if row["quality"] == "marginal" and row["w2_pass"]
        and (
            (cell == "R_STRUCT" and not row["feature_decision"])
            or (cell == "R_DRIVE" and row["k_star"] is not None and int(row["k_star"]) >= 2)
        )
    }


def negative_readmission(cell: str, candidate_diag: dict):
    keys = negative_readmission_keys(cell, candidate_diag)
    return build_registered(signal_detection="mask", marginal_admit=mask_from_keys(keys))


def placebo_statistics(values: list[float | None], observed: float | None) -> dict:
    normalized = [
        float(value) if value is not None and math.isfinite(float(value)) else None
        for value in values
    ]
    finite = np.asarray([value for value in normalized if value is not None], dtype=float)
    available = (
        len(normalized) == PLACEBOS and len(finite) == PLACEBOS
        and observed is not None and math.isfinite(float(observed))
    )
    exceed = int(np.sum(finite >= float(observed))) if available else None
    return {
        "n": len(normalized), "finite_n": len(finite),
        "nonfinite_n": len(normalized) - len(finite),
        "available": available,
        "unavailable_reason": (
            None if available else
            "observed_unavailable" if observed is None or not math.isfinite(float(observed)) else
            "placebo_count_not_200" if len(normalized) != PLACEBOS else
            "one_or_more_placebo_expectancies_nonfinite"
        ),
        "p95": float(np.percentile(finite, 95)) if available else None,
        "count_ge_observed": exceed,
        "empirical_one_sided_p": (1 + exceed) / (PLACEBOS + 1) if available else None,
        "values": normalized,
    }


def discovery_gate(
    cell: str, summary: dict, control: dict, breadth: dict, retain: dict,
    observed_value: float | None, placebo: dict, negative_value: float | None,
) -> tuple[bool, list[str]]:
    failures = []
    if summary["oos_expectancy"] is None or summary["oos_expectancy"] <= 0:
        failures.append("E2_OOS_EXPECTANCY_NONPOSITIVE")
    if summary["dsr"] is None or not math.isfinite(summary["dsr"]) or summary["dsr"] < 0.95:
        failures.append("DSR_LT_0_95")
    if observed_value is None or not math.isfinite(observed_value):
        failures.append("OBSERVED_ARM_UNAVAILABLE")
    elif observed_value <= 0:
        failures.append("OBSERVED_ARM_NONPOSITIVE")
    if not placebo["available"]:
        failures.append("PLACEBO_DISTRIBUTION_UNAVAILABLE")
    elif observed_value is None or observed_value <= placebo["p95"]:
        failures.append("OBSERVED_NOT_ABOVE_PLACEBO95")
    if placebo["empirical_one_sided_p"] is None:
        failures.append("PLACEBO_P_UNAVAILABLE")
    elif placebo["empirical_one_sided_p"] > P_LIMIT:
        failures.append("PLACEBO_P_GT_BONFERRONI")
    if negative_value is None or not math.isfinite(negative_value):
        failures.append("NEGATIVE_CONTROL_UNAVAILABLE")
    elif observed_value is None or not math.isfinite(observed_value) or negative_value >= observed_value:
        failures.append("NEGATIVE_CONTROL_NOT_WORSE")
    if breadth["symbol_nonnegative"] < 3:
        failures.append("SYMBOL_DELTA_NONNEGATIVE_LT_3_OF_4")
    if breadth["quarter_nonnegative_fraction"] < 0.60:
        failures.append("QUARTER_DELTA_NONNEGATIVE_LT_60PCT")
    if cell in {"R_STRUCT", "R_DRIVE"}:
        if retain["admitted_fraction"] < 0.70:
            failures.append("A1_ADMITTED_RETENTION_LT_70PCT")
        if retain["filled_fraction"] < 0.70:
            failures.append("A1_FILLED_RETENTION_LT_70PCT")
    elif retain["filled_fraction"] < 0.97:
        failures.append("A1_FILLED_RETENTION_LT_97PCT")
    return not failures, failures


def run_discovery(
    a1: tuple, candidates: dict[str, tuple], spec_sha: str, bundle_sha: str,
) -> dict:
    a1_tape, _, a1_diag = a1
    quarter_policy = quarter_completeness(a1_diag)
    control = discovery_summary(a1_tape, a1_diag, quarter_policy)
    output = {
        "quarter_completeness": quarter_policy,
        "control": {"summary": control, "census": census(a1_tape, a1_diag)}, "cells": {},
    }
    for cell in CELL_ORDER:
        tape, _, diag = candidates[cell]
        summary = discovery_summary(tape, diag, quarter_policy)
        breadth = delta_breadth(summary, control)
        retain = retention(diag, a1_diag)
        fingerprint = sha256_json({
            "experiment_bundle_sha256": bundle_sha,
            "spec": spec_sha, "runner": sha256_file(Path(__file__)),
            "cell": cell, "tape": tape_sha(tape), "placebos": PLACEBOS,
        })
        if cell in {"R_STRUCT", "R_DRIVE"}:
            positive = arm_summary(tape, diag)
            negative_tape, _, negative_diag = negative_readmission(cell, diag)
            negative = arm_summary(negative_tape, negative_diag)
            placebos, matching = run_readmission_placebos(
                cell, diag, fingerprint, quarter_policy,
            )
            values = [row["arm"]["filled_oos_expectancy"] for row in placebos]
            observed_value = positive["filled_oos_expectancy"]
            negative_value = negative["filled_oos_expectancy"]
            negative_record = {
                "definition": "inside_channel" if cell == "R_STRUCT" else "k_star_ge_2",
                "arm": negative, "census": census(negative_tape, negative_diag),
                "tape_sha256": tape_sha(negative_tape),
            }
        else:
            positive = summary
            negative_tape, _, negative_diag = build_registered(seat_policy="min_z")
            negative = discovery_summary(negative_tape, negative_diag, quarter_policy)
            placebos = run_seat_placebos(fingerprint, quarter_policy)
            matching = {"seed": PLACEBO_SEED, "kind": "same_epoch_random_claimant_order"}
            values = [row["full_oos"]["oos_expectancy"] for row in placebos]
            observed_value = summary["oos_expectancy"]
            negative_value = negative["oos_expectancy"]
            negative_record = {
                "definition": "ascending_z_arbitration", "full_oos": negative,
                "census": census(negative_tape, negative_diag),
                "tape_sha256": tape_sha(negative_tape),
            }
        placebo = placebo_statistics(values, observed_value)
        passed, failures = discovery_gate(
            cell, summary, control, breadth, retain, observed_value, placebo, negative_value,
        )
        output["cells"][cell] = {
            "pass": passed, "failures": failures,
            "tape_sha256": tape_sha(tape), "census": census(tape, diag),
            "summary": summary, "positive_arm": positive,
            "negative_control": negative_record, "retention": retain,
            "delta_breadth": breadth, "matching": matching,
            "placebo_summary": placebo, "placebos": placebos,
        }
        print("DISCOVERY_RESULT", cell, "PASS" if passed else "FAIL", ",".join(failures) or "none", flush=True)
        gc.collect()
    return output


def exact_path0(tape, metas, policy: RiskPolicy, boot: BootstrapSpec) -> dict:
    reference = run_monte_carlo(
        tape, metas, (policy,), paths=1, path_start=0, bootstrap=boot,
        config=SimulationConfig(equity_mode=EquityMode.TWO_STOP),
    )[policy.name]
    actual = csharp_engine.run_csharp_monte_carlo(
        tape, metas, (policy,), paths=1, path_start=0, bootstrap=boot,
    )[policy.name]
    mismatches = [
        name for name in (reference.rows.dtype.names or ())
        if reference.rows[name].tobytes() != actual.rows[name].tobytes()
    ]
    if mismatches:
        raise RuntimeError(f"Python/C# path-0 mismatch fields: {mismatches}")
    return {"exact": True, "row_sha256": actual.sha256(), "row": json_safe(actual.rows[0].tolist())}


def common_bootstrap(tapes: Iterable) -> BootstrapSpec:
    tapes = list(tapes)
    eligible = set(tapes[0].eligible_flat_block_starts(BLOCK))
    for tape in tapes[1:]:
        eligible &= set(tape.eligible_flat_block_starts(BLOCK))
    if not eligible:
        raise RuntimeError("no common eligible flat blocks")
    return BootstrapSpec(seed=BOOT_SEED, block_length=BLOCK, eligible_block_starts=tuple(sorted(eligible)))


def mc_checkpoint(label: str, paths: int, path_start: int) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
    return CHECKPOINTS / f"mc_{safe}_{path_start}_{path_start + paths}.npz"


def mc_cache_fingerprint(
    tape, policy: RiskPolicy, boot: BootstrapSpec, paths: int,
    path_start: int, bundle_sha: str,
) -> str:
    return sha256_json({
        "experiment_bundle_sha256": bundle_sha,
        "tape": tape_sha(tape), "policy": asdict(policy), "seed": boot.seed,
        "block": boot.block_length, "eligible": list(boot.eligible_block_starts or ()),
        "paths": paths, "path_start": path_start, "chunk": CHUNK,
    })


def run_chunks(
    tape, metas, policy: RiskPolicy, boot: BootstrapSpec, paths: int, label: str,
    *, path_start: int, bundle_sha: str,
) -> CompactRun:
    CHECKPOINTS.mkdir(exist_ok=True)
    path = mc_checkpoint(label, paths, path_start)
    fingerprint = mc_cache_fingerprint(tape, policy, boot, paths, path_start, bundle_sha)
    rows = []
    start = 0
    if path.exists():
        with np.load(path, allow_pickle=False) as saved:
            saved_fingerprint = str(saved["fingerprint"].item())
            if saved_fingerprint == fingerprint:
                cached = saved["rows"]
                if len(cached) <= paths and len(cached) % CHUNK == 0:
                    rows = [cached]
                    start = len(cached)
    for relative_offset in range(start, paths, CHUNK):
        count = min(CHUNK, paths - relative_offset)
        absolute_offset = path_start + relative_offset
        part = csharp_engine.run_csharp_monte_carlo(
            tape, metas, (policy,), paths=count, path_start=absolute_offset, bootstrap=boot,
        )[policy.name]
        rows.append(part.rows)
        combined = np.concatenate(rows)
        temp = path.with_suffix(".tmp")
        with temp.open("wb") as handle:
            np.savez_compressed(handle, fingerprint=np.asarray(fingerprint), rows=combined)
        temp.replace(path)
        if relative_offset + count == paths or (relative_offset + count) % 5_000 == 0:
            print(
                f"MC_PROGRESS {label} {relative_offset + count}/{paths} "
                f"path_ids={path_start}..{absolute_offset + count - 1}", flush=True,
            )
    if not rows:
        raise RuntimeError(f"empty MC checkpoint for {label}")
    return CompactRun(policy, np.concatenate(rows) if len(rows) > 1 else rows[0])


def counter_totals(run: CompactRun) -> dict:
    return {
        phase: {name: int(run.rows[f"{phase}_{name}"].sum()) for name in COUNTER_FIELDS}
        for phase in ("p1", "p2")
    }


def run_record(run: CompactRun) -> dict:
    reasons = {}
    for phase in ("p1", "p2"):
        values, counts = np.unique(run.rows[f"{phase}_reason"], return_counts=True)
        reasons[phase] = {str(int(v)): int(n) for v, n in zip(values, counts)}
    return {
        "summary": asdict(run.summary()), "row_sha256": run.sha256(),
        "counter_totals": counter_totals(run), "reason_counts": reasons,
    }


def paired(candidate: CompactRun, control: CompactRun) -> dict:
    lower, n10, n01, p10_lower, p01_upper = candidate.paired_delta_lower(control)
    discordant = n10 + n01
    return {
        "lower": lower, "n10_candidate_only_pass": n10, "n01_control_only_pass": n01,
        "discordant": discordant, "point_delta": (n10 - n01) / len(candidate.rows),
        "p10_clopper_pearson_lower": p10_lower,
        "p01_clopper_pearson_upper": p01_upper,
        "mcnemar_exact_one_sided_p_value": (
            float(binomtest(n10, discordant, 0.5, alternative="greater").pvalue)
            if discordant else 1.0
        ),
    }


def account_gate(candidate: dict, control: dict, comparison: dict) -> tuple[bool, list[str]]:
    failures = []
    if candidate["hard_probability"] > 0.003700:
        failures.append("HARD_GT_0_003700")
    if comparison["lower"] <= 0:
        failures.append("PAIRED_LOWER_NOT_POSITIVE")
    if comparison["mcnemar_exact_one_sided_p_value"] > P_LIMIT:
        failures.append("MCNEMAR_P_GT_BONFERRONI")
    if candidate["timeout_probability"] > control["timeout_probability"] + 0.005000:
        failures.append("TIMEOUT_GT_A1_PLUS_0_005")
    cand_median = candidate["median_total_days_success"]
    base_median = control["median_total_days_success"]
    if (
        cand_median is None or base_median is None
        or not math.isfinite(float(cand_median)) or not math.isfinite(float(base_median))
        or cand_median > 1.10 * base_median
    ):
        failures.append("MEDIAN_DAYS_GT_1_10_X_A1")
    return not failures, failures


def run_account_stage(
    tapes: dict[str, Any], metas, policy: RiskPolicy, boot: BootstrapSpec,
    paths: int, label: str, *, path_start: int, bundle_sha: str,
) -> dict:
    runs = {
        name: run_chunks(
            tape, metas, policy, boot, paths, f"{label}:{name}",
            path_start=path_start, bundle_sha=bundle_sha,
        )
        for name, tape in tapes.items()
    }
    control_record = run_record(runs["A1"])
    cells = {}
    for cell in CELL_ORDER:
        if cell not in runs:
            continue
        candidate_record = run_record(runs[cell])
        comparison = paired(runs[cell], runs["A1"])
        passed, failures = account_gate(
            candidate_record["summary"], control_record["summary"], comparison,
        )
        cells[cell] = {
            "record": candidate_record, "paired": comparison,
            "pass": passed, "failures": failures,
        }
        print("ACCOUNT_RESULT", label, cell, "PASS" if passed else "FAIL", ",".join(failures) or "none", flush=True)
    return {
        "paths": paths, "path_start": path_start,
        "path_end_exclusive": path_start + paths,
        "control": control_record, "cells": cells,
    }


def main() -> None:
    global ACTIVE_BUNDLE_SHA256
    commit = git_commit()
    bundle = experiment_bundle()
    ACTIVE_BUNDLE_SHA256 = bundle["sha256"]
    data_output = verify_data()
    spec_sha = sha256_file(SPEC)
    registered_sha = SPEC_HASH_FILE.read_text(encoding="utf-8").split()[0]
    if spec_sha != registered_sha:
        raise RuntimeError(f"spec hash mismatch: {spec_sha} != {registered_sha}")
    cache_record = preload_market_caches()
    self_tests = synthetic_self_tests()
    regressions, a1 = protected_regressions()

    candidates = {
        "R_STRUCT": build_registered(signal_detection="r_struct"),
        "S_ZSEAT": build_registered(seat_policy="max_z"),
        "R_DRIVE": build_registered(signal_detection="r_drive"),
    }
    causality = causality_fixtures(candidates)
    output = {
        "verdict": "INCOMPLETE", "tested_commit": commit,
        "spec": str(SPEC.relative_to(ROOT)), "spec_sha256": spec_sha,
        "experiment_bundle": bundle,
        "data_verification": data_output, "stress": "E2_STRESS",
        "market_caches": cache_record,
        "placebo_seed": PLACEBO_SEED, "placebos_per_cell": PLACEBOS,
        "account_seed": BOOT_SEED, "block_length": BLOCK, "chunk_size": CHUNK,
        "trial_charge": {"discovery_cells": 3, "conditional_confirmation_cells": 0},
        "protected_regressions": regressions, "synthetic_self_tests": self_tests,
        "causality_fixtures": causality,
        "experiment_file_sha256": {
            record["path"]: record["canonical_head_sha256"]
            for record in bundle["files"]
        },
        "discovery": None, "account_screen": None, "account_confirmation": None,
    }
    write_result(output)
    output["discovery"] = run_discovery(
        a1, candidates, spec_sha, bundle["sha256"],
    )
    write_result(output)
    survivors = [cell for cell in CELL_ORDER if output["discovery"]["cells"][cell]["pass"]]
    if not survivors:
        output["verdict"] = "SIGNAL_SURFACE_EXHAUSTED_NO_SURVIVOR"
        write_result(output)
        finish(output)
        return

    all_tapes = {"A1": a1[0], **{cell: candidates[cell][0] for cell in survivors}}
    boot = common_bootstrap(all_tapes.values())
    metas = ftmo_metas(SOURCES)
    symbols = tuple(metas)
    configure_symbols(symbols)
    risk_map = {symbol: (0.0005 if symbol == "USDJPY" else 0.0030) for symbol in symbols}
    policy = RiskPolicy("V136_SIGNAL_DYNAMIC_RISK", risk_map, risk_map)
    path0 = {name: exact_path0(tape, metas, policy, boot) for name, tape in all_tapes.items()}
    output["account_common"] = {
        "eligible_blocks": len(boot.eligible_block_starts or ()),
        "eligible_blocks_sha256": sha256_json(list(boot.eligible_block_starts or ())),
        "risk_fraction_by_symbol_both_phases": risk_map,
        "path0_python_csharp": path0,
    }
    output["account_screen"] = run_account_stage(
        all_tapes, metas, policy, boot, SCREEN_PATHS, "SCREEN",
        path_start=0, bundle_sha=bundle["sha256"],
    )
    write_result(output)
    advancing = [
        cell for cell in CELL_ORDER
        if cell in output["account_screen"]["cells"]
        and output["account_screen"]["cells"][cell]["pass"]
    ]
    if not advancing:
        output["verdict"] = "SIGNAL_SURFACE_EXHAUSTED_NO_SURVIVOR"
        write_result(output)
        finish(output)
        return
    advancing.sort(key=lambda cell: (
        -output["account_screen"]["cells"][cell]["paired"]["lower"],
        output["account_screen"]["cells"][cell]["record"]["summary"]["timeout_probability"],
        output["account_screen"]["cells"][cell]["record"]["summary"]["median_total_days_success"],
        CELL_ORDER.index(cell),
    ))
    winner = advancing[0]
    output["stage1_winner"] = winner
    output["trial_charge"]["conditional_confirmation_cells"] = 1
    confirmation_tapes = {"A1": a1[0], winner: candidates[winner][0]}
    output["account_confirmation"] = run_account_stage(
        confirmation_tapes, metas, policy, boot, CONFIRM_PATHS, "CONFIRMATION",
        path_start=SCREEN_PATHS, bundle_sha=bundle["sha256"],
    )
    confirmed = output["account_confirmation"]["cells"][winner]["pass"]
    output["verdict"] = (
        "SIGNAL_CHALLENGER_CONFIRMED_BEATS_A1"
        if confirmed else "SIGNAL_CHALLENGER_CONFIRMATION_REJECTED"
    )
    write_result(output)
    finish(output)


def finish(output: dict) -> None:
    digest = sha256_file(RESULT)
    atomic_write_text(RESULT_HASH, f"{digest}  {RESULT.name}\n")
    print("FINAL", output["verdict"], flush=True)
    print("RESULT_SHA256", digest, flush=True)
    print("RESULT_FILE", RESULT, flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        append_failure_journal(exc)
        print(f"REGISTERED_FAILURE {type(exc).__name__}: {exc}", flush=True)
        raise
