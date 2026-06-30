"""Pluggable signal generators + a single shared trade simulator.

The whole point of this file is that every candidate strategy is judged with the
*exact same* exit, fill, and cost machinery as the shipped scalper
(scalper_confluence.simulate_symbol_c). Only the ENTRY SIGNAL differs. That keeps
the comparison honest: any difference in out-of-sample expectancy is attributable
to the signal, not to a quietly-better exit.

A signal generator is a function  sig(df, **kw) -> np.ndarray  returning, for every
bar i, a side in {-1, 0, +1} computed CAUSALLY (only data <= i). The simulator then
applies entry-fill + ATR stop / TP / break-even-lock / trail / time-exit identically.

All exits are ATR-scaled, so per-trade results are in R-multiples and comparable
across instruments and price scales. Cost is a per-side fraction of ATR and always
swept (see crypto_research.py for the honest crypto cost calibration).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from scalper_backtest import wilder_atr, ema


# ---------------------------------------------------------------------------
# Execution parameters (shared by every strategy)
# ---------------------------------------------------------------------------
@dataclass
class ExecParams:
    atr_period: int = 14
    entry_style: str = "limit"        # 'market' | 'stop' | 'limit'
    entry_offset_atr: float = 0.0     # pullback (limit) / chase (stop) distance
    pending_expiry_bars: int = 3
    stop_atr: float = 1.0
    tp_atr: float = 3.0               # 0 => no fixed TP (trail/time only)
    lock_trigger_atr: float = 0.25
    trail_atr: float = 0.5
    max_hold_bars: int = 8
    cost_atr_frac: float = 0.0
    block_overlap: bool = True        # one trade per symbol at a time


# ---------------------------------------------------------------------------
# Causal indicator helpers
# ---------------------------------------------------------------------------
def rsi(c, period):
    c = np.asarray(c, float)
    d = np.diff(c, prepend=c[0])
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    ru = pd.Series(up).ewm(alpha=1.0 / period, adjust=False).mean().to_numpy()
    rd = pd.Series(dn).ewm(alpha=1.0 / period, adjust=False).mean().to_numpy()
    rs = np.divide(ru, rd, out=np.full_like(ru, np.inf), where=rd > 0)
    return 100.0 - 100.0 / (1.0 + rs)


def sma(c, period):
    return pd.Series(c, dtype=float).rolling(period).mean().to_numpy()


def rolling_std(c, period):
    return pd.Series(c, dtype=float).rolling(period).std(ddof=0).to_numpy()


def session_vwap(df):
    t = pd.to_datetime(df["time"])
    day = t.dt.floor("D")
    tp = (df["high"].astype(float) + df["low"].astype(float) + df["close"].astype(float)) / 3.0
    vol = df["volume"].astype(float) if "volume" in df else pd.Series(1.0, index=df.index)
    vol = vol.where(np.isfinite(vol) & (vol > 0), 0.0)
    cum_pv = (tp * vol).groupby(day).cumsum()
    cum_v = vol.groupby(day).cumsum().replace(0.0, np.nan)
    return (cum_pv / cum_v).to_numpy()


# ---------------------------------------------------------------------------
# Signal generators  (each returns side[-1/0/1] per bar, causal)
# ---------------------------------------------------------------------------
def sig_momentum(df, momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont"):
    """The repo's signal: a >= momentum_atr ATR move over momentum_bars, confirmed by a
    same-direction trigger candle. direction='cont' (continuation) or 'fade' (reversion)."""
    o = df["open"].to_numpy(float); c = df["close"].to_numpy(float)
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float)
    atr = wilder_atr(h, l, c, atr_period)
    n = len(c); side = np.zeros(n, np.int8)
    mb = momentum_bars
    for i in range(mb + atr_period + 1, n):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        move_atr = (c[i - (mb - 1)] - c[i]) / a
        falling = (move_atr >= momentum_atr) and (c[i] < o[i])
        rising = (-move_atr >= momentum_atr) and (c[i] > o[i])
        if not (falling or rising):
            continue
        if direction == "cont":
            side[i] = 1 if rising else -1
        else:
            side[i] = 1 if falling else -1
    return side


def sig_rsi2(df, rsi_period=2, lo=10.0, hi=90.0, trend_sma=200, atr_period=14):
    """Connors-style short-term reversion: buy oversold *in an uptrend*, sell overbought
    *in a downtrend* (trend filter = close vs SMA(trend_sma)). Classic mean-reversion."""
    c = df["close"].to_numpy(float)
    r = rsi(c, rsi_period)
    ma = sma(c, trend_sma)
    n = len(c); side = np.zeros(n, np.int8)
    for i in range(trend_sma + 1, n):
        if not np.isfinite(ma[i]):
            continue
        if r[i] < lo and c[i] > ma[i]:
            side[i] = 1
        elif r[i] > hi and c[i] < ma[i]:
            side[i] = -1
    return side


def sig_bollinger(df, bb_period=20, k=2.0, atr_period=14, mode="revert"):
    """Bollinger-band touch. mode='revert' fades the band (long below lower, short above
    upper); mode='breakout' trades the break (long above upper, short below lower)."""
    c = df["close"].to_numpy(float)
    m = sma(c, bb_period); sd = rolling_std(c, bb_period)
    upper = m + k * sd; lower = m - k * sd
    n = len(c); side = np.zeros(n, np.int8)
    for i in range(bb_period + 1, n):
        if not np.isfinite(sd[i]) or sd[i] <= 0:
            continue
        if mode == "revert":
            if c[i] < lower[i]:
                side[i] = 1
            elif c[i] > upper[i]:
                side[i] = -1
        else:
            if c[i] > upper[i]:
                side[i] = 1
            elif c[i] < lower[i]:
                side[i] = -1
    return side


def sig_donchian(df, channel=48, atr_period=14):
    """Donchian breakout (trend following): long on a new channel-bar high, short on a new
    channel-bar low. Compared against the PRIOR window so it is strictly causal."""
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    hh = pd.Series(h).rolling(channel).max().shift(1).to_numpy()
    ll = pd.Series(l).rolling(channel).min().shift(1).to_numpy()
    n = len(c); side = np.zeros(n, np.int8)
    for i in range(channel + 1, n):
        if not (np.isfinite(hh[i]) and np.isfinite(ll[i])):
            continue
        if c[i] > hh[i]:
            side[i] = 1
        elif c[i] < ll[i]:
            side[i] = -1
    return side


def sig_vwap_revert(df, stretch_atr=1.5, atr_period=14, min_bars=8):
    """Fade stretch from the session-anchored VWAP: long when price is stretch_atr ATR
    *below* VWAP, short when stretch_atr ATR *above*. Intraday mean-reversion."""
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, atr_period)
    v = session_vwap(df)
    t = pd.to_datetime(df["time"]); day = t.dt.floor("D")
    bar_pos = day.groupby(day).cumcount().to_numpy() + 1
    n = len(c); side = np.zeros(n, np.int8)
    for i in range(atr_period + 1, n):
        a = atr[i]
        if not np.isfinite(a) or a <= 0 or not np.isfinite(v[i]) or bar_pos[i] < min_bars:
            continue
        d = (c[i] - v[i]) / a
        if d <= -stretch_atr:
            side[i] = 1
        elif d >= stretch_atr:
            side[i] = -1
    return side


def sig_orb(df, atr_period=14, range_bars=4, stretch_atr=0.0):
    """Daily (00:00 UTC) opening-range breakout: after the first range_bars of a session
    set the OR high/low; long on a break above, short on a break below, once per session."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, atr_period)
    t = pd.to_datetime(df["time"]); day = t.dt.floor("D")
    bar_pos = day.groupby(day).cumcount().to_numpy()
    n = len(c); side = np.zeros(n, np.int8)
    or_hi = or_lo = np.nan; fired = False
    for i in range(n):
        if bar_pos[i] == 0:
            or_hi = or_lo = np.nan; fired = False
        if bar_pos[i] < range_bars:
            seg_hi = h[i] if not np.isfinite(or_hi) else max(or_hi, h[i])
            seg_lo = l[i] if not np.isfinite(or_lo) else min(or_lo, l[i])
            or_hi, or_lo = seg_hi, seg_lo
            continue
        if fired or not (np.isfinite(or_hi) and np.isfinite(or_lo)):
            continue
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        pad = stretch_atr * a
        if c[i] > or_hi + pad:
            side[i] = 1; fired = True
        elif c[i] < or_lo - pad:
            side[i] = -1; fired = True
    return side


