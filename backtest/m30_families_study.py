"""M30-native family discovery — Stage A tape kill-screen.

Pre-registered: docs/M30_FAMILIES_SPEC_2026-07-21.md
  (SHA256 6ac241541a1116898c5bf5798403a4d89966efea15e1ef6d924976765c54b2d0)

Six cells: A1/A2 session momentum, B1/B2 squeeze breakout, C1/C2 overnight
drift. E2 study currency (double cost). All cells reported; kill gates per
spec. No account MC here — survivors advance separately.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_m30h4_study import TF, agg  # reuse audited-mirror aggregation + costs
from run_h1_universe_screen import META_PATH
from snapshot_h1_universe_meta import SOURCE_TO_FTMO

SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
INDICES = ("Wall_Street_30", "US_Tech_100", "Japan_225")
BINS = 48


class Sym:
    def __init__(self, source, meta):
        self.source = source
        self.symbol = SOURCE_TO_FTMO[source]
        self.tf = TF(source, meta, 30)
        t = self.tf
        self.n = len(t.c)
        self.tod = ((t.ep % 86400) // 1800).astype(int)
        self.day = (t.ep // 86400).astype(int)
        prev_c = np.roll(t.c, 1)
        prev_c[0] = t.c[0]
        tr = np.maximum(t.h - t.l, np.maximum(np.abs(t.h - prev_c), np.abs(t.l - prev_c)))
        self.tr = tr
        med = np.array([np.median(tr[self.tod == b]) if (self.tod == b).sum() > 50 else 0.0
                        for b in range(BINS)])
        self.open_bin = int(np.argmax(med))
        dt = pd.to_datetime(self.tf.frame["time"])
        q = pd.PeriodIndex(dt, freq="Q")
        qs = sorted(q.unique())
        oq = set(qs[int(len(qs) * 0.7):])
        self.oos = np.array([qq in oq for qq in q])
        self.cost_e2 = t.cost_e1 * 2.0     # per side, E2

    def bar_at(self, day, tod_bin):
        idx = np.where((self.day == day) & (self.tod == tod_bin))[0]
        return int(idx[0]) if len(idx) else -1


def stats(rows, label, min_syms):
    if not rows:
        print(f"  {label}: no trades -> FAIL")
        return False
    df = pd.DataFrame(rows, columns=["source", "r", "oos", "extra"])
    r = df.r.to_numpy()
    ro = df[df.oos].r.to_numpy()
    sym_pos = sum(1 for _, g in df.groupby("source") if g.r.mean() > 0)
    n_sym = df.source.nunique()
    r4 = df.extra.to_numpy()  # 4x-cost stress r
    gates = dict(full=r.mean() > 0, oos=(len(ro) > 0 and ro.mean() > 0),
                 syms=sym_pos >= min_syms)
    ok = all(gates.values())
    print(f"  {label}: n={len(r):5d} expE2={r.mean():+.4f} win={(r > 0).mean():.1%} "
          f"| OOS n={len(ro)} exp={(ro.mean() if len(ro) else float('nan')):+.4f} "
          f"| syms+ {sym_pos}/{n_sym} | 4x-cost exp={r4.mean():+.4f} "
          f"| gates full={'Y' if gates['full'] else 'N'} oos={'Y' if gates['oos'] else 'N'} "
          f"syms={'Y' if gates['syms'] else 'N'} -> {'SURVIVE' if ok else 'FAIL'}")
    for src, g in df.groupby("source"):
        print(f"      {src:18s} n={len(g):4d} exp={g.r.mean():+.4f}")
    return ok


def family_a(syms, aligned):
    rows = []
    for s in syms:
        t = s.tf
        days = sorted(set(s.day.tolist()))
        prev_last_close = None
        for d in days:
            b0 = s.bar_at(d, s.open_bin)
            bt = s.bar_at(d, (s.open_bin + 12) % BINS)
            b_last = bt
            if b0 < 0 or bt < 0 or bt <= b0:
                if b0 >= 0:
                    end = s.bar_at(d, (s.open_bin + 12) % BINS)
                continue
            if prev_last_close is None:
                prev_last_close = t.c[bt]
                continue
            r1 = (t.c[b0] - prev_last_close) / prev_last_close
            side = 1 if r1 > 0 else (-1 if r1 < 0 else 0)
            if aligned and side != 0:
                r12 = t.c[bt - 1] - t.c[b0]
                if np.sign(r12) != side:
                    side = 0
            prev_last_close = t.c[bt]
            if side == 0:
                continue
            a = t.atr[bt]
            if not np.isfinite(a) or a <= 0:
                continue
            entry = t.o[bt]
            exitp = t.c[bt]
            gross = (exitp - entry) * side / a
            rows.append((s.source, gross - 2 * s.cost_e2, bool(s.oos[bt]),
                         gross - 4 * s.cost_e2))
    return rows


def family_b(syms, long_only):
    rows = []
    W, LOOK, ARM, HOLD = 16, 720, 8, 16
    for s in syms:
        t = s.tf
        rsum = pd.Series(s.tr).rolling(W).sum().to_numpy()
        i = LOOK + W
        while i < s.n - ARM - 1:
            rel = (s.tod[i] - s.open_bin) % BINS
            if rel > 12:                       # inside cash session only
                i += 1
                continue
            window = rsum[i - LOOK:i + 1]
            if not np.isfinite(rsum[i]) or rsum[i] > np.nanquantile(window, 0.20):
                i += 1
                continue
            hi = t.h[i - W + 1:i + 1].max()
            lo = t.l[i - W + 1:i + 1].min()
            a = t.atr[i]
            if not np.isfinite(a) or a <= 0 or (hi - lo) > 2.0 * a:
                i += 1
                continue
            fill, side = -1, 0
            for b in range(i + 1, min(i + 1 + ARM, s.n)):
                up = t.h[b] >= hi
                dn = t.l[b] <= lo
                if up and not (long_only and False):
                    fill, side = b, 1
                    break
                if dn and not long_only:
                    fill, side = b, -1
                    break
                if dn and long_only:
                    fill = -2          # short touch cancels in long-only
                    break
            if fill < 0:
                i += (ARM if fill == -1 else 1)
                continue
            entry = hi if side > 0 else lo
            risk = min(hi - lo, 1.5 * a)
            sl = entry - risk * side
            tp = entry + 2.0 * risk * side
            part = entry + 1.0 * risk * side
            banked, frac, part_done = 0.0, 1.0, False
            xb, xp = None, None
            for b in range(fill, min(fill + HOLD, s.n)):
                if side > 0:
                    if t.l[b] <= sl:
                        xb, xp = b, sl
                        break
                    if not part_done and t.h[b] >= part:
                        banked, frac, part_done = 0.5, 0.5, True
                    if t.h[b] >= tp:
                        xb, xp = b, tp
                        break
                else:
                    if t.h[b] >= sl:
                        xb, xp = b, sl
                        break
                    if not part_done and t.l[b] <= part:
                        banked, frac, part_done = 0.5, 0.5, True
                    if t.l[b] <= tp:
                        xb, xp = b, tp
                        break
            if xb is None:
                xb = min(fill + HOLD - 1, s.n - 1)
                xp = t.c[xb]
            gross = banked + frac * (xp - entry) * side / risk
            cost_r = 2 * s.cost_e2 * a / risk
            rows.append((s.source, gross - cost_r, bool(s.oos[i]),
                         gross - 2 * cost_r))
            i = xb + 1
    return rows


def family_c(syms, gated):
    rows = []
    for s in syms:
        t = s.tf
        days = sorted(set(s.day.tolist()))
        for di, d in enumerate(days[:-1]):
            bt = s.bar_at(d, (s.open_bin + 12) % BINS)
            b0d = s.bar_at(d, s.open_bin)
            if bt < 0 or b0d < 0:
                continue
            if gated and t.c[bt] < t.o[b0d]:
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
            gross = (t.o[nxt] - t.c[bt]) / a       # long only
            rows.append((s.source, gross - 2 * s.cost_e2, bool(s.oos[bt]),
                         gross - 4 * s.cost_e2))
    return rows


def main():
    chk = subprocess.run([sys.executable, str(HERE / "verify_data.py")],
                         capture_output=True, text=True)
    line = (chk.stdout + chk.stderr).strip().splitlines()[-1]
    print("verify_data:", line)
    assert "46 OK" in line
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    syms = [Sym(s, meta) for s in SOURCES]
    idx = [s for s in syms if s.source in INDICES]
    for s in syms:
        h = (s.open_bin * 30) // 60
        m = (s.open_bin * 30) % 60
        print(f"  {s.source}: open bin {s.open_bin} ({h:02d}:{m:02d} server), "
              f"cost/side E2 = {s.cost_e2:.4f} ATR(M30)")

    print("\n=== F-A session momentum ===")
    survivors = []
    if stats(family_a(syms, aligned=False), "A1 sign(r1)", 3):
        survivors.append("A1")
    if stats(family_a(syms, aligned=True), "A2 r1&r12 aligned", 3):
        survivors.append("A2")
    print("\n=== F-B squeeze breakout ===")
    if stats(family_b(syms, long_only=False), "B1 both sides", 3):
        survivors.append("B1")
    if stats(family_b(syms, long_only=True), "B2 long only", 3):
        survivors.append("B2")
    print("\n=== F-C overnight drift (indices, gross of swap) ===")
    if stats(family_c(idx, gated=False), "C1 unconditional", 2):
        survivors.append("C1")
    if stats(family_c(idx, gated=True), "C2 momentum-gated", 2):
        survivors.append("C2")

    print(f"\nStage-A survivors: {survivors if survivors else 'NONE'}")
    print("Survivors advance to the Stage-B paired account MC per spec.")


if __name__ == "__main__":
    main()
