"""Corrected-engine re-derivation: Stage-1 axis sweeps.

Pre-registered: docs/RETEST_SPEC_2026-07-12.md
  (SHA256 e7df76dfd077a1672abac3829505b5ba76b678204f036c241503986a1f7dc7a5)

Every cell runs under LIVE-PARITY enumeration (parity_engine primitives:
pre-entry filter, pending occupancy, window=4, re-arm i+window, cooldown
exit_bar+1). The bracket resolver mirrors simulate_symbol's management
semantics exactly (SL-before-TP intrabar using bar-start SL, end-of-bar
lock/trail ratchet, time exit at close of entry_bar+hold-1) and adds partial
scale-out. Exploratory SCREEN — all cells reported, promotions gate later.
"""
import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nearmiss_decisions import daylist, challenge_mc
from parity_engine import prep_symbol, START, EXPIRY
from walkforward_dsr import real_cost_per_side

SPREAD_DIR = os.path.join(HERE, "data", "derivM15_spreadgated")
TRIO = ["Wall_Street_30", "US_Tech_100", "Japan_225"]
W = 4  # live as-deployed pending window


@dataclass
class Cell:
    name: str
    filt: str = "W2"          # none | W2 | W3 | K3
    direction: str = "cont"   # cont | fade
    entry: str = "limit"      # limit | market | stop
    offset: float = 0.6       # limit/stop offset in ATR
    sl: float = 1.0
    tp: float = 3.0           # 0 = no TP
    hold: int = 8
    lock: float = 0.0         # lock trigger in R (0 = off)
    trail: float = 0.0        # trail distance in ATR (armed with lock)
    so_frac: float = 0.0      # scale-out fraction (0 = off)
    so_at: float = 0.0        # scale-out level in R


def filt_ok(s, i, filt):
    if s.side[i] == 0:
        return False
    if filt == "none":
        return True
    w = s.watr[i]
    if filt == "W2":
        return np.isfinite(w) and w >= 0.30
    if filt == "W3":
        return np.isfinite(w) and w >= 0.50
    if filt == "K3":   # drop clean-climax: wick < 0.20 AND body >= 0.70 of range
        rng = s.h[i] - s.l[i]
        body = abs(s.c[i] - s.o[i])
        clean = (np.isfinite(w) and w < 0.20) and (rng > 0 and body / rng >= 0.70)
        return not clean
    raise ValueError(filt)


def resolve(s, entry_bar, side, entry, a, cell):
    """Bracket with sim-parity management + optional partial scale-out.
    Returns (exit_bar, r_total)."""
    risk = cell.sl * a
    sl = entry - risk * side
    tp = entry + cell.tp * a * side if cell.tp > 0 else None
    lock_trig = cell.lock * risk if cell.lock > 0 else np.inf
    so_level = entry + cell.so_at * risk * side if cell.so_frac > 0 else None
    so_done = False
    r_banked = 0.0
    frac = 1.0
    n = len(s.c)
    cost_r = 2.0 * s.cost * a / risk

    def leg_r(px):
        return (px - entry) * side / risk

    exit_bar, exit_px = None, None
    for k in range(entry_bar, min(entry_bar + cell.hold, n)):
        hi, lo = s.h[k], s.l[k]
        # intrabar: SL first (pessimistic), then scale-out level vs TP ordering:
        # SL always first; then TP; scale-out checked before TP only if closer.
        if side > 0:
            if lo <= sl:
                exit_bar, exit_px = k, sl
                break
            if so_level is not None and not so_done and hi >= so_level:
                r_banked += cell.so_frac * leg_r(so_level)
                frac -= cell.so_frac
                so_done = True
            if tp is not None and hi >= tp:
                exit_bar, exit_px = k, tp
                break
        else:
            if hi >= sl:
                exit_bar, exit_px = k, sl
                break
            if so_level is not None and not so_done and lo <= so_level:
                r_banked += cell.so_frac * leg_r(so_level)
                frac -= cell.so_frac
                so_done = True
            if tp is not None and lo <= tp:
                exit_bar, exit_px = k, tp
                break
        # end-of-bar management (mirror simulate_symbol)
        price = s.c[k]
        profit = (price - entry) * side
        if profit >= lock_trig:
            if side > 0:
                sl = max(sl, entry)
                if cell.trail > 0:
                    sl = max(sl, price - cell.trail * a)
            else:
                sl = min(sl, entry)
                if cell.trail > 0:
                    sl = min(sl, price + cell.trail * a)
    if exit_bar is None:
        exit_bar = min(entry_bar + cell.hold - 1, n - 1)
        exit_px = s.c[exit_bar]
    r = r_banked + frac * leg_r(exit_px) - cost_r
    return exit_bar, r


