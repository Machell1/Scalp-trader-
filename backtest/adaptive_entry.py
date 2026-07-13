"""Research mirror for MomentumPullbackEA v1.32's lower-timeframe entry.

The live H1 path is intentionally untouched.  This module makes the optional
M5/M15 geometry testable without pretending that unvalidated parameters are an
edge: lower bars refine the candle trigger, while the H1 lookback, ATR risk
ruler, pending lifetime, and maximum hold retain their original clock.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from scalper_backtest import wilder_atr


@dataclass(frozen=True)
class AdaptiveGeometry:
    momentum_shift: int
    pending_bars: int
    holding_bars: int


def scale_bars(reference_bars: int, work_seconds: int, reference_seconds: int) -> int:
    """Scale a bar duration upward, matching the EA's integer ceiling."""
    if reference_bars <= 0 or reference_seconds <= work_seconds:
        return reference_bars
    return (reference_bars * reference_seconds + work_seconds - 1) // work_seconds


def adaptive_geometry(
    work_seconds: int,
    reference_seconds: int = 3600,
    momentum_shift: int = 6,
    pending_bars: int = 3,
    holding_bars: int = 8,
) -> AdaptiveGeometry:
    if work_seconds <= 0 or reference_seconds <= 0:
        raise ValueError("timeframe seconds must be positive")
    if reference_seconds <= work_seconds:
        return AdaptiveGeometry(momentum_shift, pending_bars, holding_bars)
    # The EA compares shifts 1 and N, so momentum spans N-1 intervals.
    momentum = 1 + scale_bars(
        momentum_shift - 1, work_seconds, reference_seconds
    )
    return AdaptiveGeometry(
        momentum,
        scale_bars(pending_bars, work_seconds, reference_seconds),
        scale_bars(holding_bars, work_seconds, reference_seconds),
    )


def _normalise_ohlc(frame: pd.DataFrame) -> pd.DataFrame:
    names = {str(col).lower(): col for col in frame.columns}
    required = ("time", "open", "high", "low", "close")
    missing = [name for name in required if name not in names]
    if missing:
        raise ValueError(f"missing OHLC columns: {', '.join(missing)}")
    out = frame.rename(columns={names[name]: name for name in required}).copy()
    out["time"] = pd.to_datetime(out["time"], utc=True)
    out = out.sort_values("time").reset_index(drop=True)
    return out


def adaptive_signal_frame(
    work: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    work_seconds: int,
    reference_seconds: int = 3600,
    atr_period: int = 14,
    momentum_shift: int = 6,
    momentum_atr: float = 2.0,
    wick_atr: float = 0.30,
    max_spread_atr_side: float | None = None,
) -> pd.DataFrame:
    """Return causal M5/M15 signal diagnostics.

    Reference ATR becomes visible only at the reference bar's close.  A lower
    bar can therefore never consume a still-forming H1 range.  ``signal_atr``
    is the H1 risk/cost ruler; ``local_atr`` is used only for the local W2 wick.
    """
    if reference_seconds <= work_seconds:
        raise ValueError("adaptive signals require a slower reference timeframe")

    w = _normalise_ohlc(work)
    r = _normalise_ohlc(reference)
    geom = adaptive_geometry(
        work_seconds, reference_seconds, momentum_shift=momentum_shift
    )

    w["local_atr"] = wilder_atr(
        w["high"].to_numpy(float),
        w["low"].to_numpy(float),
        w["close"].to_numpy(float),
        atr_period,
    )
    r_atr = wilder_atr(
        r["high"].to_numpy(float),
        r["low"].to_numpy(float),
        r["close"].to_numpy(float),
        atr_period,
    )
    available = pd.DataFrame(
        {
            "_available": r["time"] + pd.to_timedelta(reference_seconds, unit="s"),
            "signal_atr": r_atr,
        }
    ).sort_values("_available")
    w["_decision"] = w["time"] + pd.to_timedelta(work_seconds, unit="s")
    w = pd.merge_asof(
        w.sort_values("_decision"),
        available,
        left_on="_decision",
        right_on="_available",
        direction="backward",
        allow_exact_matches=True,
    )

    intervals = geom.momentum_shift - 1
    move = w["close"] - w["close"].shift(intervals)
    impulse = move / w["signal_atr"]
    bullish = (impulse >= momentum_atr) & (w["close"] > w["open"])
    bearish = (impulse <= -momentum_atr) & (w["close"] < w["open"])
    side = np.select([bullish, bearish], [1, -1], default=0).astype(np.int8)

    upper = w["high"] - np.maximum(w["open"], w["close"])
    lower = np.minimum(w["open"], w["close"]) - w["low"]
    adverse = np.where(side > 0, upper, np.where(side < 0, lower, np.nan))
    w["adverse_wick_atr"] = adverse / w["local_atr"]
    valid = (
        (side != 0)
        & np.isfinite(w["signal_atr"])
        & np.isfinite(w["local_atr"])
        & (w["adverse_wick_atr"] >= wick_atr)
    )

    if max_spread_atr_side is not None:
        if "spread_price" not in w:
            raise ValueError("spread_price is required when applying the cost gate")
        w["spread_atr_side"] = 0.5 * w["spread_price"] / w["signal_atr"]
        valid &= w["spread_atr_side"] <= max_spread_atr_side

    w["impulse_atr"] = impulse
    w["side"] = np.where(valid, side, 0).astype(np.int8)
    w["momentum_shift"] = geom.momentum_shift
    return w.drop(columns=["_decision", "_available"])
