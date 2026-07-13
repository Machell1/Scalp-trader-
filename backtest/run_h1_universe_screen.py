"""Run Stage A of the preregistered H1 FTMO universe admission study."""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

from parity_engine import START, prep_symbol
from run_h1_timeframe_screen import aggregate_h1, run_cell
from scalper_backtest import wilder_atr
from snapshot_h1_universe_meta import SOURCE_TO_FTMO
from walkforward_dsr import real_cost_per_side


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
META_PATH = HERE / "h1_universe_broker_meta.json"
RESULT_PATH = HERE / "h1_universe_screen_results.json"
PARTS = HERE / "h1_universe_screen_parts"
BASE_SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225")


@dataclass(frozen=True)
class LoadedSymbol:
    source: str
    ftmo_symbol: str
    h1: pd.DataFrame
    cost_e1: float
    cost_parts: dict[str, float]


def aggregate_h1_fast(raw: pd.DataFrame) -> pd.DataFrame:
    """Vectorized equivalent of the registered complete-four-bar aggregation."""
    frame = raw.copy()
    frame["_dt"] = pd.to_datetime(frame["time"])
    frame = frame.sort_values("_dt")
    frame["_hour"] = frame["_dt"].dt.floor("h")
    frame["_offset"] = (frame["_dt"] - frame["_hour"]).dt.total_seconds().astype(int)
    grouped = frame.groupby("_hour", sort=True)
    checks = grouped["_offset"].agg(["count", "nunique", "min", "max", "sum"])
    valid = checks.index[
        (checks["count"] == 4)
        & (checks["nunique"] == 4)
        & (checks["min"] == 0)
        & (checks["max"] == 2700)
        & (checks["sum"] == 5400)
    ]
    out = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        spread_price=("spread_price", "max"),
    ).loc[valid]
    out.index.name = "time"
    return out.reset_index()


def aggregation_regression() -> None:
    sample = pd.read_csv(source_path("Wall_Street_30"), nrows=1200)
    reference = aggregate_h1(sample).reset_index(drop=True)
    vectorized = aggregate_h1_fast(sample).reset_index(drop=True)
    pd.testing.assert_frame_equal(reference, vectorized, check_dtype=False)
    print(f"AGGREGATION_REGRESSION PASS rows={len(reference)}", flush=True)


def source_path(source: str) -> Path:
    for folder in ("derivM15_spreadgated", "derivM15_diverse"):
        path = DATA / folder / f"{source}.csv"
        if path.exists():
            return path
    raise FileNotFoundError(source)


def median_atr(frame: pd.DataFrame) -> float:
    atr = wilder_atr(
        frame["high"].to_numpy(float),
        frame["low"].to_numpy(float),
        frame["close"].to_numpy(float),
        14,
    )
    value = float(np.nanmedian(atr))
    if not math.isfinite(value) or value <= 0:
        raise ValueError("invalid median H1 ATR")
    return value


def load_symbol(source: str, meta: dict) -> LoadedSymbol:
    path = source_path(source)
    raw = pd.read_csv(path)
    has_source_spread = "spread_price" in raw.columns
    if not has_source_spread:
        # The manifest-pinned diverse frame has no spread field.  Its existing
        # preregistered universe convention is the frozen 0.03 ATR/side cost.
        raw["spread_price"] = 0.0
    h1 = aggregate_h1_fast(raw)
    med_atr = median_atr(h1)
    row = meta["symbols"][source]
    source_spread = float(real_cost_per_side(h1)) if has_source_spread else 0.03
    ftmo_spread = 0.5 * float(row["spread_points"]) * float(row["point"]) / med_atr
    commission = row["commission"]
    if commission["kind"] == "zero":
        commission_atr = 0.0
    elif commission["kind"] == "notional_fraction":
        commission_atr = (
            float(commission["per_side_fraction"])
            * float(np.nanmedian(h1["close"].to_numpy(float)))
            / med_atr
        )
    elif commission["kind"] == "usd_per_lot":
        tick_value = float(row["trade_tick_value_loss"])
        tick_size = float(row["trade_tick_size"])
        commission_price = float(commission["per_side_usd_per_lot"]) * tick_size / tick_value
        commission_atr = commission_price / med_atr
    else:
        raise ValueError(f"unknown commission rule: {commission}")
    spread_cost = max(source_spread, ftmo_spread if ftmo_spread > 0 else 0.0)
    return LoadedSymbol(
        source=source,
        ftmo_symbol=row["ftmo_symbol"],
        h1=h1,
        cost_e1=spread_cost + commission_atr,
        cost_parts={
            "median_h1_atr": med_atr,
            "source_spread_per_side_atr": source_spread,
            "ftmo_snapshot_spread_per_side_atr": ftmo_spread,
            "commission_per_side_atr": commission_atr,
        },
    )


def quarter_stats(rows: list[tuple[int, float, bool]], frame: pd.DataFrame) -> list[dict]:
    signal = {int(pd.Timestamp(t).timestamp()): pd.Timestamp(t) for t in frame["time"]}
    grouped: dict[str, list[float]] = {}
    for epoch, r_value, is_oos in rows:
        if not is_oos:
            continue
        timestamp = signal.get(int(epoch), pd.Timestamp(epoch, unit="s"))
        grouped.setdefault(str(timestamp.to_period("Q")), []).append(float(r_value))
    return [
        {"quarter": quarter, "n": len(values), "expectancy": float(np.mean(values))}
        for quarter, values in sorted(grouped.items())
    ]


