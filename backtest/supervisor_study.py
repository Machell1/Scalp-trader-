"""Supervisory-layer MC study: the proposal's exact throttle + allocator functions,
applied CAUSALLY to the live trio's W2 trade tape, judged on challenge math.

Pre-registered: docs/SUPERVISOR_SPEC_2026-07-11.md
  (SHA256 eabed8411a616f0410b2c817b858b38ac55843b48ff089c4b98c49af594e8f9a)
T1 graded drawdown throttle (daily / total anchoring) | T2 symbol allocator
(raw rolling-30 / Bayesian-shrunk) | T4 regime buckets (report-only).
Metrics: no-time-limit both-phases, bust, median pass days vs flat baseline.
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr
from walkforward_dsr import real_cost_per_side
from universe_w2_study import w2_trades, norm

NSIM = 10000
PRIOR_MEAN, PRIOR_N = 0.1117, 50
TRIO = [("Wall_Street_30", "derivM15_spreadgated/Wall_Street_30.csv"),
        ("US_Tech_100", "derivM15_spreadgated/US_Tech_100.csv"),
        ("Japan_225", "derivM15_spreadgated/Japan_225.csv")]


def build_tape():
    rows = []
    for sym, rel in TRIO:
        raw = pd.read_csv(os.path.join(HERE, "data", rel))
        cost = real_cost_per_side(raw)
        df = norm(raw)
        for (t, i, r) in w2_trades(df, cost):
            rows.append((t, sym, r))
    rows.sort()
    return rows


def allocator_multipliers(tape, shrink):
    """Causal per-trade multiplier from the symbol's trailing 30 W2 trades."""
    hist = {}
    mults = []
    for (t, sym, r) in tape:
        past = hist.get(sym, [])
        n = len(past)
        recent = past[-30:]
        rn = len(recent)
        if shrink:
            exp = ((PRIOR_MEAN * PRIOR_N + sum(recent)) / (PRIOR_N + rn)) if rn else PRIOR_MEAN
        else:
            exp = float(np.mean(recent)) if rn else 0.0
        if n < 30:
            m = 1.0
        elif exp <= 0:
            m = 0.50
        elif exp < 0.05:
            m = 0.75
        elif exp < 0.10:
            m = 1.0
        else:
            m = 1.25
        mults.append(m)
        hist.setdefault(sym, []).append(r)
    return np.array(mults)


def day_blocks(tape, mults=None):
    days = {}
    for k, (t, sym, r) in enumerate(tape):
        m = 1.0 if mults is None else mults[k]
        days.setdefault(t // 86400, []).append(r * m)
    return list(days.values())


def throttle_mult(dd):
    if dd >= 5.0:
        return 0.0
    if dd >= 4.0:
        return 0.25
    if dd >= 3.0:
        return 0.50
    if dd >= 2.0:
        return 0.75
    return 1.0


def challenge_throttled(daylist, rng, risk, target, cap_days, anchor):
    """Replay with the proposal's graded throttle. anchor: 'daily'|'total'|None."""
    eq, peak = 0.0, 0.0
    days_used = 0
    for _ in range(cap_days):
        d = daylist[rng.integers(0, len(daylist))]
        days_used += 1
        day_pnl = 0.0
        for rr in d:
            if anchor == "daily":
                m = throttle_mult(-day_pnl)
            elif anchor == "total":
                m = throttle_mult(peak - eq)
            else:
                m = 1.0
            pnl = rr * risk * m
            eq += pnl
            day_pnl += pnl
            peak = max(peak, eq)
            if day_pnl <= -5.0 or eq <= -10.0:
                return 0, days_used
            if eq >= target:
                return 1, days_used
            if day_pnl <= -3.0:
                break                          # EA daily halt (live behavior retained)
    return -1, days_used


def mc(daylist, anchor, nsim=NSIM):
    rng = np.random.default_rng(7)
    r1 = np.array([challenge_throttled(daylist, rng, 0.5, 10.0, 365, anchor) for _ in range(nsim)])
    p1 = float(np.mean(r1[:, 0] == 1))
    med = int(np.median(r1[r1[:, 0] == 1, 1])) if (r1[:, 0] == 1).any() else -1
    bust1 = float(np.mean(r1[:, 0] == 0))
    r2 = np.array([challenge_throttled(daylist, rng, 0.5, 5.0, 365, anchor) for _ in range(nsim // 2)])
    p2 = float(np.mean(r2[:, 0] == 1))
    return p1 * p2, bust1, med, p1, p2


def main():
    tape = build_tape()
    print(f"trio W2 tape: {len(tape)} trades over {len(set(t//86400 for t,_,_ in tape))} trading days "
          f"| mean R {np.mean([r for _,_,r in tape]):+.4f}")

    base = day_blocks(tape)
    b_both, b_bust, b_med, b1, b2 = mc(base, None)
    print(f"\nBASELINE flat 0.5%:            both={b_both:.1%} bust={b_bust:.1%} medDays={b_med} (P1 {b1:.1%})")

    for anchor, tag in (("daily", "T1a throttle DAILY-anchored "), ("total", "T1b throttle TOTAL-anchored ")):
        both, bust, med, p1, p2 = mc(base, anchor)
        print(f"{tag}: both={both:.1%} bust={bust:.1%} medDays={med} (P1 {p1:.1%}) "
              f"-> {'IMPROVES' if both > b_both and bust <= b_bust else 'no'}")

    for shrink, tag in ((False, "T2a allocator raw rolling-30"), (True, "T2b allocator Bayesian-shrunk")):
        mults = allocator_multipliers(tape, shrink)
        dist = {m: int((mults == m).sum()) for m in sorted(set(mults))}
        dl = day_blocks(tape, mults)
        both, bust, med, p1, p2 = mc(dl, None)
        print(f"{tag}: both={both:.1%} bust={bust:.1%} medDays={med} (P1 {p1:.1%}) "
              f"mult-dist {dist} -> {'IMPROVES' if both > b_both and bust <= b_bust else 'no'}")

    # T4 exploratory regime buckets (report-only)
    print("\nT4 regime buckets (W2 trio tape, report-only):")
    feats = []
    for sym, rel in TRIO:
        raw = pd.read_csv(os.path.join(HERE, "data", rel))
        cost = real_cost_per_side(raw)
        df = norm(raw)
        h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        atr = wilder_atr(h, l, c, 14)
        atr_pct = pd.Series(atr).rolling(2000, min_periods=200).rank(pct=True).to_numpy()
        hrs = pd.to_datetime(df["time"]).dt.hour.to_numpy()
        for (t, i, r) in w2_trades(df, cost):
            feats.append((r, atr_pct[i], hrs[i]))
    fd = pd.DataFrame(feats, columns=["r", "atrpct", "hr"])
    fd["vol"] = pd.cut(fd.atrpct, [0, .33, .66, 1], labels=["lowVol", "midVol", "highVol"])
    fd["sess"] = np.where((fd.hr >= 7) & (fd.hr <= 17), "LDN/NY", "off")
    print(fd.groupby("vol", observed=True).r.agg(["count", "mean"]).round(4).to_string())
    print(fd.groupby("sess").r.agg(["count", "mean"]).round(4).to_string())


if __name__ == "__main__":
    main()
