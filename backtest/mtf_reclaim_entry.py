"""H1-signal / lower-timeframe reclaim-entry screen.

Pre-registered in docs/MTF_RECLAIM_ENTRY_SPEC_2026-07-13.md
(SHA256 429fccd776d0c83e61a8da36eeeee22b8850a3e21592309507b0e5d43680a548).

The H1 W2 signal and H1 ATR risk unit are intentionally unchanged.  Execution
bars are used only to resolve the pullback path and, for C1, confirm a reclaim.
"""
from __future__ import annotations

import argparse
import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from parity_engine import START, prep_symbol
from walkforward_dsr import real_cost_per_side


TRIO = ("Wall_Street_30", "US_Tech_100", "Japan_225")
W2_THRESHOLD = 0.30
ENTRY_OFFSET_ATR = 0.60
MAX_RECLAIM_CHASE_ATR = 0.25
PENDING_H1_BARS = 3
HOLD_HOURS = 8


@dataclass(frozen=True)
class EntryResult:
    signal_h1: int
    signal_epoch: int
    entry_exec: int
    exit_exec: int
    exit_h1: int
    side: int
    r: float
    oos: bool
    displacement_r: float


@dataclass(frozen=True)
class RunResult:
    opportunities: int
    oos_opportunities: int
    trades: tuple[EntryResult, ...]


def normalize_ohlc(raw: pd.DataFrame) -> pd.DataFrame:
    """Return sorted canonical OHLC data with timezone-neutral UTC timestamps."""
    names = {str(col).lower(): col for col in raw.columns}
    required = ("time", "open", "high", "low", "close")
    missing = [name for name in required if name not in names]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")
    rename = {names[name]: name for name in required}
    for optional in ("volume", "spread_price", "spread"):
        if optional in names:
            rename[names[optional]] = optional
    df = raw.rename(columns=rename).copy()
    dt = pd.to_datetime(df["time"], utc=True, errors="raise")
    df["time"] = dt.dt.tz_convert(None)
    df = df.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)
    return df


