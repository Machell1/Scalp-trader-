"""Session-conditioning + VWAP overlay + ORB-retest screen.

Pre-registered: docs/SESSION_SPEC_2026-07-13.md
  (SHA256 c2154d5da38e90fa9180206984e6c50b794f8e07f347ecff2a285908cef61a7b)

Base = corrected live-parity enumeration with the LIVE v1.30 geometry
(bank 50% @ +1R, TP 2.0). Filters are true re-enumerations. SCREEN only.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nearmiss_decisions import daylist, challenge_mc
from parity_engine import prep_symbol, START
from scalper_backtest import anchored_vwap
from walkforward_dsr import real_cost_per_side
from retest_engine import TRIO, SPREAD_DIR, W

HOLDOUT = [("Germany_40", "derivM15_spreadgated"), ("US_SP_500", "derivM15_spreadgated"),
           ("UK_100", "derivM15_spreadgated"), ("France_40", "derivM15_spreadgated"),
           ("US_Small_Cap_2000", "derivM15_spreadgated"), ("Australia_200", "derivM15_diverse"),
           ("Hong_Kong_50", "derivM15_diverse"), ("EURUSD", "derivM15_diverse"),
           ("XAUUSD", "derivM15_diverse"), ("XAGUSD", "derivM15_diverse")]

THR = 0.30
BINS = 96


def load(key, sub="derivM15_spreadgated"):
    raw = pd.read_csv(os.path.join(HERE, "data", sub, key + ".csv"))
    cost = real_cost_per_side(raw)
    s = prep_symbol(raw, cost if np.isfinite(cost) else 0.03, key)
    nm = {c.lower(): c for c in raw.columns}
    df = raw.rename(columns={nm[k]: k for k in ("time", "open", "high", "low", "close") if k in nm})
    s.vwap = anchored_vwap(df)
    dt = pd.to_datetime(df["time"])
    if getattr(dt.dt, "tz", None) is not None:
        dt = dt.dt.tz_convert("UTC").dt.tz_localize(None)
    q = pd.PeriodIndex(dt, freq="Q")
    qs = sorted(q.unique())
    oq = set(qs[int(len(qs) * 0.7):])
    s.oos = np.array([qq in oq for qq in q])
    s.tod = ((s.ep % 86400) // 900).astype(int)
    # S-A: cash-open calibration = argmax median true range by time-of-day bin
    prev_c = np.roll(s.c, 1)
    prev_c[0] = s.c[0]
    tr = np.maximum(s.h - s.l, np.maximum(np.abs(s.h - prev_c), np.abs(s.l - prev_c)))
    med = np.array([np.median(tr[s.tod == b]) if (s.tod == b).sum() > 50 else 0.0
                    for b in range(BINS)])
    s.open_bin = int(np.argmax(med))
    return s


def in_window(s, i, kind):
    rel = (s.tod[i] - s.open_bin) % BINS
    if kind == "cash":
        return rel <= 25
    if kind == "opening":
        return rel <= 5
    if kind == "vwap":
        v = s.vwap[i]
        if not np.isfinite(v):
            return False
        return (s.c[i] > v) if s.side[i] > 0 else (s.c[i] < v)
    return True


def resolve_v130(s, j, sd, entry, a):
    """bank 50% @ +1R then TP2.0/SL1.0/hold8 — mirrors retest_engine.resolve."""
    risk = a
    sl = entry - risk * sd
    tp = entry + 2.0 * a * sd
    so = entry + 1.0 * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * s.cost * a / risk
    n = len(s.c)
    for k in range(j, min(j + 8, n)):
        if sd > 0:
            if s.l[k] <= sl:
                return k, banked + frac * (sl - entry) / risk - cost_r
            if not so_done and s.h[k] >= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.h[k] >= tp:
                return k, banked + frac * (tp - entry) / risk - cost_r
        else:
            if s.h[k] >= sl:
                return k, banked + frac * (entry - sl) / risk - cost_r
            if not so_done and s.l[k] <= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.l[k] <= tp:
                return k, banked + frac * (entry - tp) / risk - cost_r
    k = min(j + 8 - 1, n - 1)
    return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r


def run_v130(s, window_kind=None):
    """Live-parity per-symbol enumeration of the v1.30 config, optional filter."""
    out = []
    n = len(s.c)
    i = START
    while i < n - 1:
        ok = (s.side[i] != 0 and np.isfinite(s.watr[i]) and s.watr[i] >= THR)
        if ok and window_kind is not None:
            ok = in_window(s, i, window_kind)
        if not ok:
            i += 1
            continue
        sd = int(s.side[i])
        a = s.atr[i]
        entry = s.c[i] - 0.6 * a * sd
        j = -1
        for b in range(i + 1, min(i + 1 + W, n)):
            if (sd > 0 and s.l[b] <= entry) or (sd < 0 and s.h[b] >= entry):
                j = b
                break
        if j < 0:
            i = i + W
            continue
        xb, r = resolve_v130(s, j, sd, entry, a)
        out.append((int(s.ep[i]), r, bool(s.oos[i]), int((s.tod[i] - s.open_bin) % BINS)))
        i = xb + 1
    return out


def run_orb(s):
    """S-D ORB-retest: one trade per symbol-day, causal."""
    out = []
    n = len(s.c)
    day = s.ep // 86400
    i = START
    while i < n - 10:
        if s.tod[i] != s.open_bin:
            i += 1
            continue
        orh, orl = s.h[i], s.l[i]
        a = s.atr[i]
        if not np.isfinite(a) or a <= 0 or (orh - orl) > 2.5 * a:
            i += 1
            continue
        traded = False
        bo, sd = -1, 0
        for b in range(i + 1, min(i + 9, n)):
            if day[b] != day[i]:
                break
            if s.c[b] > orh:
                bo, sd = b, 1
                break
            if s.c[b] < orl:
                bo, sd = b, -1
                break
        if bo > 0:
            bound = orh if sd > 0 else orl
            for b in range(bo + 1, min(bo + 7, n)):
                if day[b] != day[i]:
                    break
                touched = (s.l[b] <= bound) if sd > 0 else (s.h[b] >= bound)
                closed_ok = (s.c[b] > bound) if sd > 0 else (s.c[b] < bound)
                if touched and closed_ok and b + 1 < n:
                    j = b + 1
                    entry = s.o[j]
                    stop = (s.l[b] - 0.5 * a) if sd > 0 else (s.h[b] + 0.5 * a)
                    risk = (entry - stop) * sd
                    if risk <= 0:
                        break
                    xb, r = resolve_orb(s, j, sd, entry, risk, a)
                    out.append((int(s.ep[i]), r, bool(s.oos[i]), 0))
                    traded = True
                    i = xb + 1
                    break
        if not traded:
            i += 1
    return out


def resolve_orb(s, j, sd, entry, risk, a_sig):
    sl = entry - risk * sd
    tp = entry + 2.0 * risk * sd
    so = entry + 1.0 * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * s.cost * a_sig / risk
    n = len(s.c)
    for k in range(j, min(j + 26, n)):
        if sd > 0:
            if s.l[k] <= sl:
                return k, banked + frac * (sl - entry) / risk - cost_r
            if not so_done and s.h[k] >= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.h[k] >= tp:
                return k, banked + frac * (tp - entry) / risk - cost_r
        else:
            if s.h[k] >= sl:
                return k, banked + frac * (entry - sl) / risk - cost_r
            if not so_done and s.l[k] <= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.l[k] <= tp:
                return k, banked + frac * (entry - tp) / risk - cost_r
    k = min(j + 26 - 1, n - 1)
    return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r


def report(tape, label):
    if not tape:
        print(f"  {label}: no trades")
        return None
    r = np.array([x[1] for x in tape])
    ro = np.array([x[1] for x in tape if x[2]])
    both, bust, med = challenge_mc(daylist(sorted((e, rr) for (e, rr, _, _) in tape)))
    print(f"  {label:26s}: n={len(r):5d} exp={r.mean():+.4f} "
          f"| OOS n={len(ro):4d} exp={(ro.mean() if len(ro) else float('nan')):+.4f} "
          f"| MC both={both:.1%} bust={bust:.1%}", flush=True)
    return r.mean()


def main():
    trio = [load(k) for k in TRIO]
    for s in trio:
        h = (s.open_bin * 15) // 60
        m = (s.open_bin * 15) % 60
        print(f"S-A {s.name}: cash-open bin={s.open_bin} ({h:02d}:{m:02d} server)")

    print("\nS-B bucket census (v1.30 geometry, unfiltered enumeration):")
    for s in trio:
        t = run_v130(s)
        arrs = {"OPENING": [], "CASH-REST": [], "OFF": []}
        for (e, r, o, rel) in t:
            k = "OPENING" if rel <= 5 else ("CASH-REST" if rel <= 25 else "OFF")
            arrs[k].append(r)
        row = " | ".join(f"{k} n={len(v)} exp={np.mean(v) if v else float('nan'):+.4f}"
                         for k, v in arrs.items())
        print(f"  {s.name:16s}: {row}")

    print("\nFiltered arms (true re-enumerations, trio pooled):")
    base = []
    for s in trio:
        base += run_v130(s)
    b = report(base, "BASE v1.30 (all hours)")
    for kind, label in (("cash", "S-C1 cash-session only"),
                        ("opening", "S-C2 opening 90min only"),
                        ("vwap", "S-C3 VWAP-hold overlay")):
        t = []
        for s in trio:
            t += run_v130(s, kind)
        report(t, label)

    print("\nS-D ORB-retest family (trio):")
    t = []
    for s in trio:
        t += run_orb(s)
    report(t, "ORB-retest")

    print("\nScreen only; alive-arm rule per spec (trio OOS delta >= +0.03, holdout consistent).")


if __name__ == "__main__":
    main()
