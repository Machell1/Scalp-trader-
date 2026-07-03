"""PROFIT-CONDITIONAL TIME-EXIT STUDY: at bar 8 close losers/flat on schedule, but give
profitable trades until bar 16. PRE-REGISTERED cells (3): extend if unrealized r >=
{0.0, 0.5, 1.0} at the base exit bar. Baseline = v1.23 live (pure bracket, hold 8).
Protocol identical to exit_ladder_study; cumulative deflation 65+3=68 trials.
Comparator context: unconditional hold16 (already passed, avgWin 2.24R) — the question is
whether conditioning beats it by keeping the dead-trade cleanup at bar 8."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

from scalper_confluence import CParams, simulate_symbol_c
from walkforward_dsr import load_spreadgated, real_cost_per_side
from experiment import EMC, nppf, psr, stt

BRACKET = dict(direction="cont", entry_style="limit", entry_offset_atr=0.6,
               pending_expiry_bars=3, stop_atr=1.0, tp_atr=3.0,
               lock_trigger_atr=99.0, trail_atr=99.0, max_hold_bars=8,
               momentum_bars=6, momentum_atr=2.0, atr_period=14)
CELLS = [("ext16 if r>=0.0", 16, 0.0), ("ext16 if r>=0.5", 16, 0.5), ("ext16 if r>=1.0", 16, 1.0)]
N_TRIALS = 68

def tape(data, costs, ext, minr, block=True, cm=1.0):
    recs = []
    for sym, df in data.items():
        c = costs[sym] * cm
        if not np.isfinite(c):
            continue
        p = CParams(**BRACKET, cost_atr_frac=c, hold_ext_bars=ext, hold_ext_min_r=minr,
                    block_overlap=block)
        tr, _ = simulate_symbol_c(df, p, 0, len(df))
        tt = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            recs.append((tt[t["i"]], sym, t["i"], float(t["r"])))
    return pd.DataFrame(recs, columns=["time", "sym", "sig_i", "r"]).sort_values("time").reset_index(drop=True)

def oos(t, frac=0.70):
    q = pd.PeriodIndex(pd.to_datetime(t["time"]), freq="Q")
    qs = sorted(q.unique()); n_is = max(1, int(len(qs) * frac))
    return t[q.isin(qs[n_is:])]

def wins(r):
    r = np.asarray(r, float); w = r[r > 0]
    return (w.mean() if w.size else 0.0), float((r >= 2.0).mean() * 100)

def main():
    data = load_spreadgated()
    costs = {s: real_cost_per_side(df) for s, df in data.items()}
    print("PROFIT-CONDITIONAL TIME-EXIT — v1.23 bracket baseline, 12 majors, real cost\n")

    base = tape(data, costs, 0, 0.0)
    bo = oos(base); bs = stt(bo["r"].to_numpy())
    baw, b2 = wins(bo["r"])
    b2x = stt(oos(tape(data, costs, 0, 0.0, cm=2.0))["r"].to_numpy())["exp"]
    print(f"BASELINE (bracket h8) OOS: N={bs['n']} exp={bs['exp']:+.4f} t={bs['t']:+.2f} "
          f"avgWin={baw:+.2f}R >=2R {b2:.1f}%  2x {b2x:+.4f}")
    # unconditional hold16 comparator
    u16 = oos(tape(data, costs, 16, -99.0))
    us = stt(u16["r"].to_numpy()); uaw, u2 = wins(u16["r"])
    print(f"COMPARATOR uncond hold16 OOS: N={us['n']} exp={us['exp']:+.4f} avgWin={uaw:+.2f}R >=2R {u2:.1f}%\n")

    var_null = 1.0 / max(2, bs["n"] - 1)
    z1 = nppf(1 - 1.0 / N_TRIALS); z2 = nppf(1 - 1.0 / N_TRIALS * math.exp(-1))
    sr0 = math.sqrt(var_null) * ((1 - EMC) * z1 + EMC * z2)

    base_pair = tape(data, costs, 0, 0.0, block=False)
    base_pair_oos = oos(base_pair).set_index(["sym", "sig_i"])["r"]

    hdr = (f"{'cell':20s}{'N':>6s}{'exp':>8s}{'dExp':>8s}{'pair_t':>7s}{'avgWin':>7s}"
           f"{'>=2R%':>7s}{'exp2x':>8s}{'Qpos':>6s}{'Sym+':>6s}{'DSR':>6s}  VERDICT")
    print(hdr); print("-" * len(hdr))
    for label, ext, minr in CELLS:
        t_blk = tape(data, costs, ext, minr)
        co = oos(t_blk); so = stt(co["r"].to_numpy())
        aw, p2 = wins(co["r"])
        dexp = so["exp"] - bs["exp"]
        pair = oos(tape(data, costs, ext, minr, block=False)).set_index(["sym", "sig_i"])["r"]
        j = pd.concat([base_pair_oos.rename("b"), pair.rename("c")], axis=1).dropna()
        d = (j["c"] - j["b"]).to_numpy()
        pt = (d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))) if len(d) > 5 and d.std(ddof=1) > 0 else float("nan")
        e2 = stt(oos(tape(data, costs, ext, minr, cm=2.0))["r"].to_numpy())["exp"]
        qg = co.groupby(pd.PeriodIndex(pd.to_datetime(co["time"]), freq="Q"))["r"].mean()
        qpos, qn = int((qg > 0).sum()), len(qg)
        sg = co.groupby("sym")["r"].agg(["mean", "count"])
        sp = int(((sg["mean"] > 0) & (sg["count"] >= 10)).sum()); stot = int((sg["count"] >= 10).sum())
        dsr = psr(co["r"].to_numpy(), sr0)
        gates = [dexp > 0, np.isfinite(pt) and pt > 1.96, np.isfinite(dsr) and dsr >= 0.95,
                 e2 > 0, qpos >= math.ceil(qn * 0.6), sp >= math.ceil(stot * 0.6), so["n"] >= 250]
        verdict = "SHIP" if all(gates) else ("watch" if dexp > 0 else "no")
        print(f"{label:20s}{so['n']:6d}{so['exp']:+8.4f}{dexp:+8.4f}{pt:+7.2f}{aw:+7.2f}"
              f"{p2:7.1f}{e2:+8.4f}{qpos:3d}/{qn:<2d}{sp:3d}/{stot:<2d}{dsr:6.2f}  {verdict}")

if __name__ == "__main__":
    main()
