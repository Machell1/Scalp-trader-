"""Registered overnight-short comparison: cash close/open vs broker rollover."""
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
SPEC = ROOT / "docs" / "OVERNIGHT_SHORT_THESIS_SPEC_2026-07-14.md"
OUT = HERE / "overnight_short_thesis_results.json"
EXPECTED_HASH = "2cf705ceb2e9c665b80088cdfb20500674e49825d2fa52005c75c017bb869607"

SPECS = {
    "Wall_Street_30": ("US30.cash", ZoneInfo("America/New_York"), (15, 45), (9, 30)),
    "US_Tech_100": ("US100.cash", ZoneInfo("America/New_York"), (15, 45), (9, 30)),
    "Japan_225": ("JP225.cash", ZoneInfo("Asia/Tokyo"), (15, 15), (9, 0)),
}
BROKER = ZoneInfo("Europe/Helsinki")


def protocol_hash() -> str:
    data = SPEC.read_bytes()
    marker = b"\n\n**Recorded protocol SHA256:**"
    return hashlib.sha256(data[: data.index(marker) + 1]).hexdigest()


def stats(rows):
    x = np.asarray([row["bps"] for row in rows], float)
    return {
        "n": int(len(x)), "mean_net_bps": float(x.mean()) if len(x) else None,
        "win_rate": float((x > 0.0).mean()) if len(x) else None,
        "total_net_bps": float(x.sum()) if len(x) else 0.0,
        "worst_net_bps": float(x.min()) if len(x) else None,
    }


def overnight_rows(frame: pd.DataFrame, close_zone: ZoneInfo, close_time, open_time, multiplier: float):
    utc = pd.to_datetime(frame["time"], utc=True)
    local = utc.dt.tz_convert(close_zone)
    close_idx = np.flatnonzero((local.dt.hour == close_time[0]) & (local.dt.minute == close_time[1]))
    open_idx = np.flatnonzero((local.dt.hour == open_time[0]) & (local.dt.minute == open_time[1]))
    cutoff = int(len(frame) * 0.7)
    rows, skipped = [], 0
    for entry_i in close_idx:
        loc = int(np.searchsorted(open_idx, entry_i + 1, side="left"))
        if loc >= len(open_idx):
            skipped += 1
            continue
        exit_i = int(open_idx[loc])
        if local.iloc[exit_i].date() <= local.iloc[entry_i].date():
            skipped += 1
            continue
        entry = float(frame.iloc[entry_i]["close"])
        cover = float(frame.iloc[exit_i]["open"]) + multiplier * float(frame.iloc[exit_i]["spread_price"])
        if not (np.isfinite(entry) and np.isfinite(cover) and entry > 0 and cover > 0):
            skipped += 1
            continue
        rows.append({"entry_bar": int(entry_i), "exit_bar": exit_i,
                     "oos": bool(entry_i >= cutoff), "bps": (entry - cover) / entry * 10_000.0})
    return rows, {"close_candidates": int(len(close_idx)), "skipped": int(skipped)}


def measure_cell(kind: str, multiplier: float):
    output, all_rows = {}, []
    for source, (label, zone, cash_close, cash_open) in SPECS.items():
        frame = pd.read_csv(DATA / f"{source}.csv")
        if kind == "CASH":
            rows, diag = overnight_rows(frame, zone, cash_close, cash_open, multiplier)
        else:
            rows, diag = overnight_rows(frame, BROKER, (23, 45), (0, 0), multiplier)
        output[label] = {"all": stats(rows), "oos": stats([x for x in rows if x["oos"]]), **diag}
        all_rows.extend(rows)
    pooled_oos = stats([x for x in all_rows if x["oos"]])
    per_symbol = [output[label]["oos"] for label, *_ in SPECS.values()]
    edge = bool(
        pooled_oos["mean_net_bps"] is not None and pooled_oos["mean_net_bps"] > 0.0
        and all(x["n"] >= 50 and x["mean_net_bps"] is not None and x["mean_net_bps"] > 0.0 for x in per_symbol)
    )
    return {"per_symbol": output, "pooled_oos": pooled_oos, "provisional_edge": edge}


def main():
    actual = protocol_hash()
    if actual != EXPECTED_HASH:
        raise RuntimeError(f"protocol hash mismatch: {actual}")
    output = {"protocol_sha256": actual, "cells": {}}
    for kind in ("CASH", "BROKER"):
        output["cells"][kind] = {}
        for label, multiplier in (("E1_MEASURED", 1.0), ("E2_STRESS", 2.0)):
            value = measure_cell(kind, multiplier)
            output["cells"][kind][label] = value
            print(kind, label, value["pooled_oos"], "edge", value["provisional_edge"], flush=True)
    cash = output["cells"]["CASH"]["E2_STRESS"]
    broker = output["cells"]["BROKER"]["E2_STRESS"]
    if cash["provisional_edge"] and broker["provisional_edge"]:
        winner = "CASH" if cash["pooled_oos"]["mean_net_bps"] > broker["pooled_oos"]["mean_net_bps"] else "BROKER"
    elif cash["provisional_edge"]:
        winner = "CASH"
    elif broker["provisional_edge"]:
        winner = "BROKER"
    else:
        winner = None
    output["better_provisional_edge"] = winner
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RESULT_FILE={OUT}")


if __name__ == "__main__":
    main()
