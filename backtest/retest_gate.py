"""Gate columns for the Stage-2 finalists (RETEST_SPEC e7df76df...).

Finalists (OOS>0 at 2x cost AND 3/3 per-symbol OOS signs):
  TP1.5 + so33@1R | so50@1R TP2.0 | so33@1R hold12 | so33@1R TP2.0

Columns: stitched-quarter positivity, DSR at the FULL incremented trial count
(155 prior + 49 retest screen cells = 204), challenge MC + timeline, and the
FTMO second-venue direction check (own bars, own cost, ~10 months).
STILL not a ship decision: discovery data is contaminated (exit geometry mined
from the collapse analysis); forward validation is the decision frame.
"""
import dataclasses
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nearmiss_decisions import daylist, challenge_mc
from prop_mc_scalper import challenge
from experiment import psr
from walkforward_dsr import real_cost_per_side, dsr_hurdle
from parity_engine import prep_symbol
from retest_engine import Cell, run_cell, TRIO, SPREAD_DIR

N_TRIALS = 204

FINALISTS = [
    Cell("TP1.5 + so33@1R", tp=1.5, so_frac=0.33, so_at=1.0),
    Cell("so50@1R TP2.0", tp=2.0, so_frac=0.50, so_at=1.0),
    Cell("so33@1R hold12", hold=12, so_frac=0.33, so_at=1.0),
    Cell("so33@1R TP2.0", tp=2.0, so_frac=0.33, so_at=1.0),
]


def timeline_mc(dl, nsim=8000, risk=0.3):
    rng = np.random.default_rng(7)
    funded, days = 0, []
    for _ in range(nsim):
        s1, d1 = challenge(dl, rng, risk, 10.0, 365)
        if s1 != 1:
            continue
        s2, d2 = challenge(dl, rng, risk, 5.0, 365)
        if s2 == 1:
            funded += 1
            days.append(d1 + d2)
    return funded / nsim, (int(np.median(days)) if days else -1)


def main():
    syms, quarters = [], {}
    for k in TRIO:
        raw = pd.read_csv(os.path.join(SPREAD_DIR, k + ".csv"))
        s = prep_symbol(raw, real_cost_per_side(raw), k)
        dt = pd.to_datetime(raw[[c for c in raw.columns if c.lower() == "time"][0]])
        q = pd.PeriodIndex(dt, freq="Q")
        qs = sorted(q.unique())
        oos_qs = set(qs[int(len(qs) * 0.7):])
        quarters[k] = ({int(e): str(qq) for e, qq in zip(s.ep, q)},
                       {str(qq) for qq in oos_qs})
        syms.append(s)

    # FTMO bars fetched once
    ftmo = {}
    try:
        from parity_ftmo_check import fetch
        for sym, key in (("US30.cash", "Wall_Street_30"), ("US100.cash", "US_Tech_100"),
                         ("JP225.cash", "Japan_225")):
            df, cost = fetch(sym)
            if df is not None and np.isfinite(cost):
                ftmo[key] = prep_symbol(df, cost, key)
    except Exception as e:
        print(f"FTMO fetch unavailable: {e}")

    for cell in FINALISTS:
        tape, qtags = [], []
        for s in syms:
            t = run_cell(s, cell)
            tape += t
            qm, oq = quarters[s.name]
            qtags += [(qm[e], qm[e] in oq, r) for (e, r) in t]
        r = np.array([x[1] for x in tape])
        oos_r = np.array([r_ for (_, isoos, r_) in qtags if isoos])
        # quarter table (OOS quarters only, pooled across symbols)
        qdf = pd.DataFrame([(qq, r_) for (qq, isoos, r_) in qtags if isoos],
                           columns=["q", "r"])
        qtab = qdf.groupby("q").r.mean()
        qpos = int((qtab > 0).sum())
        dsr = psr(oos_r, dsr_hurdle(n_trials=N_TRIALS, n_obs=oos_r.size))
        both, bust, med = challenge_mc(daylist(sorted((e, r_) for (e, r_) in tape)))
        fund, fdays = timeline_mc(daylist(sorted((e, r_) for (e, r_) in tape)))
        print(f"\n=== {cell.name} ===")
        print(f"  n={len(r)} exp={r.mean():+.4f} | OOS n={len(oos_r)} exp={oos_r.mean():+.4f} "
              f"| DSR@{N_TRIALS}={dsr:.3f} | OOS quarters positive {qpos}/{len(qtab)}")
        print(f"  MC both={both:.1%} bust={bust:.1%} medP1={med}d | funded={fund:.1%} med={fdays}d")
        if ftmo:
            fr = []
            for key, fs in ftmo.items():
                ft = run_cell(fs, cell)
                fr += [x[1] for x in ft]
                print(f"  FTMO {key}: n={len(ft)} exp={np.mean([x[1] for x in ft]) if ft else float('nan'):+.4f}")
            print(f"  FTMO pooled: n={len(fr)} exp={np.mean(fr):+.4f}  (direction evidence, ~10mo)")

    print("\nGate summary is a SCREEN promotion check. Contaminated discovery data ->")
    print("forward validation (live demo) is the decision frame for any deployment.")


if __name__ == "__main__":
    main()