def stats(rows: list[tuple[int, float, bool]], frame: pd.DataFrame) -> dict:
    all_r = np.asarray([item[1] for item in rows], dtype=float)
    oos_r = np.asarray([item[1] for item in rows if item[2]], dtype=float)
    return {
        "n": int(len(all_r)),
        "expectancy": float(all_r.mean()) if len(all_r) else None,
        "win_rate": float((all_r > 0).mean()) if len(all_r) else None,
        "oos_n": int(len(oos_r)),
        "oos_expectancy": float(oos_r.mean()) if len(oos_r) else None,
        "oos_win_rate": float((oos_r > 0).mean()) if len(oos_r) else None,
        "oos_quarters": quarter_stats(rows, frame),
    }


def complete_oos_quarters(items: list[dict]) -> list[dict]:
    # Calendar-edge quarters may be partial.  Interior OOS quarters are the
    # deterministic complete set; when only one/two quarters exist, retain all.
    return items[1:-1] if len(items) >= 3 else items


def gate(e1: dict, e2: dict, broker: dict) -> tuple[bool, list[str]]:
    failures = []
    if e1["oos_expectancy"] is None or e1["oos_expectancy"] <= 0:
        failures.append("E1_OOS_NONPOSITIVE")
    if e2["oos_expectancy"] is None or e2["oos_expectancy"] <= 0:
        failures.append("E2_OOS_NONPOSITIVE")
    if e2["oos_n"] < 50:
        failures.append("E2_OOS_N_LT_50")
    quarters = complete_oos_quarters(e2["oos_quarters"])
    positive = sum(item["expectancy"] > 0 for item in quarters)
    if not quarters or positive / len(quarters) < 0.60:
        failures.append("E2_POSITIVE_QUARTERS_LT_60PCT")
    if not quarters or quarters[-1]["expectancy"] <= 0:
        failures.append("E2_LATEST_COMPLETE_QUARTER_NONPOSITIVE")
    sizing = (
        "trade_tick_size", "trade_tick_value_loss", "trade_tick_value_profit",
        "volume_min", "volume_step", "volume_max",
    )
    if int(broker["trade_mode"]) == 0 or any(float(broker[key]) <= 0 for key in sizing):
        failures.append("FTMO_METADATA_NOT_TRADABLE")
    return not failures, failures


def evaluate_source(source: str, meta: dict) -> dict:
    loaded = load_symbol(source, meta)
    modes = {}
    for name, multiplier in (("E1_MEASURED", 1.0), ("E2_STRESS", 2.0)):
        prepared = prep_symbol(loaded.h1, loaded.cost_e1 * multiplier, source)
        prepared.oos = np.arange(len(loaded.h1)) >= int(len(loaded.h1) * 0.7)
        rows = run_cell(prepared, market=False)
        modes[name] = stats(rows, loaded.h1)
    passed, failures = gate(
        modes["E1_MEASURED"], modes["E2_STRESS"], meta["symbols"][source]
    )
    return {
        "ftmo_symbol": loaded.ftmo_symbol,
        "source_file": str(source_path(source).relative_to(HERE)),
        "h1_bars": int(len(loaded.h1)),
        "cost_e1_per_side_atr": loaded.cost_e1,
        "cost_parts": loaded.cost_parts,
        "modes": modes,
        "stage_a_pass": bool(passed and source not in BASE_SOURCES),
        "failures": failures,
    }


def print_row(row: dict) -> None:
    modes = row["modes"]
    print(
        row["ftmo_symbol"],
        "PASS" if row["stage_a_pass"] else "CONTROL" if row["ftmo_symbol"] in {
            "US30.cash", "US100.cash", "JP225.cash"
        } else "FAIL",
        f"E2_oos_n={modes['E2_STRESS']['oos_n']}",
        f"E2_oos_exp={modes['E2_STRESS']['oos_expectancy']}",
        ",".join(row["failures"]) if row["failures"] else "none",
        flush=True,
    )


def worker(source: str) -> None:
    if source not in SOURCE_TO_FTMO:
        raise ValueError(f"unknown source {source}")
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    row = evaluate_source(source, meta)
    PARTS.mkdir(exist_ok=True)
    path = PARTS / f"{source}.json"
    path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print_row(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source")
    args = parser.parse_args()
    if args.source:
        worker(args.source)
        return
    aggregation_regression()
    output = {
        "metadata_sha256": "ba1f3cdeaca429764129685f79a4267e1bbc55b2fead70c8187db431fd828928",
        "base_sources": list(BASE_SOURCES),
        "symbols": {},
    }
    for source in SOURCE_TO_FTMO:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--source", source],
            cwd=HERE.parent,
            text=True,
            capture_output=True,
        )
        if completed.returncode:
            raise RuntimeError(
                f"worker failed for {source} ({completed.returncode})\n"
                f"{completed.stdout}{completed.stderr}"
            )
        print(completed.stdout, end="", flush=True)
        output["symbols"][source] = json.loads(
            (PARTS / f"{source}.json").read_text(encoding="utf-8")
        )
    RESULT_PATH.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passers = [
        row["ftmo_symbol"] for row in output["symbols"].values() if row["stage_a_pass"]
    ]
    print(f"STAGE_A_PASSERS {len(passers)} {','.join(passers)}")
    print(f"RESULT_FILE {RESULT_PATH}")


if __name__ == "__main__":
    main()
