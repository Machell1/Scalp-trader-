"""Diagnostics for the parity-census collapse (Art II.4: presume pipeline broken).

1. Independent sequential reference implementation of the M1 live semantics;
   must match run_live(single symbol) trade-for-trade.
2. Mechanism decomposition:
   A1 = causal engine, live re-arm (i+3), NO pre-entry W2, post-hoc W2 filter
        -> isolates the unfilled-pending re-arm rule vs control
   M1 = pre-entry W2 + live re-arm (from census)
        -> A1 vs M1 isolates the W2-ordering effect
3. Overlap analysis: control vs M1 trade sets keyed by (sym, signal bar) --
   where does the +0.101 live?
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nearmiss_decisions import wick_trades, daylist, challenge_mc
from parity_engine import (prep_symbol, run_live, find_fill, resolve_bracket,
                           trade_r, START, EXPIRY, OFFSET)
from walkforward_dsr import real_cost_per_side

SPREAD_DIR = os.path.join(HERE, "data", "derivM15_spreadgated")
TRIO = ["Wall_Street_30", "US_Tech_100", "Japan_225"]


def load(key):
    raw = pd.read_csv(os.path.join(SPREAD_DIR, key + ".csv"))
    return prep_symbol(raw, real_cost_per_side(raw), key)


def sequential_reference_m1(s, thr, window=EXPIRY):
    """Independent, obviously-correct-by-construction M1 semantics:
    signal bar i evaluated once; W2 pre-entry; unfilled pending -> next signal
    bar i+window; after exit at xb -> next signal bar xb+1."""
    trades = []
    n = len(s.c)
    i = START
    while i < n - 1:
        sd = int(s.side[i])
        if sd == 0 or not (np.isfinite(s.watr[i]) and s.watr[i] >= thr):
            i += 1
            continue
        a = s.atr[i]
        entry = s.c[i] - OFFSET * a * sd
        j = find_fill(s, sd, entry, i + 1, i + window)
        if j < 0:
            i = i + window          # first eligible signal bar = i+window
            continue
        xb, xp, reason = resolve_bracket(s, j, sd, entry, a)
        trades.append((s.name, i, j, xb, sd, trade_r(s, sd, entry, xp, a)))
        i = xb + 1
    return trades


def main():
    syms = {k: load(k) for k in TRIO}
    W = int(os.environ.get("PARITY_WINDOW", "4"))   # 4 = live as-deployed

    print(f"=== 1. Event engine vs sequential reference (M1, per symbol, window={W}) ===")
    all_ok = True
    for k, s in syms.items():
        ref = sequential_reference_m1(s, 0.30, window=W)
        ev, _ = run_live([s], thr={k: 0.30}, caps=None, window=W)
        evt = [(t.sym, t.sig, t.entry_bar, t.exit_bar, t.side, t.r) for t in ev]
        ok = len(ref) == len(evt) and all(
            a[:5] == b[:5] and abs(a[5] - b[5]) < 1e-9 for a, b in zip(ref, evt))
        print(f"  {k}: ref n={len(ref)} event n={len(evt)} -> {'IDENTICAL' if ok else 'DIFF'}")
        if not ok:
            all_ok = False
            for a, b in zip(ref, evt):
                if a[:5] != b[:5] or abs(a[5] - b[5]) >= 1e-9:
                    print(f"    first diff: ref={a} event={b}")
                    break
    if not all_ok:
        print("  EVENT ENGINE BUG -- stop and fix before interpreting anything.")
        sys.exit(1)

    print(f"\n=== 2. Mechanism decomposition (trio pooled, window={W}) ===")
    control = []
    for k in TRIO:
        control += wick_trades(k + ".csv", 0.30)
    cr = np.array([x[1] for x in control])
    both, bust, med = challenge_mc(daylist(control))
    print(f"  control (M0 + post-hoc W2):  n={len(cr)} exp={cr.mean():+.4f} "
          f"| MC both={both:.1%} bust={bust:.1%} med={med}d")

    a1 = []
    for k, s in syms.items():
        tr, _ = run_live([s], thr=None, caps=None, window=W)
        a1 += [t for t in tr if np.isfinite(s.watr[t.sig]) and s.watr[t.sig] >= 0.30]
    a1r = np.array([t.r for t in a1])
    tape = sorted((int(t.ep_sig), float(t.r)) for t in a1)
    both, bust, med = challenge_mc(daylist(tape))
    print(f"  A1 (live re-arm + post-hoc W2): n={len(a1r)} exp={a1r.mean():+.4f} "
          f"| MC both={both:.1%} bust={bust:.1%} med={med}d   <- isolates re-arm rule")

    m1 = []
    for k, s in syms.items():
        tr, _ = run_live([s], thr={k: 0.30}, caps=None, window=W)
        m1 += tr
    m1r = np.array([t.r for t in m1])
    tape = sorted((int(t.ep_sig), float(t.r)) for t in m1)
    both, bust, med = challenge_mc(daylist(tape))
    print(f"  M1 (pre-entry W2 + live re-arm): n={len(m1r)} exp={m1r.mean():+.4f} "
          f"| MC both={both:.1%} bust={bust:.1%} med={med}d   <- adds W2-ordering effect")

    print("\n=== 3. Overlap: where does the +0.101 live? (key = sym, signal bar) ===")
    ckey = {}
    for k in TRIO:
        raw = pd.read_csv(os.path.join(SPREAD_DIR, k + ".csv"))
        nmap = {c.lower(): c for c in raw.columns}
        df = raw.rename(columns={nmap[x]: x for x in ("time",) if x in nmap})
        # rebuild control with signal-bar keys (wick_trades returns (epoch, r));
        # map epoch -> bar index via prep arrays
        s = syms[k]
        ep_to_bar = {int(e): b for b, e in enumerate(s.ep)}
        for (e, r) in wick_trades(k + ".csv", 0.30):
            ckey[(k, ep_to_bar[int(e)])] = r
    mkey = {(t.sym, t.sig): t.r for t in m1}
    inter = set(ckey) & set(mkey)
    only_c = set(ckey) - set(mkey)
    only_m = set(mkey) - set(ckey)
    ic = np.array([ckey[x] for x in inter])
    im = np.array([mkey[x] for x in inter])
    oc = np.array([ckey[x] for x in only_c])
    om = np.array([mkey[x] for x in only_m])
    print(f"  shared signals: n={len(inter)} exp(control)={ic.mean():+.4f} exp(M1)={im.mean():+.4f} "
          f"identical_r={(np.abs(ic - im) < 1e-9).mean():.1%}")
    print(f"  control-only (live can't take): n={len(oc)} exp={oc.mean():+.4f}")
    print(f"  M1-only (recovered/shifted):    n={len(om)} exp={om.mean():+.4f}")


if __name__ == "__main__":
    main()
