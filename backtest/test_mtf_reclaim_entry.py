"""Synthetic checks for the H1-signal / lower-timeframe entry screen."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from mtf_reclaim_entry import (
    EntryResult,
    RunResult,
    _find_entry,
    _resolve_v130,
    aggregate_h1,
    summarize,
)


def bars(rows, *, minutes=15):
    frame = pd.DataFrame(rows, columns=("open", "high", "low", "close"))
    frame.insert(0, "time", pd.date_range("2026-01-01", periods=len(frame), freq=f"{minutes}min"))
    frame["volume"] = 1.0
    frame["spread_price"] = 0.2
    return frame


def assert_causal_aggregation():
    raw = bars([
        (100.0, 101.0, 99.0, 100.5),
        (100.5, 102.0, 100.0, 101.0),
        (101.0, 103.0, 100.5, 102.0),
        (102.0, 104.0, 101.5, 103.0),
        (103.0, 105.0, 102.0, 104.0),
        (104.0, 106.0, 103.0, 105.0),
        (105.0, 107.0, 104.0, 106.0),
        (106.0, 108.0, 105.0, 107.0),
    ])
    h1, starts, ends = aggregate_h1(raw, 15)
    assert len(h1) == 2
    assert tuple(starts) == (0, 4) and tuple(ends) == (3, 7)
    assert tuple(h1.iloc[0][["open", "high", "low", "close"]]) == (100.0, 104.0, 99.0, 103.0)
    assert h1.iloc[0]["volume"] == 4.0 and h1.iloc[0]["spread_price"] == 0.2

    missing = raw.drop(index=2).reset_index(drop=True)
    h1_missing, starts_missing, _ = aggregate_h1(missing, 15)
    assert len(h1_missing) == 1 and tuple(starts_missing) == (3,)


def assert_reclaim_is_directional_and_bounded():
    long_path = bars([
        (100.4, 100.5, 100.2, 100.3),  # no touch
        (100.3, 100.4, 99.8, 99.9),    # touch, closes below
        (99.9, 100.2, 99.7, 100.1),    # bullish reclaim +0.10R
    ])
    touch = _find_entry(
        long_path, side=1, level=100.0, signal_atr=1.0,
        first_bar=0, last_bar=2, mode="touch",
    )
    reclaim = _find_entry(
        long_path, side=1, level=100.0, signal_atr=1.0,
        first_bar=0, last_bar=2, mode="reclaim",
    )
    assert touch == (1, 100.0, 0.0)
    assert reclaim[0] == 2 and abs(reclaim[1] - 100.1) < 1e-12
    assert abs(reclaim[2] - 0.1) < 1e-12

    chase = long_path.copy()
    chase.loc[2, ["open", "high", "low", "close"]] = (99.9, 100.4, 99.7, 100.3)
    rejected = _find_entry(
        chase, side=1, level=100.0, signal_atr=1.0,
        first_bar=0, last_bar=2, mode="reclaim",
    )
    assert rejected[0] == -1 and math.isnan(rejected[1])

    short_path = bars([
        (99.8, 100.2, 99.7, 100.1),    # touch, closes above
        (100.1, 100.3, 99.8, 99.9),    # bearish reclaim
    ])
    short = _find_entry(
        short_path, side=-1, level=100.0, signal_atr=1.0,
        first_bar=0, last_bar=1, mode="reclaim",
    )
    assert short[0] == 1 and abs(short[2] - 0.1) < 1e-12


def assert_v130_path_order_and_cost():
    stop_first = bars([(100.0, 102.5, 98.5, 101.0)])
    exit_bar, result = _resolve_v130(stop_first, 0, 1, 100.0, 1.0, 0.02, 32)
    assert exit_bar == 0 and abs(result - (-1.04)) < 1e-12

    winner = bars([
        (100.0, 101.2, 99.8, 101.0),
        (101.0, 102.2, 100.8, 102.0),
    ])
    exit_bar, result = _resolve_v130(winner, 0, 1, 100.0, 1.0, 0.02, 32)
    assert exit_bar == 1 and abs(result - 1.46) < 1e-12


def assert_oos_denominator_is_honest():
    trades = (
        EntryResult(1, 1, 1, 2, 1, 1, 1.0, False, 0.0),
        EntryResult(2, 2, 2, 3, 2, 1, -1.0, True, 0.1),
    )
    result = RunResult(4, 1, trades)
    full = summarize(result)
    oos = summarize(result, oos_only=True)
    assert full["fills"] == 2 and full["fill_rate"] == 0.5
    assert oos["fills"] == 1 and oos["fill_rate"] == 1.0
    assert oos["expectancy"] == -1.0


def main():
    assert_causal_aggregation()
    assert_reclaim_is_directional_and_bounded()
    assert_v130_path_order_and_cost()
    assert_oos_denominator_is_honest()
    print("MTF reclaim synthetic checks: 4 passed")


if __name__ == "__main__":
    main()
