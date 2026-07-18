"""Research-only implementation of the fixed video-gap-fade protocol."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data" / "derivM15_spreadgated"
SPEC = ROOT / "docs" / "VIDEO_GAP_FADE_SPEC_2026-07-14.md"
OUT = HERE / "video_gap_fade_results.json"
EXPECTED_HASH = "8f5acbfc8cf7d216bb16e4150184d33bab9a26e918559ada842960f5cad8901e"
GAP_THRESHOLD = 0.005

SESSIONS = {
    "Wall_Street_30": ("US30.cash", ZoneInfo("America/New_York"), (9, 30), (15, 45)),
    "US_Tech_100": ("US100.cash", ZoneInfo("America/New_York"), (9, 30), (15, 45)),
    "Japan_225": ("JP225.cash", ZoneInfo("Asia/Tokyo"), (9, 0), (15, 15)),
}


def protocol_hash() -> str:
    data = SPEC.read_bytes()
    start = data.index(b"**PRE-REGISTRATION ENDS")
    end = data.index(b"\n", start) + 1
    return hashlib.sha256(data[:end]).hexdigest()


def stats(rows: list[dict]) -> dict:
    returns = np.asarray([row["bps"] for row in rows], dtype=float)
    return {
        "n": int(len(returns)),
        "mean_net_bps": float(returns.mean()) if len(returns) else None,
        "win_rate": float((returns > 0.0).mean()) if len(returns) else None,
        "total_net_bps": float(returns.sum()) if len(returns) else 0.0,
        "worst_net_bps": float(returns.min()) if len(returns) else None,
    }


def session_rows(
    frame: pd.DataFrame,
    zone: ZoneInfo,
    open_time: tuple[int, int],
    close_time: tuple[int, int],
    multiplier: float,
) -> tuple[list[dict], dict]:
    local = pd.to_datetime(frame["time"], utc=True).dt.tz_convert(zone)
    open_idx = np.flatnonzero(
        (local.dt.hour == open_time[0]) & (local.dt.minute == open_time[1])
    )
    close_idx = np.flatnonzero(
        (local.dt.hour == close_time[0]) & (local.dt.minute == close_time[1])
    )
    local_dates = local.dt.date.to_numpy()
    close_by_date = {local_dates[index]: int(index) for index in close_idx}
    cutoff = int(len(frame) * 0.7)
    rows: list[dict] = []
    diagnostics = {"open_candidates": int(len(open_idx)), "qualified": 0, "skipped": 0}

    for entry_i in open_idx:
        prior_position = int(np.searchsorted(close_idx, entry_i)) - 1
        exit_i = close_by_date.get(local_dates[entry_i])
        if prior_position < 0 or exit_i is None or exit_i <= entry_i:
            diagnostics["skipped"] += 1
            continue
        reference_i = int(close_idx[prior_position])
        reference = float(frame.iloc[reference_i]["close"])
        entry = float(frame.iloc[entry_i]["open"])
        exit_price = float(frame.iloc[exit_i]["close"]) + multiplier * float(frame.iloc[exit_i]["spread_price"])
        if not (np.isfinite(reference) and np.isfinite(entry) and np.isfinite(exit_price) and reference > 0.0 and entry > 0.0 and exit_price > 0.0):
            diagnostics["skipped"] += 1
            continue
        gap = (entry - reference) / reference
        if gap < GAP_THRESHOLD:
            continue
        diagnostics["qualified"] += 1
        rows.append({
            "entry_bar": int(entry_i), "exit_bar": exit_i, "gap_fraction": float(gap),
            "oos": bool(entry_i >= cutoff), "bps": (entry - exit_price) / entry * 10_000.0,
        })
    return rows, diagnostics


def measure(multiplier: float) -> dict:
    symbols, pooled = {}, []
    for source, (label, zone, open_time, close_time) in SESSIONS.items():
        rows, diag = session_rows(pd.read_csv(DATA / f"{source}.csv"), zone, open_time, close_time, multiplier)
        oos = [row for row in rows if row["oos"]]
        symbols[label] = {"all": stats(rows), "oos": stats(oos), **diag}
        pooled.extend(oos)
    pooled_oos = stats(pooled)
    per_symbol = [symbols[label]["oos"] for label, *_ in SESSIONS.values()]
    provisional = bool(
        pooled_oos["n"] >= 300
        and pooled_oos["mean_net_bps"] is not None
        and pooled_oos["mean_net_bps"] > 0.0
        and all(item["n"] >= 25 and item["mean_net_bps"] is not None and item["mean_net_bps"] > 0.0 for item in per_symbol)
    )
    return {"per_symbol": symbols, "pooled_oos": pooled_oos, "provisional_edge": provisional}


def main() -> None:
    actual_hash = protocol_hash()
    if actual_hash != EXPECTED_HASH:
        raise RuntimeError(f"protocol hash mismatch: expected {EXPECTED_HASH}, got {actual_hash}")
    result = {"protocol_sha256": actual_hash, "gap_threshold": GAP_THRESHOLD, "cells": {}}
    for label, multiplier in (("E1_MEASURED", 1.0), ("E2_STRESS", 2.0)):
        result["cells"][label] = measure(multiplier)
        print(label, result["cells"][label]["pooled_oos"], "edge", result["cells"][label]["provisional_edge"], flush=True)
    result["verdict"] = "PROVISIONAL_EDGE" if result["cells"]["E2_STRESS"]["provisional_edge"] else "DISPOSED"
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RESULT_FILE={OUT}")


if __name__ == "__main__":
    main()
