"""Trade-through fill-realism robustness (harvest idea #1, MQL5 live-fill data:
59% of touched-but-not-crossed limits never filled).

Applies a trade-through buffer to EVERY limit-side fill our engine books
optimistically: the ENTRY limit, the TP limit, and the SCALE-OUT limit now
require price to trade THROUGH by buf = k*ATR14(signal). The protective STOP
keeps touch-fill (pessimistic against us). SCREEN-grade robustness column for
tonight's finalists; RETEST_SPEC e7df76df applies.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nearmiss_decisions import daylist, challenge_mc
from parity_engine import prep_symbol, START
from walkforward_dsr import real_cost_per_side
from retest_engine import TRIO, SPREAD_DIR, W

CELLS = [
    ("BASE bracket TP3", dict(tp=3.0, so_frac=0.0, so_at=0.0)),
    ("TP1.5 + so33@1R", dict(tp=1.5, so_frac=0.33, so_at=1.0)),
    ("so50@1R TP2.0", dict(tp=2.0, so_frac=0.50, so_at=1.0)),
]


def run(s, tp, so_frac, so_at, buf_frac, thr=0.30, sl_mult=1.0, hold=8, offset=0.6):
    out = []
    n = len(s.c)
    i = START
    while i < n - 1:
        if not (s.side[i] != 0 and np.isfinite(s.watr[i]) and s.watr[i] >= thr):
            i += 1
            continue
        sd = int(s.side[i])
        a = s.atr[i]
        buf = buf_frac * a
        entry = s.c[i] - offset * a * sd
        j = -1
        for b in range(i + 1, min(i + 1 + W, n)):
            if (sd > 0 and s.l[b] <= entry - buf) or (sd < 0 and s.h[b] >= entry + buf):
                j = b
                break
        if j < 0:
            i = i + W
            continue
        risk = sl_mult * a
        sl = entry - risk * sd
        tp_px = entry + tp * a * sd if tp > 0 else None
        so_px = entry + so_at * risk * sd if so_frac > 0 else None
        so_done = False
        r_banked, frac = 0.0, 1.0
        cost_r = 2.0 * s.cost * a / risk
        xb, xp = None, None
        for k in range(j, min(j + hold, n)):
            if sd > 0:
                if s.l[k] <= sl:
                    xb, xp = k, sl
                    break
                if so_px is not None and not so_done and s.h[k] >= so_px + buf:
                    r_banked += so_frac * (so_px - entry) * sd / risk
                    frac -= so_frac
                    so_done = True
                if tp_px is not None and s.h[k] >= tp_px + buf:
                    xb, xp = k, tp_px
                    break
            else:
                if s.h[k] >= sl:
                    xb, xp = k, sl
                    break
                if so_px is not None and not so_done and s.l[k] <= so_px - buf:
                    r_banked += so_frac * (so_px - entry) * sd / risk
                    frac -= so_frac
                    so_done = True
                if tp_px is not None and s.l[k] <= tp_px - buf:
                    xb, xp = k, tp_px
                    break
        if xb is None:
            xb = min(j + hold - 1, n - 1)
            xp = s.c[xb]
        r = r_banked + frac * (xp - entry) * sd / risk - cost_r
        out.append((int(s.ep[i]), r))
        i = xb + 1
    return out


def main():
    syms = []
    for k in TRIO:
        raw = pd.read_csv(os.path.join(SPREAD_DIR, k + ".csv"))
        syms.append(prep_symbol(raw, real_cost_per_side(raw), k))

    print("TRADE-THROUGH FILL REALISM (entry/TP/scale-out need trade-through; SL touch-fills)")
    print(f"{'cell':20s} {'buf':>6s} {'n':>6s} {'exp':>8s} {'win':>6s} {'both':>6s} {'bust':>6s}")
    for name, kw in CELLS:
        for buf in (0.0, 0.02, 0.05):
            tape = []
            for s in syms:
                tape += run(s, buf_frac=buf, **kw)
            r = np.array([x[1] for x in tape])
            both, bust, med = challenge_mc(daylist(sorted(tape)))
            print(f"{name:20s} {buf:6.2f} {len(r):6d} {r.mean():+8.4f} {(r > 0).mean():6.1%} "
                  f"{both:6.1%} {bust:6.1%}", flush=True)

    print("\nbuf=0.00 must reproduce tonight's numbers (consistency); 0.02/0.05 = realism stress.")


if __name__ == "__main__":
    main()