def run_cell(s, cell):
    """Live-parity per-symbol enumeration for one cell."""
    out = []
    n = len(s.c)
    i = START
    while i < n - 1:
        if not filt_ok(s, i, cell.filt):
            i += 1
            continue
        mom = int(s.side[i])
        side = mom if cell.direction == "cont" else -mom
        a = s.atr[i]

        if cell.entry == "market":
            j = i + 1
            entry = s.o[j]
        else:
            if cell.entry == "limit":
                entry = s.c[i] - cell.offset * a * side
                touch = (lambda b: s.l[b] <= entry) if side > 0 else (lambda b: s.h[b] >= entry)
            else:  # stop breakout
                entry = s.c[i] + cell.offset * a * side
                touch = (lambda b: s.h[b] >= entry) if side > 0 else (lambda b: s.l[b] <= entry)
            j = -1
            for b in range(i + 1, min(i + 1 + W, n)):
                if touch(b):
                    j = b
                    break
            if j < 0:
                i = i + W          # live re-arm rule
                continue
        xb, r = resolve(s, j, side, entry, a, cell)
        out.append((int(s.ep[i]), r))
        i = xb + 1
    return out


def stats(tape, qmap):
    r = np.array([x[1] for x in tape])
    if len(r) == 0:
        return None
    oos = np.array([x[1] for x in tape if qmap[x[0]]])
    both, bust, med = challenge_mc(daylist(sorted(tape)))
    return dict(n=len(r), exp=r.mean(), win=(r > 0).mean(),
                n_oos=len(oos), oos=oos.mean() if len(oos) else np.nan,
                both=both, bust=bust, med=med)


def main():
    syms, qmaps = [], []
    for k in TRIO:
        raw = pd.read_csv(os.path.join(SPREAD_DIR, k + ".csv"))
        s = prep_symbol(raw, real_cost_per_side(raw), k)
        dt = pd.to_datetime(raw[[c for c in raw.columns if c.lower() == "time"][0]])
        q = pd.PeriodIndex(dt, freq="Q")
        qs = sorted(q.unique())
        oos_qs = set(qs[int(len(qs) * 0.7):])
        qmap = {int(e): (qq in oos_qs) for e, qq in zip(s.ep, q)}
        syms.append(s)
        qmaps.append(qmap)
    qall = {}
    for m in qmaps:
        qall.update(m)

    base = Cell("BASE cont/limit/W2/SL1/TP3/hold8")
    cells = [base]
    # filters
    for f in ("none", "W3", "K3"):
        cells.append(Cell(f"filter={f}", filt=f))
    # direction
    cells.append(Cell("fade (W2)", direction="fade"))
    cells.append(Cell("fade (none)", filt="none", direction="fade"))
    # entry styles (never contaminated by the pending artifact: market)
    cells.append(Cell("entry=market (W2)", entry="market"))
    cells.append(Cell("entry=market (none)", filt="none", entry="market"))
    cells.append(Cell("entry=stop 0.05 (W2)", entry="stop", offset=0.05))
    cells.append(Cell("entry=stop 0.05 (none)", filt="none", entry="stop", offset=0.05))
    # TP
    for tp in (1.5, 2.0, 2.5, 4.0):
        cells.append(Cell(f"TP={tp}", tp=tp))
    # hold
    for h in (4, 12, 16, 24):
        cells.append(Cell(f"hold={h}", hold=h))
    # SL
    for slv in (0.75, 1.5):
        cells.append(Cell(f"SL={slv}", sl=slv))
    # locks (the owner's high-water idea gets its honest test)
    for lk in (0.5, 1.0, 1.5, 2.0):
        cells.append(Cell(f"lock={lk}R", lock=lk))
    # lock+trail
    for lk, tr in ((0.5, 1.5), (1.0, 1.0), (1.0, 2.0)):
        cells.append(Cell(f"lock={lk}R trail={tr}ATR", lock=lk, trail=tr))
    # scale-outs (the owner's scale-out WATCH gets its honest test)
    for fr, at in ((0.5, 1.5), (0.5, 2.0), (0.33, 1.0)):
        cells.append(Cell(f"scaleout {int(fr*100)}%@{at}R", so_frac=fr, so_at=at))

    print(f"STAGE 1: {len(cells)} cells, live-parity enumeration w={W}, trio, real cost")
    print(f"{'cell':34s} {'n':>5s} {'exp':>8s} {'win':>6s} {'OOSn':>5s} {'OOS':>8s} {'both':>6s} {'bust':>6s} {'med':>4s}")
    rows = []
    for cell in cells:
        tape = []
        for s in syms:
            tape += run_cell(s, cell)
        st = stats(tape, qall)
        if st is None:
            print(f"{cell.name:34s}  EMPTY")
            continue
        rows.append((cell.name, st))
        print(f"{cell.name:34s} {st['n']:5d} {st['exp']:+8.4f} {st['win']:6.1%} "
              f"{st['n_oos']:5d} {st['oos']:+8.4f} {st['both']:6.1%} {st['bust']:6.1%} {st['med']:4d}",
              flush=True)

    print("\nStage-1 axis winners (OOS >= +0.03):")
    for name, st in rows:
        if np.isfinite(st['oos']) and st['oos'] >= 0.03:
            print(f"  {name}: OOS {st['oos']:+.4f} (n_oos={st['n_oos']}) both={st['both']:.1%}")
    print("\nScreen only — promotions need Stage 2 + full gate + forward validation.")


if __name__ == "__main__":
    main()
