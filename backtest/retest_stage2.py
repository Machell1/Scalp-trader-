"""Stage 2: combinations of Stage-1 axis winners + 2x-cost stress + per-symbol
stability. Same pre-registration (RETEST_SPEC_2026-07-12, e7df76df...).
Still a SCREEN: promotions need the full gate + forward validation.
"""
import dataclasses
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nearmiss_decisions import daylist, challenge_mc
from parity_engine import prep_symbol
from walkforward_dsr import real_cost_per_side
from retest_engine import Cell, run_cell, TRIO, SPREAD_DIR


def load():
    syms, qall = [], {}
    for k in TRIO:
        raw = pd.read_csv(os.path.join(SPREAD_DIR, k + ".csv"))
        s = prep_symbol(raw, real_cost_per_side(raw), k)
        dt = pd.to_datetime(raw[[c for c in raw.columns if c.lower() == "time"][0]])
        q = pd.PeriodIndex(dt, freq="Q")
        qs = sorted(q.unique())
        oos_qs = set(qs[int(len(qs) * 0.7):])
        qall.update({int(e): (qq in oos_qs) for e, qq in zip(s.ep, q)})
        syms.append(s)
    return syms, qall


def main():
    syms, qall = load()

    cells = [
        Cell("BASE (corrected)"),
        # TP1.5 family
        Cell("TP1.5 W2", tp=1.5),
        Cell("TP1.5 W3", filt="W3", tp=1.5),
        Cell("TP1.5 K3", filt="K3", tp=1.5),
        Cell("TP1.5 none", filt="none", tp=1.5),
        Cell("TP1.5 hold12", tp=1.5, hold=12),
        Cell("TP1.5 + so33@1R", tp=1.5, so_frac=0.33, so_at=1.0),
        # scale-out family (owner's idea)
        Cell("so33@1R W2 (S1 winner)", so_frac=0.33, so_at=1.0),
        Cell("so33@1R W3", filt="W3", so_frac=0.33, so_at=1.0),
        Cell("so33@1R hold12", hold=12, so_frac=0.33, so_at=1.0),
        Cell("so33@1R TP2.0", tp=2.0, so_frac=0.33, so_at=1.0),
        Cell("so50@1R TP2.0", tp=2.0, so_frac=0.50, so_at=1.0),
        Cell("so33@1R none", filt="none", so_frac=0.33, so_at=1.0),
        # unstable-but-big entry styles x winning geometry
        Cell("market W2 TP1.5", entry="market", tp=1.5),
        Cell("stop.05 W2 TP1.5", entry="stop", offset=0.05, tp=1.5),
        Cell("market W2 so33@1R", entry="market", so_frac=0.33, so_at=1.0),
        Cell("stop.05 W2 so33@1R", entry="stop", offset=0.05, so_frac=0.33, so_at=1.0),
        # W3 + hold interaction
        Cell("W3 hold12", filt="W3", hold=12),
        Cell("W3 TP2.0", filt="W3", tp=2.0),
    ]

    print(f"STAGE 2: {len(cells)} cells | OOS at real cost AND 2x cost | per-symbol OOS signs")
    print(f"{'cell':26s} {'n':>5s} {'exp':>8s} {'OOS':>8s} {'OOS2x':>8s} {'both':>6s} {'bust':>6s} "
          f"{'US30':>7s} {'US100':>7s} {'JP225':>7s}")
    for cell in cells:
        tape, tape2 = [], []
        per_oos = []
        for s in syms:
            t1 = run_cell(s, cell)
            s2 = dataclasses.replace(s, cost=s.cost * 2.0)
            t2 = run_cell(s2, cell)
            tape += t1
            tape2 += t2
            po = np.array([r for (e, r) in t1 if qall[e]])
            per_oos.append(po.mean() if len(po) else np.nan)
        r = np.array([x[1] for x in tape])
        oos = np.array([x[1] for x in tape if qall[x[0]]])
        oos2 = np.array([x[1] for x in tape2 if qall[x[0]]])
        both, bust, med = challenge_mc(daylist(sorted(tape)))
        print(f"{cell.name:26s} {len(r):5d} {r.mean():+8.4f} "
              f"{oos.mean() if len(oos) else float('nan'):+8.4f} "
              f"{oos2.mean() if len(oos2) else float('nan'):+8.4f} "
              f"{both:6.1%} {bust:6.1%} "
              f"{per_oos[0]:+7.3f} {per_oos[1]:+7.3f} {per_oos[2]:+7.3f}", flush=True)

    print("\nScreen only. Promotion bar: OOS>0 at 2x cost, 3/3 symbol signs, then full gate + forward.")


if __name__ == "__main__":
    main()