# ---------------------------------------------------------------------------
# The single shared trade simulator
# ---------------------------------------------------------------------------
def simulate(df, side_arr, p: ExecParams, lo, hi, atr=None):
    """Run side_arr signals through the shared entry/exit/cost model. Returns
    (list of per-trade dicts {i, side, r, fill_lag}, counters)."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    if atr is None:
        atr = wilder_atr(h, l, c, p.atr_period)
    n = len(c)
    trades = []
    cnt = dict(signals=0, filled=0, nonfill=0)
    start = max(lo, p.atr_period + 2)
    end = min(hi, n - 1)

    i = start
    while i < end:
        side = int(side_arr[i])
        if side == 0:
            i += 1; continue
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            i += 1; continue
        cnt["signals"] += 1
        offset = p.entry_offset_atr * a
        ref = c[i]

        if p.entry_style == "market":
            entry_bar = i + 1
            if entry_bar >= n:
                i += 1; continue
            entry = o[entry_bar]
        else:
            entry = (ref + offset if side > 0 else ref - offset) if p.entry_style == "stop" \
                else (ref - offset if side > 0 else ref + offset)
            filled = False; entry_bar = -1
            for j in range(i + 1, min(i + 1 + p.pending_expiry_bars, n)):
                if p.entry_style == "stop":
                    hit = (h[j] >= entry) if side > 0 else (l[j] <= entry)
                else:
                    hit = (l[j] <= entry) if side > 0 else (h[j] >= entry)
                if hit:
                    filled = True; entry_bar = j; break
            if not filled:
                cnt["nonfill"] += 1; i += 1; continue
        cnt["filled"] += 1

        risk = p.stop_atr * a
        if side > 0:
            sl = entry - risk
            tp = entry + p.tp_atr * a if p.tp_atr > 0 else None
        else:
            sl = entry + risk
            tp = entry - p.tp_atr * a if p.tp_atr > 0 else None
        lock_trigger = p.lock_trigger_atr * a
        trail_dist = p.trail_atr * a
        cost = p.cost_atr_frac * a

        exit_price = None; exit_bar = entry_bar
        for k in range(entry_bar, min(entry_bar + p.max_hold_bars, n)):
            if side > 0:
                if l[k] <= sl: exit_price, exit_bar = sl, k; break
                if tp is not None and h[k] >= tp: exit_price, exit_bar = tp, k; break
            else:
                if h[k] >= sl: exit_price, exit_bar = sl, k; break
                if tp is not None and l[k] <= tp: exit_price, exit_bar = tp, k; break
            price = c[k]
            if side > 0:
                if (price - entry) >= lock_trigger:
                    sl = max(sl, entry, price - trail_dist)
            else:
                if (entry - price) >= lock_trigger:
                    sl = min(sl, entry, price + trail_dist)
        if exit_price is None:
            exit_bar = min(entry_bar + p.max_hold_bars - 1, n - 1)
            exit_price = c[exit_bar]

        gross = (exit_price - entry) * side
        r = (gross - 2 * cost) / risk
        trades.append(dict(i=i, side=side, r=r, fill_lag=entry_bar - i))
        i = max(exit_bar + 1, i + 1) if p.block_overlap else (i + 1)

    return trades, cnt


SIGNALS = {
    "momentum": sig_momentum,
    "rsi2": sig_rsi2,
    "bollinger": sig_bollinger,
    "donchian": sig_donchian,
    "vwap_revert": sig_vwap_revert,
    "orb": sig_orb,
}
