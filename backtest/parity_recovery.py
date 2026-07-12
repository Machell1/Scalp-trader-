"""EXPLORATORY recovery arms after the live-parity collapse.

ALL ARMS CONTAMINATED: these mechanizations were derived from this data's
failure decomposition (verification agent's roadmap). Nothing here can ship on
these numbers alone -- forward validation (the live demo) is the only
decision-grade frame. Charged to the ledger as exploratory screens (see spec
addendum). Per-symbol (M1-style) frames at window=4 (live as-deployed).

Arms:
  STRATA -- instrumented control run: tag re-arm-child trades in the M0 tape
            and expiry-substitute trades in the M1 tape (where does +0.28/-0.18
            live, by fill-bar stratum)
  S1(C)  -- post-expiry cooldown: unfilled pending -> suppress signals until
            bar i+w+C, C in {1,2,4} (kill the toxic substitutes)
  Q2     -- untouched expiry release: at expiry, if price never touched the
            level, re-place the SAME level once with a fresh window
  L1     -- OCO ladder, max 2 rungs: each fresh signal arms a new level
            (opposite side clears the ladder); first touch fills nearest-to-
            market level first; siblings cancelled on fill
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nearmiss_decisions import daylist, challenge_mc
from parity_engine import (prep_symbol, find_fill, resolve_bracket, trade_r,
                           run_m0, run_live, START, OFFSET)
from walkforward_dsr import real_cost_per_side

SPREAD_DIR = os.path.join(HERE, "data", "derivM15_spreadgated")
TRIO = ["Wall_Street_30", "US_Tech_100", "Japan_225"]
W = 4       # live as-deployed window
THR = 0.30


def load(key):
    raw = pd.read_csv(os.path.join(SPREAD_DIR, key + ".csv"))
    return prep_symbol(raw, real_cost_per_side(raw), key)


def w2ok(s, i):
    return s.side[i] != 0 and np.isfinite(s.watr[i]) and s.watr[i] >= THR


def seq_s1(s, cooldown_extra):
    """Live M1 semantics + post-expiry cooldown of C extra bars."""
    out = []
    n = len(s.c)
    i = START
    while i < n - 1:
        if not w2ok(s, i):
            i += 1
            continue
        sd = int(s.side[i])
        a = s.atr[i]
        entry = s.c[i] - OFFSET * a * sd
        j = find_fill(s, sd, entry, i + 1, i + W)
        if j < 0:
            i = i + W + cooldown_extra
            continue
        xb, xp, _ = resolve_bracket(s, j, sd, entry, a)
        out.append((int(s.ep[i]), trade_r(s, sd, entry, xp, a), i))
        i = xb + 1
    return out


def seq_q2(s):
    """Live M1 semantics + single untouched-expiry re-placement of the level."""
    out = []
    n = len(s.c)
    i = START
    while i < n - 1:
        if not w2ok(s, i):
            i += 1
            continue
        sd = int(s.side[i])
        a = s.atr[i]
        entry = s.c[i] - OFFSET * a * sd
        j = find_fill(s, sd, entry, i + 1, i + W)
        if j < 0:
            # untouched by construction (no fill = no touch); re-place once
            j2 = find_fill(s, sd, entry, i + W + 1, i + 2 * W)
            if j2 < 0:
                i = i + 2 * W       # both windows consumed; next scan bar
                continue
            xb, xp, _ = resolve_bracket(s, j2, sd, entry, a)
            out.append((int(s.ep[i]), trade_r(s, sd, entry, xp, a), i))
            i = xb + 1
            continue
        xb, xp, _ = resolve_bracket(s, j, sd, entry, a)
        out.append((int(s.ep[i]), trade_r(s, sd, entry, xp, a), i))
        i = xb + 1
    return out


def seq_ladder(s, max_rungs=2):
    """OCO ladder: every W2 signal arms a rung (newest replaces oldest beyond
    max_rungs; opposite side clears). Per bar, nearest-to-market rung fills
    first. Fill cancels all rungs. Per-symbol, causal."""
    out = []
    n = len(s.c)
    rungs = []          # list of (sig_i, side, entry, atr, window_end)
    pos_until = -1      # busy through this bar (position)
    cool_upto = -1
    b = START + 1
    while b < n:
        # position blocks everything
        if b <= pos_until:
            b += 1
            continue
        # expire dead rungs (their window ended before this bar)
        rungs = [r for r in rungs if r[4] >= b]
        # fill check on bar b for armed rungs (armed = placed at bar <= b)
        live = [r for r in rungs if r[0] + 1 <= b]
        if live:
            sd = live[0][1]
            # nearest-to-market first: for longs the HIGHEST entry, shorts lowest
            ordered = sorted(live, key=lambda r: -r[2] * sd)
            filled = None
            for (qi, qsd, qe, qa, we) in ordered:
                if (qsd > 0 and s.l[b] <= qe) or (qsd < 0 and s.h[b] >= qe):
                    filled = (qi, qsd, qe, qa)
                    break
            if filled is not None:
                qi, qsd, qe, qa = filled
                rungs = []
                xb, xp, _ = resolve_bracket(s, b, qsd, qe, qa)
                out.append((int(s.ep[qi]), trade_r(s, qsd, qe, xp, qa), qi))
                pos_until = xb
                cool_upto = xb
                b = b + 1
                continue
        # new signal at bar b-1 (bar b's open scan)
        i = b - 1
        if i > cool_upto and w2ok(s, i):
            sd = int(s.side[i])
            if rungs and rungs[0][1] != sd:
                rungs = []                      # momentum flipped: thesis dead
            a = s.atr[i]
            rungs.append((i, sd, s.c[i] - OFFSET * a * sd, a, i + W))
            if len(rungs) > max_rungs:
                rungs.pop(0)                    # keep newest rungs
        b += 1
    return out


def strata(s):
    """Instrumented M0: control trades tagged re-arm-child (signal bar follows
    >=1 unfilled-signal rewind within W bars) + fill-bar stratum; and M1 tape
    tagged expiry-substitute (signal bar == prev unfilled signal + W)."""
    n = len(s.c)
    # --- control (M0 semantics) with rewind bookkeeping
    ctl = []
    last_unfilled = -10**9
    i = START
    while i < n - 1:
        sd = int(s.side[i])
        if sd == 0:
            i += 1
            continue
        a = s.atr[i]
        entry = s.c[i] - OFFSET * a * sd
        j = find_fill(s, sd, entry, i + 1, i + 3)      # validated window
        if j < 0:
            last_unfilled = i
            i += 1
            continue
        if np.isfinite(s.watr[i]) and s.watr[i] >= THR:
            child = (i - last_unfilled) <= 3            # re-arm child
            ctl.append((trade_r(s, sd, entry, resolve_bracket(s, j, sd, entry, a)[1], a),
                        child, j - i))
        i = max(resolve_bracket(s, j, sd, entry, a)[0] + 1, i + 1)
    # --- live M1 with substitute bookkeeping
    m1 = []
    last_exp = -10**9
    i = START
    while i < n - 1:
        if not w2ok(s, i):
            i += 1
            continue
        sd = int(s.side[i])
        a = s.atr[i]
        entry = s.c[i] - OFFSET * a * sd
        j = find_fill(s, sd, entry, i + 1, i + W)
        if j < 0:
            last_exp = i
            i = i + W
            continue
        sub = (i - last_exp) <= W                       # post-expiry substitute
        m1.append((trade_r(s, sd, entry, resolve_bracket(s, j, sd, entry, a)[1], a), sub))
        i = resolve_bracket(s, j, sd, entry, a)[0] + 1
    return ctl, m1


def report(name, tape):
    r = np.array([x[1] for x in tape])
    dl = daylist(sorted((x[0], x[1]) for x in tape))
    both, bust, med = challenge_mc(dl)
    print(f"  {name:34s}: n={len(r):5d} exp={r.mean():+.4f} win={(r > 0).mean():.1%} "
          f"| MC both={both:.1%} bust={bust:.1%} med={med}d")


def main():
    syms = {k: load(k) for k in TRIO}

    print("=== STRATA (where the pools live) ===")
    ctl_all, m1_all = [], []
    for k, s in syms.items():
        c, m = strata(s)
        ctl_all += c
        m1_all += m
    cr = np.array([(r, ch, fb) for (r, ch, fb) in ctl_all])
    child = cr[cr[:, 1] == 1][:, 0]
    plain = cr[cr[:, 1] == 0][:, 0]
    print(f"  control: re-arm children n={len(child)} exp={child.mean():+.4f} "
          f"| non-children n={len(plain)} exp={plain.mean():+.4f}")
    mr = np.array(m1_all)
    subs = mr[mr[:, 1] == 1][:, 0]
    nsubs = mr[mr[:, 1] == 0][:, 0]
    print(f"  live M1: expiry-substitutes n={len(subs)} exp={subs.mean():+.4f} "
          f"| others n={len(nsubs)} exp={nsubs.mean():+.4f}")

    print("\n=== RECOVERY ARMS (per-symbol, w=4, CONTAMINATED/exploratory) ===")
    base = []
    for k, s in syms.items():
        base += seq_s1(s, 0)
    report("M1 baseline (C=0)", base)
    for C in (1, 2, 4):
        tape = []
        for k, s in syms.items():
            tape += seq_s1(s, C)
        report(f"S1 post-expiry cooldown C={C}", tape)
    tape = []
    for k, s in syms.items():
        tape += seq_q2(s)
    report("Q2 untouched expiry re-place", tape)
    for rungs in (2, 3):
        tape = []
        for k, s in syms.items():
            tape += seq_ladder(s, rungs)
        report(f"L1 OCO ladder max_rungs={rungs}", tape)

    print("\nAll arms CONTAMINATED (derived from this data). Forward validation only.")


if __name__ == "__main__":
    main()
