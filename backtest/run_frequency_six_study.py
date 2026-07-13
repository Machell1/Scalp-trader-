"""Run the preregistered M30 six-fill frequency screen.

Protocol: docs/FREQUENCY_SIX_SPEC_2026-07-13.md
SHA256: 5748232e24bd8d78bb4349704a4ac9ab7f4c80d4e35a75902146103a1acb22fe
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from build_h1_universe_tape import CLUSTERS
from parity_engine import ExecutionPlan, START, prep_symbol, run_live
from run_h1_universe_screen import META_PATH, source_path
from scalper_backtest import wilder_atr
from snapshot_h1_universe_meta import SOURCE_TO_FTMO
from walkforward_dsr import real_cost_per_side


HERE = Path(__file__).resolve().parent
RESULT_PATH = HERE / "frequency_six_results.json"
PRAGUE = ZoneInfo("Europe/Prague")
BAR_SECONDS = 1800
CAPS = {"global": 2, "cluster": 1, "fills_day": 8, "consec": 4}
LIVE_FIRST = ("US30.cash", "US100.cash", "JP225.cash", "USDJPY")
SEED = 13020260713


@dataclass(frozen=True)
class Loaded:
    source: str
    ftmo_symbol: str
    frame: pd.DataFrame
    cost_e1: float
    cluster: int


def aggregate_m30(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    frame["_dt"] = pd.to_datetime(frame["time"])
    if getattr(frame["_dt"].dt, "tz", None) is not None:
        frame["_dt"] = frame["_dt"].dt.tz_convert("UTC").dt.tz_localize(None)
    frame = frame.sort_values("_dt")
    frame["_half"] = frame["_dt"].dt.floor("30min")
    frame["_offset"] = (
        frame["_dt"] - frame["_half"]
    ).dt.total_seconds().astype(int)
    grouped = frame.groupby("_half", sort=True)
    checks = grouped["_offset"].agg(["count", "nunique", "min", "max", "sum"])
    valid = checks.index[
        (checks["count"] == 2)
        & (checks["nunique"] == 2)
        & (checks["min"] == 0)
        & (checks["max"] == 900)
        & (checks["sum"] == 900)
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


def aggregate_regression() -> None:
    raw = pd.read_csv(source_path("Wall_Street_30"), nrows=1200)
    fast = aggregate_m30(raw)
    rows = []
    raw["_dt"] = pd.to_datetime(raw["time"])
    raw["_half"] = raw["_dt"].dt.floor("30min")
    for half, group in raw.groupby("_half", sort=True):
        group = group.sort_values("_dt")
        expected = [half, half + pd.Timedelta(minutes=15)]
        if len(group) != 2 or list(group["_dt"]) != expected:
            continue
        rows.append({
            "time": half,
            "open": float(group.iloc[0]["open"]),
            "high": float(group["high"].max()),
            "low": float(group["low"].min()),
            "close": float(group.iloc[-1]["close"]),
            "volume": float(group["volume"].sum()),
            "spread_price": float(group["spread_price"].max()),
        })
    slow = pd.DataFrame(rows)
    pd.testing.assert_frame_equal(fast, slow, check_dtype=False)
    print(f"AGGREGATION_REGRESSION PASS rows={len(fast)}", flush=True)


def median_atr(frame: pd.DataFrame) -> float:
    atr = wilder_atr(
        frame["high"].to_numpy(float),
        frame["low"].to_numpy(float),
        frame["close"].to_numpy(float),
        14,
    )
    value = float(np.nanmedian(atr))
    if not math.isfinite(value) or value <= 0:
        raise ValueError("invalid M30 median ATR")
    return value


def load_all() -> dict[str, Loaded]:
    snapshot = json.loads(META_PATH.read_text(encoding="utf-8"))
    cluster_ids = {name: i for i, name in enumerate(sorted(set(CLUSTERS.values())))}
    output = {}
    for source, ftmo_symbol in SOURCE_TO_FTMO.items():
        raw = pd.read_csv(source_path(source))
        has_spread = "spread_price" in raw.columns
        if not has_spread:
            raw["spread_price"] = 0.0
        frame = aggregate_m30(raw)
        med_atr = median_atr(frame)
        broker = snapshot["symbols"][source]
        source_spread = float(real_cost_per_side(frame)) if has_spread else 0.03
        broker_spread = (
            0.5 * float(broker["spread_points"]) * float(broker["point"]) / med_atr
        )
        commission = broker["commission"]
        if commission["kind"] == "zero":
            commission_atr = 0.0
        elif commission["kind"] == "notional_fraction":
            commission_atr = (
                float(commission["per_side_fraction"])
                * float(np.nanmedian(frame["close"].to_numpy(float)))
                / med_atr
            )
        elif commission["kind"] == "usd_per_lot":
            commission_price = (
                float(commission["per_side_usd_per_lot"])
                * float(broker["trade_tick_size"])
                / float(broker["trade_tick_value_loss"])
            )
            commission_atr = commission_price / med_atr
        else:
            raise ValueError(f"unknown commission rule {commission}")
        output[source] = Loaded(
            source=source,
            ftmo_symbol=ftmo_symbol,
            frame=frame,
            cost_e1=max(source_spread, broker_spread) + commission_atr,
            cluster=cluster_ids[CLUSTERS[ftmo_symbol]],
        )
    return output


def prague_day(epoch: int):
    return datetime.fromtimestamp(int(epoch), timezone.utc).astimezone(PRAGUE).date()


class M30Execution:
    def __init__(self, entry_style: str):
        self.entry_style = entry_style

    def find_fill(self, s, side, entry, w_start, w_end):
        if self.entry_style == "market":
            return int(w_start) if w_start < len(s.c) else -1
        for bar in range(w_start, min(w_end + 1, len(s.c))):
            if (side > 0 and s.l[bar] <= entry) or (side < 0 and s.h[bar] >= entry):
                return int(bar)
        return -1

    def resolve(self, s, sig_i, entry_bar, side, entry, atr_sig):
        stop = entry - atr_sig * side
        target = entry + 2.0 * atr_sig * side
        partial_price = entry + atr_sig * side
        partial = False
        banked = 0.0
        fraction = 1.0
        cost_r = 2.0 * float(s.cost)
        exit_bar = min(entry_bar + 7, len(s.c) - 1)
        exit_price = float(s.c[exit_bar])
        reason = "TIME"
        for bar in range(entry_bar, min(entry_bar + 8, len(s.c))):
            if side > 0:
                if s.l[bar] <= stop:
                    exit_bar, exit_price, reason = bar, stop, "SL"
                    break
                if not partial and s.h[bar] >= partial_price:
                    partial, banked, fraction = True, 0.5, 0.5
                if s.h[bar] >= target:
                    exit_bar, exit_price, reason = bar, target, "TP"
                    break
            else:
                if s.h[bar] >= stop:
                    exit_bar, exit_price, reason = bar, stop, "SL"
                    break
                if not partial and s.l[bar] <= partial_price:
                    partial, banked, fraction = True, 0.5, 0.5
                if s.l[bar] <= target:
                    exit_bar, exit_price, reason = bar, target, "TP"
                    break
        total_r = banked + fraction * (exit_price - entry) * side / atr_sig - cost_r
        if reason == "TIME" and exit_bar + 1 < len(s.c):
            free_epoch = int(s.ep[exit_bar + 1])
        else:
            free_epoch = int(s.ep[exit_bar]) + BAR_SECONDS
        return ExecutionPlan(
            exit_bar=int(exit_bar),
            exit_price=float(exit_price),
            reason=reason,
            total_r=float(total_r),
            free_epoch=int(free_epoch),
        )


def prepared(loaded: Loaded, cost_multiplier: float):
    s = prep_symbol(
        loaded.frame,
        loaded.cost_e1 * cost_multiplier,
        loaded.ftmo_symbol,
        loaded.cluster,
    )
    return s


def replay(symbols, entry_style: str, caps=CAPS):
    return run_live(
        symbols,
        thr={s.name: 0.30 for s in symbols},
        caps=caps,
        window=3,
        execution=M30Execution(entry_style),
        day_key=prague_day,
        entry_style=entry_style,
        bar_seconds=BAR_SECONDS,
    )


def basic_stats(trades) -> dict:
    values = np.asarray([t.r for t in trades], dtype=float)
    positive = values[values > 0]
    negative = values[values < 0]
    return {
        "n": int(len(values)),
        "expectancy": float(values.mean()) if len(values) else None,
        "win_rate": float((values > 0).mean()) if len(values) else None,
        "profit_factor": (
            float(positive.sum() / -negative.sum()) if len(negative) else None
        ),
        "average_hold_bars": (
            float(np.mean([t.exit_bar - t.entry_bar + 1 for t in trades]))
            if trades else None
        ),
    }


def split_stats(trades, cut50: int, cut70: int) -> tuple[dict, dict]:
    calibration = [t for t in trades if t.ep_sig < cut50]
    confirmation = [t for t in trades if cut50 <= t.ep_sig < cut70]
    return basic_stats(calibration), basic_stats(confirmation)


def positive_quarter_fraction(trades, end_epoch: int) -> tuple[int, int, float | None]:
    rows = [t for t in trades if t.ep_sig < end_epoch]
    grouped: dict[str, list[float]] = {}
    for trade in rows:
        quarter = str(pd.Timestamp(trade.ep_sig, unit="s").to_period("Q"))
        grouped.setdefault(quarter, []).append(float(trade.r))
    quarters = [(key, float(np.mean(values))) for key, values in sorted(grouped.items())]
    complete = quarters[1:-1] if len(quarters) >= 3 else quarters
    positive = sum(value > 0 for _, value in complete)
    fraction = positive / len(complete) if complete else None
    return positive, len(complete), fraction


def order_sources(selected: list[str], loaded: dict[str, Loaded]) -> list[str]:
    rank = {symbol: i for i, symbol in enumerate(LIVE_FIRST)}
    return sorted(
        selected,
        key=lambda source: (
            rank.get(loaded[source].ftmo_symbol, len(rank)),
            loaded[source].ftmo_symbol if loaded[source].ftmo_symbol not in rank else "",
        ),
    )


def common_oos_bounds(selected: list[str], loaded: dict[str, Loaded]) -> tuple[int, int]:
    starts = []
    ends = []
    for source in selected:
        frame = loaded[source].frame
        starts.append(int(pd.Timestamp(frame.iloc[int(len(frame) * 0.7)]["time"]).timestamp()))
        ends.append(int(pd.Timestamp(frame.iloc[-1]["time"]).timestamp()) + BAR_SECONDS)
    start, end = max(starts), min(ends)
    if start >= end:
        raise ValueError("selected symbols have no common final-OOS interval")
    return start, end


def filter_oos(trades, start: int, end: int):
    return [t for t in trades if start <= t.ep_sig < end]


def eligible_days(start: int, end: int):
    first = prague_day(start)
    last = prague_day(end - 1)
    return [d.date() for d in pd.date_range(first, last, freq="D") if d.weekday() < 5]


def frequency_stats(trades, days: list) -> dict:
    counts = {day: 0 for day in days}
    for trade in trades:
        day = prague_day(trade_entry_epoch[id(trade)])
        if day in counts:
            counts[day] += 1
    values = np.asarray(list(counts.values()), dtype=float)
    return {
        "eligible_days": int(len(values)),
        "mean_fills_per_day": float(values.mean()),
        "median": float(np.median(values)),
        "p10": float(np.quantile(values, 0.10)),
        "p90": float(np.quantile(values, 0.90)),
        "maximum": int(values.max()),
        "zero_fill_days": int((values == 0).sum()),
        "days_ge_6_fraction": float((values >= 6).mean()),
        "daily_counts": [int(value) for value in values],
    }


def pooled_quarters(trades) -> dict:
    grouped: dict[str, list[float]] = {}
    for trade in trades:
        key = str(pd.Timestamp(trade.ep_sig, unit="s").to_period("Q"))
        grouped.setdefault(key, []).append(float(trade.r))
    rows = [
        {"quarter": key, "n": len(values), "expectancy": float(np.mean(values))}
        for key, values in sorted(grouped.items())
    ]
    complete = rows[1:-1] if len(rows) >= 3 else rows
    positive = sum(row["expectancy"] > 0 for row in complete)
    return {
        "rows": rows,
        "complete_n": len(complete),
        "positive_n": positive,
        "positive_fraction": positive / len(complete) if complete else None,
    }


def symbol_expectancies(trades, selected: list[str], loaded: dict[str, Loaded]) -> dict:
    output = {}
    for source in selected:
        symbol = loaded[source].ftmo_symbol
        rows = [trade for trade in trades if trade.sym == symbol]
        output[symbol] = basic_stats(rows)
    return output


def bootstrap_lower(trades, days: list, draws: int = 10_000) -> float | None:
    if not trades or not days:
        return None
    index = {day: i for i, day in enumerate(days)}
    counts = np.zeros(len(days), dtype=np.int64)
    sums = np.zeros(len(days), dtype=float)
    for trade in trades:
        day = prague_day(trade_entry_epoch[id(trade)])
        if day in index:
            counts[index[day]] += 1
            sums[index[day]] += trade.r
    rng = np.random.default_rng(SEED)
    estimates = np.empty(draws, dtype=float)
    probability = 1.0 / 20.0
    n = len(days)
    for draw in range(draws):
        sampled = np.empty(n, dtype=np.int64)
        sampled[0] = rng.integers(n)
        restart = rng.random(n - 1) < probability
        random_starts = rng.integers(n, size=n - 1)
        for j in range(1, n):
            sampled[j] = random_starts[j - 1] if restart[j - 1] else (sampled[j - 1] + 1) % n
        denominator = int(counts[sampled].sum())
        estimates[draw] = sums[sampled].sum() / denominator if denominator else np.nan
    finite = estimates[np.isfinite(estimates)]
    return float(np.quantile(finite, 0.05)) if len(finite) else None


# Populated for each coupled replay so frequency and bootstrap use actual fill bars.
trade_entry_epoch: dict[int, int] = {}


def coupled_cell(cell: str, entry_style: str, selected: list[str], loaded: dict[str, Loaded]):
    ordered = order_sources(selected, loaded)
    start, end = common_oos_bounds(ordered, loaded)
    modes = {}
    global trade_entry_epoch
    for mode, multiplier in (("E1_MEASURED", 1.0), ("E2_STRESS", 2.0)):
        symbols = [prepared(loaded[source], multiplier) for source in ordered]
        trades, census = replay(symbols, entry_style)
        lookup = {s.name: s for s in symbols}
        trade_entry_epoch = {
            id(trade): int(lookup[trade.sym].ep[trade.entry_bar]) for trade in trades
        }
        oos = filter_oos(trades, start, end)
        days = eligible_days(start, end)
        stats = basic_stats(oos)
        stats["symbols"] = symbol_expectancies(oos, ordered, loaded)
        stats["quarters"] = pooled_quarters(oos)
        stats["bootstrap_lower_95_one_sided"] = bootstrap_lower(oos, days)
        stats["frequency"] = frequency_stats(oos, days)
        stats["census"] = vars(census)
        modes[mode] = stats
    e1 = modes["E1_MEASURED"]
    e2 = modes["E2_STRESS"]
    positive_symbols = sum(
        row["expectancy"] is not None and row["expectancy"] > 0
        for row in e2["symbols"].values()
    )
    symbol_fraction = positive_symbols / len(ordered)
    failures = []
    if e2["frequency"]["mean_fills_per_day"] < 6.0:
        failures.append("FREQUENCY_LT_6")
    if e2["expectancy"] is None or e2["expectancy"] <= 0:
        failures.append("E2_EXPECTANCY_NONPOSITIVE")
    if (
        e2["bootstrap_lower_95_one_sided"] is None
        or e2["bootstrap_lower_95_one_sided"] <= 0
    ):
        failures.append("E2_BOOTSTRAP_LOWER_NONPOSITIVE")
    if symbol_fraction < 0.60:
        failures.append("E2_POSITIVE_SYMBOLS_LT_60PCT")
    quarter_fraction = e2["quarters"]["positive_fraction"]
    if quarter_fraction is None or quarter_fraction < 0.60:
        failures.append("E2_POSITIVE_QUARTERS_LT_60PCT")
    if e1["expectancy"] is None or e1["expectancy"] <= 0:
        failures.append("E1_EXPECTANCY_NONPOSITIVE")
    return {
        "cell": cell,
        "entry_style": entry_style,
        "selected_sources": ordered,
        "selected_symbols": [loaded[source].ftmo_symbol for source in ordered],
        "oos_start_epoch": start,
        "oos_end_epoch": end,
        "positive_symbol_fraction_e2": symbol_fraction,
        "modes": modes,
        "failures": failures,
        "screen_pass": not failures,
        "account_mc": "REQUIRED_NOT_RUN" if not failures else "NOT_ELIGIBLE",
    }


def main() -> None:
    aggregate_regression()
    loaded = load_all()
    print(f"LOADED {len(loaded)} FTMO twins", flush=True)
    output = {
        "protocol_sha256": "5748232e24bd8d78bb4349704a4ac9ab7f4c80d4e35a75902146103a1acb22fe",
        "cells": {},
    }
    for cell, entry_style in (("P30", "limit"), ("M30", "market")):
        selection = {}
        selected = []
        for source in order_sources(list(loaded), loaded):
            item = loaded[source]
            s = prepared(item, 2.0)
            trades, _ = replay(
                [s], entry_style,
                caps={"global": 1, "cluster": 1, "fills_day": 8, "consec": 4},
            )
            cut50 = int(s.ep[int(len(s.ep) * 0.5)])
            cut70 = int(s.ep[int(len(s.ep) * 0.7)])
            calibration, confirmation = split_stats(trades, cut50, cut70)
            q_pos, q_n, q_fraction = positive_quarter_fraction(trades, cut70)
            passed = bool(
                calibration["n"] >= 50
                and calibration["expectancy"] is not None
                and calibration["expectancy"] > 0
                and confirmation["n"] >= 20
                and confirmation["expectancy"] is not None
                and confirmation["expectancy"] > 0
                and q_fraction is not None
                and q_fraction >= 0.50
            )
            selection[item.ftmo_symbol] = {
                "source": source,
                "cost_e2_per_side_atr": item.cost_e1 * 2.0,
                "calibration": calibration,
                "confirmation": confirmation,
                "positive_quarters": q_pos,
                "complete_quarters": q_n,
                "positive_quarter_fraction": q_fraction,
                "selected": passed,
            }
            if passed:
                selected.append(source)
            print(
                f"{cell} {item.ftmo_symbol} {'SELECT' if passed else 'REJECT'} "
                f"cal_n={calibration['n']} cal_exp={calibration['expectancy']} "
                f"conf_n={confirmation['n']} conf_exp={confirmation['expectancy']} "
                f"q={q_pos}/{q_n}",
                flush=True,
            )
        print(f"{cell} SELECTED {len(selected)}", flush=True)
        if selected:
            coupled = coupled_cell(cell, entry_style, selected, loaded)
        else:
            coupled = {
                "cell": cell,
                "entry_style": entry_style,
                "selected_sources": [],
                "selected_symbols": [],
                "failures": ["EMPTY_SELECTION"],
                "screen_pass": False,
                "account_mc": "NOT_ELIGIBLE",
            }
        output["cells"][cell] = {"selection": selection, "coupled": coupled}
        print(
            f"{cell} VERDICT {'PASS' if coupled['screen_pass'] else 'FAIL'} "
            f"{','.join(coupled['failures']) if coupled['failures'] else 'none'}",
            flush=True,
        )
    RESULT_PATH.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RESULT_FILE {RESULT_PATH}", flush=True)


if __name__ == "__main__":
    main()
