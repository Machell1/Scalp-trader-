"""PARTIAL-SCALE-OUT STUDY: can banking part of a winner at +1.5R while leaving
a runner improve expectancy or right-tail capture vs v1.23 pure bracket?

PRE-REGISTERED cells (3, fixed before running):
  * close 33%, 50%, or 67% at +1.5R; remainder keeps the normal TP3/hold8 bracket.

This is not a trailing-profit-protection rule: no stop is moved and no conditional hold is
introduced. Baseline = v1.23 pure bracket. Protocol mirrors exit_ladder_study.py: real
per-instrument Deriv cost, stitched-OOS quarters, paired per-signal t-stat, DSR deflated
for 68 cumulative trials, 2x cost stress, stability, and win-size metrics.
"""
from __future__ import annotations
import math
import sys
import numpy as np
import pandas as pd

from scalper_confluence import CParams, simulate_symbol_c
from walkforward_dsr import SPREAD_GATED, DATA_DIR, load_spreadgated, real_cost_per_side
from experiment import EMC, nppf, psr, stt

N_TRIALS = 68
BRACKET = dict(direction="cont", entry_style="limit", entry_offset_atr=0.6,
               pending_expiry_bars=3, stop_atr=1.0, tp_atr=3.0,
               lock_trigger_atr=99.0, trail_atr=99.0, max_hold_bars=8,
               momentum_bars=6, momentum_atr=2.0, atr_period=14)
CELLS = [("scale33@1.5R", 0.33), ("scale50@1.5R", 0.50), ("scale67@1.5R", 0.67)]


def tape(data, costs, frac=0.0, block=True, cost_mult=1.0):
    recs = []
    for sym, df in data.items():
        c = costs[sym] * cost_mult
        if not np.isfinite(c):
            continue
        p = CParams(**BRACKET, cost_atr_frac=c, block_overlap=block,
                    partial_exit_r=(1.5 if frac > 0 else 0.0), partial_exit_frac=frac)
        tr, _ = simulate_symbol_c(df, p, 0, len(df))
        tt = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            recs.append((tt[t["i"]], sym, t["i"], float(t["r"])))
    return pd.DataFrame(recs, columns=["time", "sym", "sig_i", "r"]).sort_values("time").reset_index(drop=True)


def split(t, frac=0.70):
    q = pd.PeriodIndex(pd.to_datetime(t["time"]), freq="Q")
    qs = sorted(q.unique())
    n_is = max(1, int(len(qs) * frac))
    return t[q.isin(qs[:n_is])], t[q.isin(qs[n_is:])]


def wins(r):
    r = np.asarray(r, float)
    w = r[r > 0]
    return (w.mean() if w.size else 0.0, np.median(w) if w.size else 0.0,
            float((r >= 2.0).mean() * 100))


def pair_t(base, cand):
    j = pd.concat([base.rename("b"), cand.rename("c")], axis=1).dropna()
    d = (j["c"] - j["b"]).to_numpy()
    return (d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))) if len(d) > 5 and d.std(ddof=1) > 0 else float("nan")


def main():
    data = load_spreadgated()
    if len(data) < 8:
        missing = [s for s in SPREAD_GATED if s not in data]
        print(f"Need spread-gated CSVs in {DATA_DIR}/ ({len(data)}/{len(SPREAD_GATED)} found).",
              file=sys.stderr)
        if missing:
            print(f"  Missing: {', '.join(missing)}", file=sys.stderr)
        print("  Run: python fetch_spreadgated.py  (MT5 terminal open + logged in)", file=sys.stderr)
        sys.exit(1)
    costs = {s: real_cost_per_side(df) for s, df in data.items()}
    print("PARTIAL-SCALE-OUT STUDY — v1.23 bracket baseline, 12 majors, real cost")
    print(f"DSR deflation: {N_TRIALS} cumulative research trials\n")

    base = tape(data, costs)
    base_is, base_oos = split(base)
    bs = stt(base_oos["r"].to_numpy())
    baw, bmw, b2 = wins(base_oos["r"])
    base_pair = split(tape(data, costs, block=False))[1].set_index(["sym", "sig_i"])["r"]
    base2x = stt(split(tape(data, costs, cost_mult=2.0))[1]["r"].to_numpy())["exp"]
    print(f"BASELINE (no scale-out) OOS: N={bs['n']} exp={bs['exp']:+.4f} t={bs['t']:+.2f} "
          f"avgWin={baw:+.2f}R medWin={bmw:+.2f}R >=2R {b2:.1f}%  2x {base2x:+.4f}\n")

    var_null = 1.0 / max(2, bs["n"] - 1)
    z1 = nppf(1 - 1.0 / N_TRIALS)
    z2 = nppf(1 - 1.0 / N_TRIALS * math.exp(-1))
    sr0 = math.sqrt(var_null) * ((1 - EMC) * z1 + EMC * z2)

    hdr = (f"{'cell':14s}{'N':>6s}{'exp':>8s}{'dExp':>8s}{'pair_t':>7s}{'WFE':>6s}"
           f"{'avgWin':>7s}{'medWin':>7s}{'>=2R%':>7s}{'exp2x':>8s}{'Qpos':>6s}{'Sym+':>6s}{'DSR':>6s}  VERDICT")
    print(hdr); print("-" * len(hdr))
    for label, frac in CELLS:
        t_blk = tape(data, costs, frac)
        c_is, c_oos = split(t_blk)
        so, si = stt(c_oos["r"].to_numpy()), stt(c_is["r"].to_numpy())
        aw, mw, p2 = wins(c_oos["r"])
        de = so["exp"] - bs["exp"]
        wfe = so["exp"] / si["exp"] if si["exp"] > 0 else float("nan")
        cand_pair = split(tape(data, costs, frac, block=False))[1].set_index(["sym", "sig_i"])["r"]
        pt = pair_t(base_pair, cand_pair)
        e2 = stt(split(tape(data, costs, frac, cost_mult=2.0))[1]["r"].to_numpy())["exp"]
        qg = c_oos.groupby(pd.PeriodIndex(pd.to_datetime(c_oos["time"]), freq="Q"))["r"].mean()
        qpos, qn = int((qg > 0).sum()), len(qg)
        sg = c_oos.groupby("sym")["r"].agg(["mean", "count"])
        sp, stot = int(((sg["mean"] > 0) & (sg["count"] >= 10)).sum()), int((sg["count"] >= 10).sum())
        dsr = psr(c_oos["r"].to_numpy(), sr0)
        gates = [de > 0, np.isfinite(pt) and pt > 1.96, np.isfinite(wfe) and wfe >= 0.3,
                 np.isfinite(dsr) and dsr >= 0.95, e2 > 0,
                 qpos >= math.ceil(qn * 0.6), sp >= math.ceil(stot * 0.6), so["n"] >= 250]
        verdict = "SHIP" if all(gates) else ("watch" if de > 0 and so["exp"] > 0 else "no")
        print(f"{label:14s}{so['n']:6d}{so['exp']:+8.4f}{de:+8.4f}{pt:+7.2f}{wfe:6.2f}"
              f"{aw:+7.2f}{mw:+7.2f}{p2:7.1f}{e2:+8.4f}{qpos:3d}/{qn:<2d}{sp:3d}/{stot:<2d}{dsr:6.2f}  {verdict}")


if __name__ == "__main__":
    main()
