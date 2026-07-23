"""Three-bar reversal pattern — Stage A screen.

Pre-registered: docs/THREEBAR_REVERSAL_SPEC_2026-07-22.md
  (SHA256 87f7b6e8aa84bbcadde1f34bddc000c3913c5c3f7fdcdbe8dc0a87a01b7704b2)

T1 H1 house-exits | T2 H1 pattern-native exits | T3 M30 house-exits.
Quartet primary + 10-symbol holdout. E2 currency. All cells reported.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_m30h4_study import TF
from run_h1_universe_screen import META_PATH
from nearmiss_decisions import daylist, challenge_mc

QUARTET = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
HOLDOUT = ("Germany_40", "US_SP_500", "UK_100", "France_40", "US_Small_Cap_2000",
           "Australia_200", "Hong_Kong_50", "EURUSD", "XAUUSD", "XAGUSD")


def run_cell(tf: TF, exits: str):
    """exits: 'house' (SL1/bank75@1R/TP1.5/hold8) | 'native' (rev-extreme SL/TP2R/hold16)."""
    o, h, l, c, atr, ep = tf.o, tf.h, tf.l, tf.c, tf.atr, tf.ep
    n = len(c)
    cost = tf.cost_e1 * 2.0     # E2 per side
    dt = pd.to_datetime(tf.frame["time"])
    q = pd.PeriodIndex(dt, freq="Q")
    qs = sorted(q.unique())
    oos_qs = set(qs[int(len(qs) * 0.7):])
    rows = []
    t = 22
    while t < n - 2:
        a = atr[t]
        if not np.isfinite(a) or a <= 0:
            t += 1
            continue
        bull = (c[t - 2] < o[t - 2]) and (l[t - 1] < l[t - 2]) and (c[t] > h[t - 1])
        bear = (c[t - 2] > o[t - 2]) and (h[t - 1] > h[t - 2]) and (c[t] < l[t - 1])
        if not (bull or bear):
            t += 1
            continue
        side = 1 if bull else -1
        j = t + 1
        entry = o[j]
        if exits == "house":
            risk = 1.0 * a
            sl = entry - risk * side
            tp = entry + 1.5 * a * side
            part = entry + 1.0 * risk * side
            part_frac, hold = 0.75, 8
        else:
            rev = l[t - 1] - 0.1 * a if side > 0 else h[t - 1] + 0.1 * a
            risk = min(abs(entry - rev), 1.5 * a)
            if risk <= 0:
                t += 1
                continue
            sl = entry - risk * side
            tp = entry + 2.0 * risk * side
            part, part_frac, hold = None, 0.0, 16
        banked, frac, done = 0.0, 1.0, False
        xb, xp = None, None
        for k in range(j, min(j + hold, n)):
            if side > 0:
                if l[k] <= sl:
                    xb, xp = k, sl
                    break
                if part is not None and not done and h[k] >= part:
                    banked, frac, done = part_frac * 1.0, 1.0 - part_frac, True
                if h[k] >= tp:
                    xb, xp = k, tp
                    break
            else:
                if h[k] >= sl:
                    xb, xp = k, sl
                    break
                if part is not None and not done and l[k] <= part:
                    banked, frac, done = part_frac * 1.0, 1.0 - part_frac, True
                if l[k] <= tp:
                    xb, xp = k, tp
                    break
        if xb is None:
            xb = min(j + hold - 1, n - 1)
            xp = c[xb]
        gross = banked + frac * (xp - entry) * side / risk
        r = gross - 2.0 * cost * a / risk
        rows.append((int(ep[t]), r, q[t] in oos_qs))
        t = xb + 1
    return rows


def report(rows_by_sym, label, primary_syms, min_syms):
    all_rows = [r for rows in rows_by_sym.values() for r in rows]
    if not all_rows:
        print(f"  {label}: no trades")
        return
    r = np.array([x[1] for x in all_rows])
    ro = np.array([x[1] for x in all_rows if x[2]])
    pos = sum(1 for s in primary_syms
              if rows_by_sym.get(s) and np.mean([x[1] for x in rows_by_sym[s]]) > 0)
    both, bust, med = challenge_mc(daylist(sorted((e, rr) for (e, rr, _) in all_rows)))
    gates = dict(full=r.mean() > 0, oos=len(ro) > 0 and ro.mean() > 0, syms=pos >= min_syms)
    ok = all(gates.values())
    print(f"  {label}: n={len(r):5d} expE2={r.mean():+.4f} win={(r > 0).mean():.1%} "
          f"| OOS n={len(ro)} exp={(ro.mean() if len(ro) else float('nan')):+.4f} "
          f"| syms+ {pos}/{len(primary_syms)} | MC both={both:.1%} "
          f"-> {'SURVIVE' if ok else 'FAIL'}")
    for s, rows in rows_by_sym.items():
        if rows:
            print(f"      {s:18s} n={len(rows):4d} exp={np.mean([x[1] for x in rows]):+.4f}")


def main():
    chk = subprocess.run([sys.executable, str(HERE / "verify_data.py")],
                         capture_output=True, text=True)
    line = (chk.stdout + chk.stderr).strip().splitlines()[-1]
    print("verify_data:", line)
    assert "46 OK" in line
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))

    for cell, minutes, exits in (("T1 H1 house-exits", 60, "house"),
                                 ("T2 H1 native-exits", 60, "native"),
                                 ("T3 M30 house-exits", 30, "house")):
        print(f"\n=== {cell} ===")
        prim = {}
        for s in QUARTET:
            prim[s] = run_cell(TF(s, meta, minutes), exits)
        report(prim, "QUARTET", QUARTET, 3)
        hold = {}
        for s in HOLDOUT:
            try:
                hold[s] = run_cell(TF(s, meta, minutes), exits)
            except Exception as e:
                print(f"      {s}: skipped ({type(e).__name__})")
        allh = [r for rows in hold.values() for r in rows]
        if allh:
            hr = np.array([x[1] for x in allh])
            hpos = sum(1 for s, rows in hold.items() if rows and np.mean([x[1] for x in rows]) > 0)
            print(f"  HOLDOUT-10: n={len(hr)} exp={hr.mean():+.4f} syms+ {hpos}/{len(hold)}")

    print("\nScreen only; survivors advance to account-MC under a separate registration.")


if __name__ == "__main__":
    main()
