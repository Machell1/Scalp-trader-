"""M30 families round 2 — Stage A (swap-net where applicable).

Pre-registered: docs/M30_FAMILIES_R2_SPEC_2026-07-21.md
  (SHA256 709a6bdd4370afb47e9525cbde0ac0fd394307ad7a5341bd7e74457e3a94c899)
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from m30_families_study import Sym, INDICES, SOURCES
from run_h1_universe_screen import META_PATH

SWAP_PRICE = {"Wall_Street_30": -11.2694, "US_Tech_100": -6.2145,
              "Japan_225": -8.2192}
BINS = 48


def overnight_rows(syms, avoid_friday):
    rows = []
    for s in syms:
        t = s.tf
        days = sorted(set(s.day.tolist()))
        for di, d in enumerate(days[:-1]):
            bt = s.bar_at(d, (s.open_bin + 12) % BINS)
            b0d = s.bar_at(d, s.open_bin)
            if bt < 0 or b0d < 0 or t.c[bt] < t.o[b0d]:
                continue
            nxt = -1
            for d2 in days[di + 1:di + 4]:
                cand = s.bar_at(d2, s.open_bin)
                if cand > bt:
                    nxt = cand
                    break
            if nxt < 0:
                continue
            a = t.atr[bt]
            if not np.isfinite(a) or a <= 0:
                continue
            nights, has_friday = 0.0, False
            for dd in range(int(t.ep[bt]) // 86400, int(t.ep[nxt]) // 86400):
                wd = pd.Timestamp(dd * 86400, unit="s").weekday()
                if wd == 4:
                    has_friday = True
                    nights += 3.0
                else:
                    nights += 1.0
            if avoid_friday and has_friday:
                continue
            swap_r = SWAP_PRICE[s.source] * nights / a
            gross = (t.o[nxt] - t.c[bt]) / a
            rows.append((s.source, gross - 2 * s.cost_e2 + swap_r, bool(s.oos[bt])))
    return rows


def squeeze_rows(syms):
    rows = []
    W, LOOK, ARM, HOLD = 16, 720, 8, 16
    for s in syms:
        t = s.tf
        rsum = pd.Series(s.tr).rolling(W).sum().to_numpy()
        i = LOOK + W
        while i < s.n - ARM - 1:
            rel = (s.tod[i] - s.open_bin) % BINS
            if rel > 12 or not np.isfinite(rsum[i]):
                i += 1
                continue
            window = rsum[i - LOOK:i + 1]
            if rsum[i] > np.nanquantile(window, 0.40):
                i += 1
                continue
            hi = t.h[i - W + 1:i + 1].max()
            lo = t.l[i - W + 1:i + 1].min()
            a = t.atr[i]
            if not np.isfinite(a) or a <= 0:
                i += 1
                continue
            fill, side = -1, 0
            for b in range(i + 1, min(i + 1 + ARM, s.n)):
                if t.h[b] >= hi:
                    fill, side = b, 1
                    break
                if t.l[b] <= lo:
                    fill, side = b, -1
                    break
            if fill < 0:
                i += ARM
                continue
            entry = hi if side > 0 else lo
            risk = min(hi - lo, 1.5 * a)
            if risk <= 0:
                i += 1
                continue
            sl = entry - risk * side
            tp = entry + 2.0 * risk * side
            part = entry + 1.0 * risk * side
            banked, frac, done = 0.0, 1.0, False
            xb, xp = None, None
            for b in range(fill, min(fill + HOLD, s.n)):
                if side > 0:
                    if t.l[b] <= sl:
                        xb, xp = b, sl
                        break
                    if not done and t.h[b] >= part:
                        banked, frac, done = 0.5, 0.5, True
                    if t.h[b] >= tp:
                        xb, xp = b, tp
                        break
                else:
                    if t.h[b] >= sl:
                        xb, xp = b, sl
                        break
                    if not done and t.l[b] <= part:
                        banked, frac, done = 0.5, 0.5, True
                    if t.l[b] <= tp:
                        xb, xp = b, tp
                        break
            if xb is None:
                xb = min(fill + HOLD - 1, s.n - 1)
                xp = t.c[xb]
            gross = banked + frac * (xp - entry) * side / risk
            cost_r = 2 * s.cost_e2 * a / risk
            rows.append((s.source, gross - cost_r, bool(s.oos[i])))
            i = xb + 1
    return rows


def report(rows, label, min_syms, min_n=0):
    if not rows:
        print(f"  {label}: no trades -> FAIL")
        return False
    df = pd.DataFrame(rows, columns=["source", "r", "oos"])
    r = df.r.to_numpy()
    ro = df[df.oos].r.to_numpy()
    sym_pos = sum(1 for _, g in df.groupby("source") if g.r.mean() > 0)
    n_sym = df.source.nunique()
    gates = dict(full=r.mean() > 0, oos=len(ro) > 0 and ro.mean() > 0,
                 syms=sym_pos >= min_syms, n=len(r) >= min_n)
    ok = all(gates.values())
    print(f"  {label}: n={len(r):5d} exp={r.mean():+.4f} win={(r > 0).mean():.1%} "
          f"| OOS n={len(ro)} exp={(ro.mean() if len(ro) else float('nan')):+.4f} "
          f"| syms+ {sym_pos}/{n_sym} | gates "
          + " ".join(f"{k}={'Y' if v else 'N'}" for k, v in gates.items())
          + f" -> {'SURVIVE' if ok else 'FAIL'}")
    for src, g in df.groupby("source"):
        print(f"      {src:18s} n={len(g):4d} exp={g.r.mean():+.4f}")
    return ok


def main():
    chk = subprocess.run([sys.executable, str(HERE / "verify_data.py")],
                         capture_output=True, text=True)
    line = (chk.stdout + chk.stderr).strip().splitlines()[-1]
    print("verify_data:", line)
    assert "46 OK" in line
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    all_idx = [Sym(s, meta) for s in INDICES]
    ex_us30 = [s for s in all_idx if s.source != "Wall_Street_30"]
    quartet = [Sym(s, meta) for s in SOURCES]

    survivors = []
    print("\n=== R2a overnight ex-US30 (swap-net) ===")
    if report(overnight_rows(ex_us30, avoid_friday=False), "R2a", 2):
        survivors.append("R2a")
    print("\n=== R2b overnight Friday-avoided (swap-net, 3 indices) ===")
    if report(overnight_rows(all_idx, avoid_friday=True), "R2b", 2):
        survivors.append("R2b")
    print("\n=== informational: ex-US30 AND Friday-avoided (no cell charged) ===")
    report(overnight_rows(ex_us30, avoid_friday=True), "R2a+R2b info", 2)
    print("\n=== R2c squeeze @40th pctile, cap removed (E2) ===")
    if report(squeeze_rows(quartet), "R2c", 3, min_n=200):
        survivors.append("R2c")

    print(f"\nRound-2 survivors: {survivors if survivors else 'NONE'}")


if __name__ == "__main__":
    main()
