"""Invariant checks for the new additive exit-engine params (scale-out / pyramid /
adaptive TP) in simulate_symbol_c. Complements baseline_repro_test.py (which proves
the OFF-defaults path is byte-exact vs scalper_backtest.simulate_symbol):

  1. Feature-NEUTRAL settings reproduce the baseline exactly (maxdiff 0.00e+00):
     scale-out with frac=0; pyramid with an unreachable trigger; adaptive TP with
     lo=hi=tp_atr.
  2. Active features never change the ENTRY set (same signal indices with
     block_overlap=False) — required for the paired per-signal t-stat to be valid.
  3. Downside bounds: scale-out(+BE) cannot lose more than the baseline -1R-costs;
     the pyramid's worst case is -frac*TP_R - (1+frac)*2*cost: unit1 never exits
     below BE once armed (engine convention: exit at the stop price), while the add
     can fill anywhere below TP (gap-guarded) and ride back down to BE.

Runs on a seeded in-memory synthetic series (pure engine property, no broker data).
Exit code 0 = all pass.
"""
from __future__ import annotations
import sys
import numpy as np

from baseline_repro_test import synthetic_symbol
from scalper_confluence import CParams, simulate_symbol_c, rs_of

BRACKET = dict(direction="cont", entry_style="limit", entry_offset_atr=0.6,
               pending_expiry_bars=3, stop_atr=1.0, tp_atr=3.0,
               lock_trigger_atr=99.0, trail_atr=99.0, max_hold_bars=8,
               momentum_bars=6, momentum_atr=2.0, atr_period=14)
COST = 0.02


def main() -> int:
    df = synthetic_symbol(42, n=30000)
    ok = True
    base = rs_of(simulate_symbol_c(df, CParams(**BRACKET, cost_atr_frac=COST), 0, len(df))[0])

    neutral = [
        ("scale-out frac=0", dict(scaleout_r=1.5, scaleout_frac=0.0)),
        ("pyramid trigger +99R", dict(pyr_add_r=99.0)),
        ("adaptive TP lo=hi=3", dict(tp_rv_split=0.5, tp_atr_lo_rv=3.0, tp_atr_hi_rv=3.0)),
    ]
    for label, kw in neutral:
        rs = rs_of(simulate_symbol_c(df, CParams(**BRACKET, cost_atr_frac=COST, **kw),
                                     0, len(df))[0])
        d = (float(np.max(np.abs(np.array(rs) - np.array(base))))
             if len(rs) == len(base) else float("inf"))
        good = d == 0.0
        ok &= good
        print(f"  [{'PASS' if good else 'FAIL'}] neutral {label:24s} maxdiff {d:.2e}  "
              f"N {len(rs)}/{len(base)}")

    p0 = CParams(**BRACKET, cost_atr_frac=COST, block_overlap=False)
    sig0 = [t["i"] for t in simulate_symbol_c(df, p0, 0, len(df))[0]]
    active = [
        ("scale-out 50%@+1.5R", dict(scaleout_r=1.5, scaleout_frac=0.5)),
        ("scale-out 50%@+1.5R+BE", dict(scaleout_r=1.5, scaleout_frac=0.5, scaleout_be=True)),
        ("pyramid add 100%@+1R", dict(pyr_add_r=1.0, pyr_add_frac=1.0)),
        ("adaptive TP lo4/hi3", dict(tp_rv_split=0.5, tp_atr_lo_rv=4.0, tp_atr_hi_rv=3.0)),
    ]
    tr0 = simulate_symbol_c(df, p0, 0, len(df))[0]
    for label, kw in active:
        p = CParams(**BRACKET, cost_atr_frac=COST, block_overlap=False, **kw)
        tr = simulate_symbol_c(df, p, 0, len(df))[0]
        same = [t["i"] for t in tr] == sig0
        changed = sum(1 for a, b in zip(tr, tr0) if a["r"] != b["r"])
        good = same and changed > 0
        ok &= good
        print(f"  [{'PASS' if good else 'FAIL'}] active  {label:24s} entries identical: {same}  "
              f"changed R on {changed} trades")

    p = CParams(**BRACKET, cost_atr_frac=COST, scaleout_r=1.5, scaleout_frac=0.5,
                scaleout_be=True)
    rs = rs_of(simulate_symbol_c(df, p, 0, len(df))[0])
    bound = min(base) - 1e-12
    good = min(rs) >= bound
    ok &= good
    print(f"  [{'PASS' if good else 'FAIL'}] bound   scale-out+BE min R {min(rs):+.3f} >= "
          f"baseline min {min(base):+.3f}")

    frac = 1.0
    p = CParams(**BRACKET, cost_atr_frac=COST, pyr_add_r=1.0, pyr_add_frac=frac)
    rs = rs_of(simulate_symbol_c(df, p, 0, len(df))[0])
    # worst case: add fills just under TP (+3R here), whole position exits at BE
    pyr_bound = -frac * BRACKET["tp_atr"] - (1.0 + frac) * 2 * COST - 1e-9
    good = min(rs) >= pyr_bound
    ok &= good
    print(f"  [{'PASS' if good else 'FAIL'}] bound   pyramid min R {min(rs):+.3f} >= "
          f"{pyr_bound:+.3f}")

    print(f"\n>>> {'ALL INVARIANTS PASS' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
