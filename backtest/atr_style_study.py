"""Does the DEPLOYED ATR estimator (MT5 iATR = sliding SIMPLE mean of TR) retain
the edge that was validated with Wilder-smoothed ATR?

Context (audit 2026-07-10, finding #21): the live EA reads iATR, whose formula --
verified in the terminal's own Indicators/Examples/ATR.mq5 line 92 -- is
    ATR[i] = ATR[i-1] + (TR[i] - TR[i-period]) / period          (rolling SMA)
while every validated number came from wilder_atr() (RMA, alpha=1/period).
Everything the strategy does is ATR-scaled, so the two estimators produce
partially different trade sets. This study reruns the EXACT audited engine
(simulate_symbol, untouched) on the same real Deriv M15 data with only the ATR
function swapped, to decide whether the EA must be moved to Wilder (Tier B).

Protocol: deployed params (mom 6 / 2.0 ATR, limit 0.6, expiry 3, SL 1.0, TP 3.0,
hold 8, cost 0.03/side), 70/30 IS/OOS, 12-symbol spread-gated universe.
Also reports the signal-overlap rate between estimators per symbol.
"""
import glob
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scalper_backtest as sb


def sma_atr(high, low, close, period):
    """Exact iATR replica: rolling simple mean of TR (same TR as wilder_atr)."""
    prev_close = np.empty_like(close)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = np.full_like(close, np.nan)
    if len(close) <= period:
        return atr
    csum = np.cumsum(tr)
    atr[period:] = (csum[period:] - csum[:-period]) / period
    return atr


def params(cost):
    return sb.Params(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
                     entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
                     stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
                     max_hold_bars=8, cost_atr_frac=cost)


def stats(rs):
    rs = np.asarray(rs, float)
    if len(rs) < 3:
        return dict(n=len(rs), exp=0.0, t=0.0)
    sd = rs.std(ddof=1)
    return dict(n=len(rs), exp=float(rs.mean()),
                t=float(rs.mean() / (sd / np.sqrt(len(rs)))) if sd > 0 else 0.0)


def signal_mask(df, atr_fn, p):
    """Recreate the engine's signal condition per bar for overlap measurement."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = atr_fn(h, l, c, p.atr_period)
    n = len(c); mb = p.momentum_bars
    sig = np.zeros(n, bool)
    for i in range(mb + p.atr_period + 1, n):
        a = atr[i - 1]
        if not np.isfinite(a) or a <= 0:
            continue
        move = (c[i - 1] - c[i - 1 - mb]) / a
        if move >= p.momentum_atr and c[i - 1] > o[i - 1]:
            sig[i] = True
        elif -move >= p.momentum_atr and c[i - 1] < o[i - 1]:
            sig[i] = True
    return sig


def main():
    p = params(0.03)
    files = sorted(glob.glob(os.path.join(HERE, "data", "derivM15_spreadgated", "*.csv")))
    print(f"{len(files)} symbols | deployed params, cost 0.03/side, 70/30 IS/OOS\n")
    print(f"{'symbol':16s} {'bars':>6s} | {'WILDER oos':>10s} {'t':>6s} | {'SMA oos':>8s} {'t':>6s} | {'overlap':>7s}")
    print("-" * 78)
    pooled = {"wilder": [], "sma": []}
    idx_pooled = {"wilder": [], "sma": []}
    orig = sb.wilder_atr
    for f in files:
        sym = os.path.basename(f).replace(".csv", "").replace("_M15", "")
        df = pd.read_csv(f)
        ncols = {c.lower(): c for c in df.columns}
        df = df.rename(columns={ncols[k]: k for k in ("time", "open", "high", "low", "close") if k in ncols})
        n = len(df); split = int(0.7 * n)
        res = {}
        for style, fn in (("wilder", orig), ("sma", sma_atr)):
            sb.wilder_atr = fn
            res[style] = sb.simulate_symbol(df, p, split, n)
        sb.wilder_atr = orig
        sw, ss = signal_mask(df, orig, p), signal_mask(df, sma_atr, p)
        union = (sw | ss).sum()
        overlap = (sw & ss).sum() / union if union else float("nan")
        W, S = stats(res["wilder"]), stats(res["sma"])
        pooled["wilder"] += list(res["wilder"]); pooled["sma"] += list(res["sma"])
        if sym in ("US_Tech_100", "Wall_Street_30"):
            idx_pooled["wilder"] += list(res["wilder"]); idx_pooled["sma"] += list(res["sma"])
        print(f"{sym:16s} {n:6d} | {W['exp']:+10.4f} {W['t']:+6.2f} | {S['exp']:+8.4f} {S['t']:+6.2f} | {overlap:6.1%}")
    print("-" * 78)
    for tag, d in (("POOLED 12-sym OOS", pooled), ("FTMO pair (US30+US100) OOS", idx_pooled)):
        W, S = stats(d["wilder"]), stats(d["sma"])
        print(f"{tag}: WILDER exp {W['exp']:+.4f} (n={W['n']}, t={W['t']:+.2f})  |  "
              f"SMA exp {S['exp']:+.4f} (n={S['n']}, t={S['t']:+.2f})")
    print("\nDecision rule: SMA OOS expectancy comparable to Wilder (same sign, within noise)"
          "\n=> deployed estimator acceptable, Tier B ATR swap optional; SMA materially worse => swap to Wilder.")


if __name__ == "__main__":
    main()