def aggregate_h1(execution: pd.DataFrame, exec_minutes: int) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Aggregate complete execution-bar hours and retain source-index bounds."""
    if exec_minutes <= 0 or 60 % exec_minutes:
        raise ValueError("execution timeframe must divide one hour exactly")
    per_hour = 60 // exec_minutes
    df = normalize_ohlc(execution)
    df["_exec_index"] = np.arange(len(df), dtype=np.int64)
    df["_hour"] = df["time"].dt.floor("h")
    rows: list[dict] = []
    starts: list[int] = []
    ends: list[int] = []
    for hour, group in df.groupby("_hour", sort=True):
        group = group.sort_values("time")
        expected = [hour + pd.Timedelta(minutes=exec_minutes * k) for k in range(per_hour)]
        if len(group) != per_hour or list(group["time"]) != expected:
            continue
        row = {
            "time": hour,
            "open": float(group.iloc[0]["open"]),
            "high": float(group["high"].max()),
            "low": float(group["low"].min()),
            "close": float(group.iloc[-1]["close"]),
        }
        if "volume" in group:
            row["volume"] = float(group["volume"].sum())
        if "spread_price" in group:
            row["spread_price"] = float(group["spread_price"].max())
        elif "spread" in group:
            row["spread"] = float(group["spread"].max())
        rows.append(row)
        starts.append(int(group.iloc[0]["_exec_index"]))
        ends.append(int(group.iloc[-1]["_exec_index"]))
    if not rows:
        raise ValueError("no complete contiguous H1 groups")
    return pd.DataFrame(rows), np.asarray(starts), np.asarray(ends)


def _execution_to_h1(n_exec: int, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    mapping = np.full(n_exec, -1, dtype=np.int64)
    for h1_index, (start, end) in enumerate(zip(starts, ends)):
        mapping[start:end + 1] = h1_index
    return mapping


def _find_entry(
    execution: pd.DataFrame,
    *,
    side: int,
    level: float,
    signal_atr: float,
    first_bar: int,
    last_bar: int,
    mode: str,
) -> tuple[int, float, float]:
    """Return entry bar, price, and displacement; (-1, nan, 0) if unfilled."""
    high = execution["high"].to_numpy(float)
    low = execution["low"].to_numpy(float)
    open_ = execution["open"].to_numpy(float)
    close = execution["close"].to_numpy(float)
    touched = False
    for bar in range(first_bar, last_bar + 1):
        touch = low[bar] <= level if side > 0 else high[bar] >= level
        touched = touched or touch
        if not touched:
            continue
        if mode == "touch":
            return bar, level, 0.0
        aligned_body = side * (close[bar] - open_[bar]) > 0.0
        displacement = side * (close[bar] - level) / signal_atr
        reclaimed = displacement >= 0.0
        if aligned_body and reclaimed and displacement <= MAX_RECLAIM_CHASE_ATR:
            return bar, float(close[bar]), float(displacement)
    return -1, math.nan, 0.0


def _resolve_v130(
    execution: pd.DataFrame,
    start_bar: int,
    side: int,
    entry: float,
    signal_atr: float,
    cost_per_side_h1_atr: float,
    hold_exec_bars: int,
) -> tuple[int, float]:
    """Resolve frozen v1.30 exits on the lower-timeframe path."""
    high = execution["high"].to_numpy(float)
    low = execution["low"].to_numpy(float)
    close = execution["close"].to_numpy(float)
    stop = entry - side * signal_atr
    partial = entry + side * signal_atr
    target = entry + side * 2.0 * signal_atr
    banked = 0.0
    remaining = 1.0
    partial_done = False
    end = min(start_bar + hold_exec_bars, len(execution))
    for bar in range(start_bar, end):
        if (side > 0 and low[bar] <= stop) or (side < 0 and high[bar] >= stop):
            gross_r = banked + remaining * side * (stop - entry) / signal_atr
            return bar, gross_r - 2.0 * cost_per_side_h1_atr
        if not partial_done and (
            (side > 0 and high[bar] >= partial) or (side < 0 and low[bar] <= partial)
        ):
            banked += 0.5
            remaining = 0.5
            partial_done = True
        if (side > 0 and high[bar] >= target) or (side < 0 and low[bar] <= target):
            gross_r = banked + remaining * side * (target - entry) / signal_atr
            return bar, gross_r - 2.0 * cost_per_side_h1_atr
    exit_bar = max(start_bar, end - 1)
    gross_r = banked + remaining * side * (close[exit_bar] - entry) / signal_atr
    return exit_bar, gross_r - 2.0 * cost_per_side_h1_atr


def run_symbol(
    raw: pd.DataFrame,
    symbol: str,
    *,
    mode: str,
    exec_minutes: int = 15,
    cost_mult: float = 1.0,
) -> RunResult:
    """Run C0_TOUCH or C1_RECLAIM with causal one-symbol enumeration."""
    if mode not in {"touch", "reclaim"}:
        raise ValueError("mode must be 'touch' or 'reclaim'")
    execution = normalize_ohlc(raw)
    h1, starts, ends = aggregate_h1(execution, exec_minutes)
    base_cost = real_cost_per_side(h1)
    if not np.isfinite(base_cost):
        raise ValueError(f"{symbol}: spread cost unavailable")
    signal = prep_symbol(h1, base_cost * cost_mult, symbol)
    split = int(len(h1) * 0.70)
    exec_to_h1 = _execution_to_h1(len(execution), starts, ends)
    hold_bars = HOLD_HOURS * 60 // exec_minutes
    trades: list[EntryResult] = []
    opportunities = 0
    oos_opportunities = 0
    i = START
    while i < len(h1) - 1:
        side = int(signal.side[i])
        if side == 0 or not np.isfinite(signal.watr[i]) or signal.watr[i] < W2_THRESHOLD:
            i += 1
            continue
        opportunities += 1
        if i >= split:
            oos_opportunities += 1
        atr = float(signal.atr[i])
        level = float(signal.c[i] - side * ENTRY_OFFSET_ATR * atr)
        last_h1 = min(i + PENDING_H1_BARS, len(h1) - 1)
        first_exec = int(starts[i + 1])
        last_exec = int(ends[last_h1])
        entry_bar, entry, displacement = _find_entry(
            execution,
            side=side,
            level=level,
            signal_atr=atr,
            first_bar=first_exec,
            last_bar=last_exec,
            mode=mode,
        )
        if entry_bar < 0:
            i += PENDING_H1_BARS + 1
            continue

        # A reclaim is known only at its candle close, so its range cannot also
        # stop or profit the newly opened position. Touch-control enters intrabar.
        resolve_start = entry_bar if mode == "touch" else entry_bar + 1
        if resolve_start >= len(execution):
            break
        exit_exec, result_r = _resolve_v130(
            execution, resolve_start, side, entry, atr, signal.cost, hold_bars
        )
        exit_h1 = int(exec_to_h1[exit_exec])
        if exit_h1 < 0:
            exit_h1 = int(np.searchsorted(starts, exit_exec, side="right") - 1)
        trades.append(
            EntryResult(
                signal_h1=i,
                signal_epoch=int(signal.ep[i]),
                entry_exec=entry_bar,
                exit_exec=exit_exec,
                exit_h1=exit_h1,
                side=side,
                r=float(result_r),
                oos=i >= split,
                displacement_r=float(displacement if mode == "reclaim" else 0.0),
            )
        )
        i = max(i + 1, exit_h1 + 1)
    return RunResult(opportunities, oos_opportunities, tuple(trades))


def summarize(result: RunResult, *, oos_only: bool = False) -> dict[str, float | int]:
    trades = [trade for trade in result.trades if trade.oos or not oos_only]
    opportunities = result.oos_opportunities if oos_only else result.opportunities
    values = np.asarray([trade.r for trade in trades], dtype=float)
    displacement = np.asarray([trade.displacement_r for trade in trades], dtype=float)
    wins = values[values > 0.0]
    losses = values[values < 0.0]
    return {
        "opportunities": opportunities,
        "fills": len(trades),
        "fill_rate": len(trades) / opportunities if opportunities else math.nan,
        "expectancy": float(values.mean()) if len(values) else math.nan,
        "win_rate": float((values > 0.0).mean()) if len(values) else math.nan,
        "profit_factor": (
            float(wins.sum() / -losses.sum()) if len(losses) and -losses.sum() > 0.0 else math.nan
        ),
        "median_displacement_r": float(np.median(displacement)) if len(displacement) else math.nan,
    }


def _pooled(results: list[RunResult]) -> RunResult:
    return RunResult(
        sum(result.opportunities for result in results),
        sum(result.oos_opportunities for result in results),
        tuple(trade for result in results for trade in result.trades),
    )


def _print_summary(label: str, result: RunResult) -> None:
    print(label, {"full": summarize(result), "oos": summarize(result, oos_only=True)})


def main() -> int:
    parser = argparse.ArgumentParser()
    default_data = Path(__file__).resolve().parent / "data" / "derivM15_spreadgated"
    parser.add_argument("--data-dir", type=Path, default=default_data)
    parser.add_argument("--exec-minutes", type=int, choices=(5, 15), default=15)
    args = parser.parse_args()
    files = sorted(args.data_dir.glob("*.csv"))
    if not files:
        parser.error(f"no CSV files in {args.data_dir}")

    by_name = {path.stem: path for path in files}
    missing_trio = [symbol for symbol in TRIO if symbol not in by_name]
    if missing_trio:
        parser.error(f"primary trio missing: {', '.join(missing_trio)}")

    for cost_mult in (1.0, 2.0):
        print(f"\nCOST x{cost_mult:.0f}")
        all_results: dict[str, dict[str, RunResult]] = {"touch": {}, "reclaim": {}}
        for symbol, path in by_name.items():
            raw = pd.read_csv(path)
            for mode in ("touch", "reclaim"):
                result = run_symbol(
                    raw, symbol, mode=mode, exec_minutes=args.exec_minutes, cost_mult=cost_mult
                )
                all_results[mode][symbol] = result
                _print_summary(f"{symbol} C0_TOUCH" if mode == "touch" else f"{symbol} C1_RECLAIM", result)
        for mode, label in (("touch", "C0_TOUCH"), ("reclaim", "C1_RECLAIM")):
            trio = _pooled([all_results[mode][symbol] for symbol in TRIO])
            breadth = _pooled(list(all_results[mode].values()))
            _print_summary(f"TRIO {label}", trio)
            _print_summary(f"BREADTH {label}", breadth)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
