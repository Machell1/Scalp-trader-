"""Near-miss recombination decision analyses D1 + D2 (pre-registered addendum in
UNIVERSE_W2_SPEC_2026-07-10.md, file hash faf87558... at registration).

D1: W3 (wick>=0.50) vs live W2 — challenge MC on the trio.
D2: funded-account objective — trio vs trio+GER40 vs trio+GER40+EURUSD.
Decision analyses on already-gated components; no ledger charge.
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr, Params, simulate_symbol
from walkforward_dsr import real_cost_per_side
from prop_mc_scalper import challenge

P = dict(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
         entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
         stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
         max_hold_bars=8)


def wick_trades(fn, thr):
    raw = pd.read_csv(os.path.join(HERE, "data", "derivM15_spreadgated", fn))
    n = {c.lower(): c for c in raw.columns}
    df = raw.rename(columns={n[k]: k for k in ("time", "open", "high", "low", "close") if k in n})
    cost = real_cost_per_side(raw)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    up = h - np.maximum(o, c); dn = np.minimum(o, c) - l
    sigs = []
    simulate_symbol(df, Params(**P, cost_atr_frac=cost), 0, len(df), signals_out=sigs)
    dt = pd.to_datetime(df["time"])
    ep = ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy()
    out = []
    for (i, eb, side, r) in sigs:
        if np.isfinite(atr[i]) and atr[i] > 0 and ((up[i] if side > 0 else dn[i]) / atr[i]) >= thr:
            out.append((int(ep[i]), float(r)))
    return out


def daylist(tape):
    days = {}
    for (t, r) in tape:
        days.setdefault(t // 86400, []).append(r)
    return list(days.values())


def challenge_mc(dl, nsim=8000):
    rng = np.random.default_rng(7)
    r1 = np.array([challenge(dl, rng, 0.3, 10.0, 365) for _ in range(nsim)])
    p1 = float(np.mean(r1[:, 0] == 1)); bust = float(np.mean(r1[:, 0] == 0))
    med = int(np.median(r1[r1[:, 0] == 1, 1])) if (r1[:, 0] == 1).any() else -1
    r2 = np.array([challenge(dl, rng, 0.3, 5.0, 365)[0] for _ in range(nsim // 2)])
    return p1 * float(np.mean(r2 == 1)), bust, med


def funded_mc(dl, nsim=8000, risk=0.3, days_horizon=252):
    """Funded rules: no target; dead at -5% day or -10% static; track P&L."""
    rng = np.random.default_rng(11)
    surv, annual, monthly = [], [], []
    for _ in range(nsim):
        eq = 0.0; dead = False
        month_marks = []
        for dnum in range(days_horizon):
            d = dl[rng.integers(0, len(dl))]
            day_pnl = 0.0
            for rr in d:
                pnl = rr * risk
                eq += pnl; day_pnl += pnl
                if day_pnl <= -5.0 or eq <= -10.0:
                    dead = True; break
                if day_pnl <= -3.0:
                    break
            if dnum % 21 == 20:
                month_marks.append(eq)
            if dead:
                break
        surv.append(0 if dead else 1)
        annual.append(eq)
        if len(month_marks) >= 2:
            diffs = np.diff([0] + month_marks)
            monthly.append(float(np.median(diffs)))
    return (float(np.mean(surv)), float(np.median(annual)),
            float(np.median(monthly)) if monthly else float("nan"))


def main():
    trio_w2 = []
    for fn in ("Wall_Street_30.csv", "US_Tech_100.csv", "Japan_225.csv"):
        trio_w2 += wick_trades(fn, 0.30)
    trio_w3 = []
    for fn in ("Wall_Street_30.csv", "US_Tech_100.csv", "Japan_225.csv"):
        trio_w3 += wick_trades(fn, 0.50)

    print("==== D1: W3 vs W2 (challenge objective) ====")
    for name, tape in (("W2 (live)", trio_w2), ("W3 (0.50)", trio_w3)):
        both, bust, med = challenge_mc(daylist(tape))
        print(f"  {name:10s}: n={len(tape):5d} trades | both={both:.1%} bust={bust:.1%} medDaysP1={med}")

    print("\n==== D2: funded-account objective (252d, no target, -5%day/-10%static) ====")
    ger = wick_trades("Germany_40.csv", 0.30)
    eur = wick_trades("EURUSD.csv", 0.30) if os.path.isfile(os.path.join(HERE, "data", "derivM15_spreadgated", "EURUSD.csv")) else None
    if eur is None:
        raw_p = os.path.join(HERE, "data", "derivM15_diverse", "EURUSD.csv")
        eur = wick_trades_diverse(raw_p) if False else None
    variants = [("trio (live)", trio_w2), ("trio+GER40", trio_w2 + ger)]
    if eur:
        variants.append(("trio+GER40+EURUSD", trio_w2 + ger + eur))
    else:
        print("  (EURUSD: no spread-gated CSV — evaluated only if present; skipped, reported honestly)")
    for name, tape in variants:
        surv, ann, mon = funded_mc(daylist(tape))
        print(f"  {name:18s}: n={len(tape):5d} | P(survive 1y)={surv:.1%} | median annual {ann:+.1f}% "
              f"| median month {mon:+.2f}% (~${mon*1000*0.8:,.0f}/mo withdrawal @$100k, 80% split)")


if __name__ == "__main__":
    main()
