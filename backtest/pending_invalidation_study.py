"""PENDING-INVALIDATION STUDY — user rule: "orders must be pulled once the setup is violated."

Tests cancelling a resting pullback LIMIT when price runs BEYOND the signal close by k*ATR
without filling (the deep-V fill risk inside the 3-bar window). Baseline = v1.23 live config
(pure bracket: SL1/TP3/hold8, no lock/trail), 12 spread-gated majors, real per-instrument cost.

PRE-REGISTERED cells (3): cancel_beyond_atr in {1.0, 1.5, 2.4}. 2.4 = the TP-touch level
(entry = close-0.6*ATR, TP = entry+3*ATR = close+2.4*ATR): cancel when the market has already
taken the move we wanted. Cumulative deflation count: 62 prior + 3 = 65 trials.

DECISIVE EVIDENCE: the rule only REMOVES fills. With identical signals (block_overlap=False,
paired on (sym,sig_i)), the trades removed by each cell are identified exactly and their
baseline expectancy IS the rule's value: removing losers = good, removing winners = bad.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

from scalper_confluence import CParams, simulate_symbol_c
from walkforward_dsr import load_spreadgated, real_cost_per_side
from experiment import stt

BRACKET = dict(direction="cont", entry_style="limit", entry_offset_atr=0.6,
               pending_expiry_bars=3, stop_atr=1.0, tp_atr=3.0,
               lock_trigger_atr=99.0, trail_atr=99.0, max_hold_bars=8,
               momentum_bars=6, momentum_atr=2.0, atr_period=14)
CELLS = [1.0, 1.5, 2.4]

def tape(data, costs, cancel, block, cost_mult=1.0):
    recs = []
    for sym, df in data.items():
        c = costs[sym] * cost_mult
        if not np.isfinite(c):
            continue
        p = CParams(**BRACKET, cost_atr_frac=c, cancel_beyond_atr=cancel, block_overlap=block)
        tr, _ = simulate_symbol_c(df, p, 0, len(df))
        tt = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            recs.append((tt[t["i"]], sym, t["i"], float(t["r"])))
    return pd.DataFrame(recs, columns=["time", "sym", "sig_i", "r"]).sort_values("time").reset_index(drop=True)

def oos(t, is_frac=0.70):
    q = pd.PeriodIndex(pd.to_datetime(t["time"]), freq="Q")
    qs = sorted(q.unique()); n_is = max(1, int(len(qs) * is_frac))
    return t[q.isin(qs[n_is:])]

def main():
    data = load_spreadgated()
    costs = {s: real_cost_per_side(df) for s, df in data.items()}
    print("PENDING-INVALIDATION STUDY — v1.23 bracket baseline, 12 majors, real cost\n")

    base_blk = tape(data, costs, 0.0, block=True)
    bs = stt(oos(base_blk)["r"].to_numpy())
    print(f"BASELINE OOS: N={bs['n']} exp={bs['exp']:+.4f} t={bs['t']:+.2f}\n")
    base_prd = tape(data, costs, 0.0, block=False).set_index(["sym", "sig_i"])

    hdr = (f"{'cancel@ATR':12s}{'N_oos':>7s}{'exp':>8s}{'dExp':>8s}"
           f"{'removed':>8s}{'remv_exp':>9s}{'remv_win%':>10s}{'keep_exp':>9s}  READ")
    print(hdr); print("-" * len(hdr))
    for k in CELLS:
        blk = tape(data, costs, k, block=True)
        so = stt(oos(blk)["r"].to_numpy())
        # paired removal analysis on the FULL sample (rule is mechanical, not fitted)
        prd = tape(data, costs, k, block=False).set_index(["sym", "sig_i"])
        removed_idx = base_prd.index.difference(prd.index)
        removed = base_prd.loc[removed_idx, "r"].to_numpy()
        kept = base_prd.loc[base_prd.index.intersection(prd.index), "r"].to_numpy()
        r_exp = removed.mean() if removed.size else float("nan")
        r_win = (removed > 0).mean() * 100 if removed.size else float("nan")
        # bootstrap CI on removed mean
        if removed.size >= 20:
            rng = np.random.default_rng(7)
            boots = [rng.choice(removed, removed.size, replace=True).mean() for _ in range(2000)]
            lo, hi = np.percentile(boots, [2.5, 97.5])
            ci = f"CI[{lo:+.3f},{hi:+.3f}]"
        else:
            ci = "n too small"
        read = ("removes LOSERS -> rule helps" if removed.size >= 20 and hi < 0 else
                "removes WINNERS -> rule hurts" if removed.size >= 20 and lo > 0 else
                "neutral/underpowered")
        print(f"{k:<12.1f}{so['n']:7d}{so['exp']:+8.4f}{so['exp']-bs['exp']:+8.4f}"
              f"{removed.size:8d}{r_exp:+9.4f}{r_win:10.1f}{kept.mean():+9.4f}  {read} {ci}")

if __name__ == "__main__":
    main()
