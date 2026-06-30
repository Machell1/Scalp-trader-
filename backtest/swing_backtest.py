"""Multi-family swing-strategy backtest engine for the TradingView-sourced
diverse basket (Daily / H4). See EDGE_SEARCH_PLAN.md for the rationale.

Design mirrors scalper_backtest.py / scalper_confluence.py on purpose so the
results are directly comparable and judged by the identical statistical gate
(swing_experiment.py is the Daily/H4 analogue of experiment.py):
  * Real data only (backtest/fetch_tradingview.py).
  * Trades are scored in R-multiples (risk-normalised) so results are
    instrument-agnostic.
  * Cost is a per-side fraction of ATR, always swept (0 / 0.02 / 0.04).
  * One trade at a time per symbol (block_overlap), causal indicators only.
  * Entries fill at the NEXT bar's open after a signal (no same-bar lookahead).

Five independent strategy families (F1-F5), selectable via `family`:
  donchian     - N-bar breakout + ATR chandelier trail, no fixed TP (trend)
  ema_pullback - EMA(fast)>EMA(slow) trend filter + RSI dip-and-recover entry
  squeeze      - Bollinger-width-percentile squeeze + band breakout
  rsi2         - RSI(2) mean reversion (Connors-style), fixed RSI-cross exit
  random       - negative control: random entries, same exit machinery as F1
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


@dataclass
class SParams:
    family: str = "donchian"  # donchian | ema_pullback | squeeze | rsi2 | random
    atr_period: int = 14
    stop_atr: float = 2.0
    trail_atr: float = 3.0
    use_trail: bool = True
    tp_atr: float = 0.0           # 0 => no fixed TP
    max_hold_bars: int = 100
    cost_atr_frac: float = 0.0
    long_only: bool = False
    short_only: bool = False
    # F1 donchian breakout
    don_entry_n: int = 20
    use_don_exit: bool = False
    don_exit_n: int = 10
    # F2 ema pullback
    ema_fast: int = 20
    ema_slow: int = 100
    rsi_period: int = 14
    pullback_th: float = 50.0
    # F3 squeeze breakout
    bb_period: int = 20
    bb_k: float = 2.0
    bb_width_pct_max: float = 0.2
    bb_rank_win: int = 500
    breakout_buffer_atr: float = 0.1
    # F4 rsi2 mean reversion
    rsi2_period: int = 2
    rsi_entry_long: float = 10.0
    rsi_entry_short: float = 90.0
    rsi_exit_mid: float = 50.0
    trend_filter_sma: int = 0     # 0 off; >0 => only long above / short below this SMA
    # F5 random control
    random_seed: int = 0
    random_p: float = 0.04


# ---------------------------------------------------------------------------
# Indicators (causal: value at bar i uses only bars <= i)
# ---------------------------------------------------------------------------
def wilder_atr(high, low, close, period):
    prev_close = np.empty_like(close)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = np.full_like(close, np.nan)
    if len(close) <= period:
        return atr
    atr[period] = tr[1: period + 1].mean()
    alpha = 1.0 / period
    for i in range(period + 1, len(close)):
        atr[i] = atr[i - 1] + alpha * (tr[i] - atr[i - 1])
    return atr


def ema(values, period):
    out = np.full_like(values, np.nan, dtype=float)
    if period <= 0 or len(values) == 0:
        return out
    k = 2.0 / (period + 1.0)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(close, period):
    s = pd.Series(close)
    delta = s.diff()
    up = delta.clip(lower=0.0)
    dn = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    roll_dn = dn.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = roll_up / roll_dn.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    return out.to_numpy()


def donchian(high, low, n):
    h = pd.Series(high).rolling(n).max().shift(1).to_numpy()
    l = pd.Series(low).rolling(n).min().shift(1).to_numpy()
    return h, l


def bollinger_width_pct(close, period, k, rank_win):
    s = pd.Series(close)
    mid = s.rolling(period).mean()
    sd = s.rolling(period).std()
    upper = mid + k * sd
    lower = mid - k * sd
    width = (upper - lower) / mid.replace(0.0, np.nan)
    pct = width.rolling(rank_win, min_periods=max(50, period * 2)).rank(pct=True)
    return upper.to_numpy(), lower.to_numpy(), pct.to_numpy()


# ---------------------------------------------------------------------------
# Signal generation per family -> list of (signal_bar_index, side)
# Side resolved from regime/cross-conditions; entry fills next bar's open.
# ---------------------------------------------------------------------------
def signals_donchian(df, p, ind):
    c = df["close"].to_numpy(float)
    dh, dl = ind["don_hi"], ind["don_lo"]
    sig = []
    for i in range(len(c)):
        if not (np.isfinite(dh[i]) and np.isfinite(dl[i])):
            continue
        if c[i] > dh[i]:
            sig.append((i, 1))
        elif c[i] < dl[i]:
            sig.append((i, -1))
    return sig


def signals_ema_pullback(df, p, ind):
    c = df["close"].to_numpy(float)
    ef, es, r = ind["ema_fast"], ind["ema_slow"], ind["rsi"]
    sig = []
    for i in range(1, len(c)):
        if not (np.isfinite(ef[i]) and np.isfinite(es[i]) and np.isfinite(r[i]) and np.isfinite(r[i - 1])):
            continue
        up = ef[i] > es[i]
        dn = ef[i] < es[i]
        if up and r[i - 1] < p.pullback_th <= r[i]:
            sig.append((i, 1))
        elif dn and r[i - 1] > (100 - p.pullback_th) >= r[i]:
            sig.append((i, -1))
    return sig


def signals_squeeze(df, p, ind):
    c = df["close"].to_numpy(float)
    atr = ind["atr"]
    upper, lower, pct = ind["bb_upper"], ind["bb_lower"], ind["bb_pct"]
    sig = []
    for i in range(1, len(c)):
        if not (np.isfinite(pct[i - 1]) and np.isfinite(upper[i]) and np.isfinite(lower[i]) and np.isfinite(atr[i])):
            continue
        was_squeezed = pct[i - 1] <= p.bb_width_pct_max
        if not was_squeezed:
            continue
        buf = p.breakout_buffer_atr * atr[i]
        if c[i] > upper[i] + buf:
            sig.append((i, 1))
        elif c[i] < lower[i] - buf:
            sig.append((i, -1))
    return sig


def signals_rsi2(df, p, ind):
    c = df["close"].to_numpy(float)
    r = ind["rsi2"]
    sma = ind.get("trend_sma")
    sig = []
    for i in range(len(c)):
        if not np.isfinite(r[i]):
            continue
        if sma is not None and not np.isfinite(sma[i]):
            continue
        long_regime = True if sma is None else c[i] > sma[i]
        short_regime = True if sma is None else c[i] < sma[i]
        if r[i] <= p.rsi_entry_long and long_regime:
            sig.append((i, 1))
        elif r[i] >= p.rsi_entry_short and short_regime:
            sig.append((i, -1))
    return sig


def signals_random(df, p, ind):
    n = len(df)
    rng = np.random.default_rng(p.random_seed + (ind.get("seed_salt") or 0))
    sig = []
    for i in range(n):
        if rng.random() < p.random_p:
            side = 1 if rng.random() < 0.5 else -1
            sig.append((i, side))
    return sig


FAMILY_SIGNALS = {
    "donchian": signals_donchian,
    "ema_pullback": signals_ema_pullback,
    "squeeze": signals_squeeze,
    "rsi2": signals_rsi2,
    "random": signals_random,
}


def precompute(df, p: SParams, seed_salt=0):
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    ind = {"atr": wilder_atr(h, l, c, p.atr_period), "seed_salt": seed_salt}
    if p.family == "donchian":
        ind["don_hi"], ind["don_lo"] = donchian(h, l, p.don_entry_n)
        if p.use_don_exit:
            ind["don_exit_hi"], ind["don_exit_lo"] = donchian(h, l, p.don_exit_n)
    elif p.family == "ema_pullback":
        ind["ema_fast"] = ema(c, p.ema_fast)
        ind["ema_slow"] = ema(c, p.ema_slow)
        ind["rsi"] = rsi(c, p.rsi_period)
    elif p.family == "squeeze":
        ind["bb_upper"], ind["bb_lower"], ind["bb_pct"] = bollinger_width_pct(c, p.bb_period, p.bb_k, p.bb_rank_win)
    elif p.family == "rsi2":
        ind["rsi2"] = rsi(c, p.rsi2_period)
        if p.trend_filter_sma > 0:
            ind["trend_sma"] = pd.Series(c).rolling(p.trend_filter_sma).mean().to_numpy()
    elif p.family == "random":
        pass
    else:
        raise ValueError(f"unknown family {p.family!r}")
    return ind


# ---------------------------------------------------------------------------
# Shared trade-management engine: signal at bar i -> fill at open[i+1] ->
# manage stop / chandelier trail / fixed TP / RSI-cross exit / time exit.
# ---------------------------------------------------------------------------
def simulate_symbol(df: pd.DataFrame, p: SParams, lo: int, hi: int, ind=None):
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    n = len(c)
    if ind is None:
        ind = precompute(df, p)
    atr = ind["atr"]
    sig_fn = FAMILY_SIGNALS[p.family]
    signals = sig_fn(df, p, ind)

    start = max(lo, p.atr_period + 2)
    end = min(hi, n - 1)
    trades = []
    sig_iter = iter(s for s in signals if start <= s[0] < end)
    next_sig = next(sig_iter, None)
    busy_until = -1

    while next_sig is not None:
        i, side = next_sig
        if i <= busy_until:
            next_sig = next(sig_iter, None)
            continue
        if p.long_only and side < 0:
            next_sig = next(sig_iter, None)
            continue
        if p.short_only and side > 0:
            next_sig = next(sig_iter, None)
            continue
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            next_sig = next(sig_iter, None)
            continue
        entry_bar = i + 1
        if entry_bar >= n:
            break
        entry = o[entry_bar]
        risk = p.stop_atr * a
        if risk <= 0:
            next_sig = next(sig_iter, None)
            continue
        sl = entry - risk if side > 0 else entry + risk
        tp = (entry + p.tp_atr * a if side > 0 else entry - p.tp_atr * a) if p.tp_atr > 0 else None
        extreme = entry  # running highest-high (long) / lowest-low (short) since entry, for chandelier trail
        cost = p.cost_atr_frac * a

        exit_price = None
        exit_bar = entry_bar
        for k in range(entry_bar, min(entry_bar + p.max_hold_bars, n)):
            if side > 0:
                if l[k] <= sl:
                    exit_price, exit_bar = sl, k
                    break
                if tp is not None and h[k] >= tp:
                    exit_price, exit_bar = tp, k
                    break
            else:
                if h[k] >= sl:
                    exit_price, exit_bar = sl, k
                    break
                if tp is not None and l[k] <= tp:
                    exit_price, exit_bar = tp, k
                    break
            # RSI(2) mean-reversion exit: cross back to the midline.
            if p.family == "rsi2":
                rk = ind["rsi2"][k]
                if np.isfinite(rk):
                    if side > 0 and rk >= p.rsi_exit_mid:
                        exit_price, exit_bar = c[k], k
                        break
                    if side < 0 and rk <= p.rsi_exit_mid:
                        exit_price, exit_bar = c[k], k
                        break
            # Turtle-style opposite-channel exit.
            if p.family == "donchian" and p.use_don_exit:
                eh, el = ind["don_exit_hi"][k], ind["don_exit_lo"][k]
                if side > 0 and np.isfinite(el) and c[k] < el:
                    exit_price, exit_bar = c[k], k
                    break
                if side < 0 and np.isfinite(eh) and c[k] > eh:
                    exit_price, exit_bar = c[k], k
                    break
            # Chandelier ATR trail (ratchets toward price, never away).
            if p.use_trail:
                ak = atr[k] if np.isfinite(atr[k]) and atr[k] > 0 else a
                if side > 0:
                    extreme = max(extreme, h[k])
                    sl = max(sl, extreme - p.trail_atr * ak)
                else:
                    extreme = min(extreme, l[k])
                    sl = min(sl, extreme + p.trail_atr * ak)

        if exit_price is None:
            exit_bar = min(entry_bar + p.max_hold_bars - 1, n - 1)
            exit_price = c[exit_bar]

        gross = (exit_price - entry) * side
        r = (gross - 2 * cost) / risk
        trades.append(dict(i=i, entry_bar=entry_bar, side=side, r=r, exit_bar=exit_bar))
        busy_until = exit_bar
        next_sig = next(sig_iter, None)

    return trades


def rs_of(trades):
    return [t["r"] for t in trades]


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------
def load_dataset(tf: str):
    folder = os.path.join(DATA, f"tv_{tf}")
    files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    data = {}
    for f in files:
        sym = os.path.splitext(os.path.basename(f))[0]
        df = pd.read_csv(f, parse_dates=["time"])
        if len(df) > 250:
            data[sym] = df
    return data


if __name__ == "__main__":
    data = load_dataset("D1")
    print(f"Loaded {len(data)} symbols: {', '.join(data)}")
    p = SParams(family="donchian", don_entry_n=20, stop_atr=2.0, trail_atr=3.0, cost_atr_frac=0.02)
    pooled = []
    for sym, df in data.items():
        tr = simulate_symbol(df, p, 0, len(df))
        pooled.extend(rs_of(tr))
    arr = np.array(pooled)
    print(f"N={len(arr)} exp={arr.mean():+.4f}R win={ (arr>0).mean()*100:.1f}% totR={arr.sum():+.1f}")
