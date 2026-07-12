"""Cross-symbol holdout for the Stage-2 finalists (RETEST_SPEC e7df76df...).

The scale-out/TP geometry was mined ONLY on the trio. These 10 symbols never
participated in that fitting. PREDICTION REGISTERED BEFORE RUNNING: if the
geometry is a real property of the momentum-pullback signal family, the
holdout pool should show (a) positive expectancy and (b) improvement over the
holdout BASE (bracket TP3) of the same sign/order as on the trio
(base -> +0.05..0.07). If it is trio-mining luck, holdout deltas ~ 0.

Live-parity enumeration, W2 0.30, real per-instrument cost (fallback 0.03
where no spread column), metals/FX get their commission-inclusive costs where
known. Direction evidence at scale; not a substitute for forward validation.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parity_engine import prep_symbol
from walkforward_dsr import real_cost_per_side
from retest_engine import Cell, run_cell

HOLDOUT = [
    ("Germany_40", "derivM15_spreadgated"),
    ("US_SP_500", "derivM15_spreadgated"),
    ("UK_100", "derivM15_spreadgated"),
    ("France_40", "derivM15_spreadgated"),
    ("US_Small_Cap_2000", "derivM15_spreadgated"),
    ("Australia_200", "derivM15_diverse"),
    ("Hong_Kong_50", "derivM15_diverse"),
    ("EURUSD", "derivM15_diverse"),
    ("XAUUSD", "derivM15_diverse"),
    ("XAGUSD", "derivM15_diverse"),
]

CELLS = [
    Cell("BASE bracket TP3"),
    Cell("TP1.5 + so33@1R", tp=1.5, so_frac=0.33, so_at=1.0),
    Cell("so50@1R TP2.0", tp=2.0, so_frac=0.50, so_at=1.0),
]


def main():
    syms = []
    for key, sub in HOLDOUT:
        path = os.path.join(HERE, "data", sub, key + ".csv")
        if not os.path.isfile(path):
            print(f"  {key}: no file, skipped")
            continue
        raw = pd.read_csv(path)
        cost = real_cost_per_side(raw)
        if not np.isfinite(cost):
            cost = 0.03
        syms.append(prep_symbol(raw, cost, key))

    print(f"HOLDOUT: {len(syms)} symbols never used in the exit-geometry mining\n")
    header = f"{'symbol':20s}" + "".join(f"{c.name:>22s}" for c in CELLS)
    print(header)
    pooled = {c.name: [] for c in CELLS}
    per_sym = {c.name: [] for c in CELLS}
    for s in syms:
        row = f"{s.name:20s}"
        for c in CELLS:
            t = run_cell(s, c)
            rs = [r for (_, r) in t]
            pooled[c.name] += rs
            m = np.mean(rs) if rs else float("nan")
            per_sym[c.name].append(m)
            row += f"{m:+21.4f} "
        print(row, flush=True)

    print("\nPOOLED (all holdout trades):")
    base_mean = None
    for c in CELLS:
        rs = np.array(pooled[c.name])
        pos = sum(1 for m in per_sym[c.name] if np.isfinite(m) and m > 0)
        mean = rs.mean()
        se = rs.std(ddof=1) / np.sqrt(len(rs))
        if base_mean is None:
            base_mean = mean
        print(f"  {c.name:22s}: n={len(rs):5d} exp={mean:+.4f} (SE {se:.4f}) "
              f"| symbols positive {pos}/{len(per_sym[c.name])} "
              f"| delta vs holdout-BASE {mean - base_mean:+.4f}")

    print("\nPrediction check: real geometry -> holdout delta ~ +0.05..0.07 like the trio;"
          "\nmining luck -> delta ~ 0. Numbers above decide.")


if __name__ == "__main__":
    main()
