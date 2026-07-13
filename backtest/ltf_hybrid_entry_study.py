"""Multi-TF / hybrid entry reliability screen.

Pre-registered: docs/LTF_HYBRID_ENTRY_SPEC_2026-07-13.md
  (SHA256 3320f2889be9b29be944ac9da4c3f36d839f6ced928edc8cdd6b37ee75ae491f)

Yahoo proxy only — not gate-grade Deriv. Preserves pullback LIMIT + v1.30 exits.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
from scalper_backtest import wilder_atr

SYMBOLS = [
    "US30", "US100", "JP225", "USDJPY",
    "GER40", "FRA40", "UK100", "AUS200", "XAUUSD", "BTCUSD",
]
CORE = {"US30", "US100", "JP225", "USDJPY"}

WICK_THR = 0.30
MOM = 2.0
OFFSET = 0.6
STOP = 1.0
TP = 2.0
SO_FRAC = 0.50
SO_AT = 1.0


@dataclass
class Bars:
    name: str
    ep: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    atr: np.ndarray
    spread: np.ndarray


def load_bars(tf: str, name: str) -> Bars | None:
    path = os.path.join(HERE, "data", f"yahoo{tf}", f"{name}.csv")
    if not os.path.isfile(path):
        return None
    df = pd.read_csv(path)
    dt = pd.to_datetime(df["time"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
    ep = ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy(np.int64)
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    if "spread_price" in df.columns:
        spr = df["spread_price"].to_numpy(float)
    else:
        spr = np.full(len(c), float(np.nanmedian(c)) * 0.00015)
    return Bars(name, ep, o, h, l, c, atr, spr)


def impulse_sides(b: Bars, mb: int, mom: float = MOM):
    n = len(b.c)
    start = mb + 14 + 1
    move = np.full(n, np.nan)
    move[mb - 1 :] = b.c[: n - (mb - 1)] - b.c[mb - 1 :]
    with np.errstate(invalid="ignore", divide="ignore"):
        ma = move / b.atr
    valid = np.isfinite(b.atr) & (b.atr > 0) & (np.arange(n) >= start)
    falling = valid & (ma >= mom) & (b.c < b.o)
    rising = valid & (-ma >= mom) & (b.c > b.o)
    side = np.zeros(n, dtype=np.int8)
    side[falling] = -1
    side[rising] = 1
    up = b.h - np.maximum(b.o, b.c)
    dn = np.minimum(b.o, b.c) - b.l
    watr = np.full(n, np.nan)
    watr[rising] = up[rising] / b.atr[rising]
    watr[falling] = dn[falling] / b.atr[falling]
    return side, watr, start


def resolve_v130(h, l, c, j, sd, entry, a, hold, cost_side, buf=0.0):
    """bank 50%@1R, TP2, SL1, hold bars; stop-first; limit bank/TP need trade-through buf."""
    risk = STOP * a
    sl = entry - risk * sd
    tp = entry + TP * a * sd
    so = entry + SO_AT * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * cost_side / risk
    n = len(c)
    for k in range(j, min(j + hold, n)):
        if sd > 0:
            if l[k] <= sl:
                return k, banked + frac * (sl - entry) / risk - cost_r
            if not so_done and h[k] >= so + buf:
                banked += SO_FRAC
                frac -= SO_FRAC
                so_done = True
            if h[k] >= tp + buf:
                return k, banked + frac * (tp - entry) / risk - cost_r
        else:
            if h[k] >= sl:
                return k, banked + frac * (entry - sl) / risk - cost_r
            if not so_done and l[k] <= so - buf:
                banked += SO_FRAC
                frac -= SO_FRAC
                so_done = True
            if l[k] <= tp - buf:
                return k, banked + frac * (entry - tp) / risk - cost_r
    k = min(j + hold - 1, n - 1)
    return k, banked + frac * (c[k] - entry) * sd / risk - cost_r


def run_native(b: Bars, mb: int, pending: int, hold: int, stress=False, buf_frac=0.0):
    side, watr, start = impulse_sides(b, mb)
    out = []
    n = len(b.c)
    i = start
    while i < n - 1:
        sd = int(side[i])
        if sd == 0 or not (np.isfinite(watr[i]) and watr[i] >= WICK_THR):
            i += 1
            continue
        a = b.atr[i]
        if not np.isfinite(a) or a <= 0:
            i += 1
            continue
        cost_side = b.spread[i] * (2.0 if stress else 1.0)
        buf = buf_frac * a
        entry = b.c[i] - OFFSET * a * sd
        j = -1
        for t in range(i + 1, min(i + 1 + pending, n)):
            if sd > 0 and b.l[t] <= entry - buf:
                j = t
                break
            if sd < 0 and b.h[t] >= entry + buf:
                j = t
                break
        if j < 0:
            i = i + pending
            continue
        xb, r = resolve_v130(b.h, b.l, b.c, j, sd, entry, a, hold, cost_side, buf)
        out.append((int(b.ep[i]), float(r), i))
        i = xb + 1
    return out


def align_ltf_index(h1_ep: int, ltf_ep: np.ndarray) -> int:
    """First LTF bar with epoch > h1 signal close (≈ next LTF after H1 close)."""
    # H1 bar epoch is bar open; signal uses that bar's close → next LTF after open+3600
    target = h1_ep + 3600
    j = int(np.searchsorted(ltf_ep, target, side="left"))
    return j if j < len(ltf_ep) else -1


def run_hybrid(h1: Bars, ltf: Bars, pending_ltf: int, hold_ltf: int,
               confirm_wick: float = 0.0, stress=False, buf_frac=0.0):
    side, watr, start = impulse_sides(h1, 6)
    out = []
    n = len(h1.c)
    nl = len(ltf.c)
    i = start
    busy_until_ep = -1
    while i < n - 1:
        if h1.ep[i] <= busy_until_ep:
            i += 1
            continue
        sd = int(side[i])
        if sd == 0 or not (np.isfinite(watr[i]) and watr[i] >= WICK_THR):
            i += 1
            continue
        a = h1.atr[i]
        if not np.isfinite(a) or a <= 0:
            i += 1
            continue
        cost_side = h1.spread[i] * (2.0 if stress else 1.0)
        buf = buf_frac * a
        entry = h1.c[i] - OFFSET * a * sd
        j0 = align_ltf_index(int(h1.ep[i]), ltf.ep)
        if j0 < 0 or j0 >= nl - 1:
            i += 1
            continue
        j = -1
        for t in range(j0, min(j0 + pending_ltf, nl)):
            touched = (sd > 0 and ltf.l[t] <= entry - buf) or (sd < 0 and ltf.h[t] >= entry + buf)
            if not touched:
                continue
            if confirm_wick > 0:
                # contested touch: adverse wick on the fill bar relative to H1 ATR
                if sd > 0:
                    adv = min(ltf.o[t], ltf.c[t]) - ltf.l[t]
                else:
                    adv = ltf.h[t] - max(ltf.o[t], ltf.c[t])
                if adv < confirm_wick * a:
                    continue
            j = t
            break
        if j < 0:
            # occupy pending window wall-clock then re-arm
            busy_until_ep = int(h1.ep[i]) + pending_ltf * (ltf.ep[1] - ltf.ep[0] if nl > 1 else 900)
            i += 1
            continue
        xb, r = resolve_v130(ltf.h, ltf.l, ltf.c, j, sd, entry, a, hold_ltf, cost_side, buf)
        out.append((int(h1.ep[i]), float(r), i))
        busy_until_ep = int(ltf.ep[min(xb, nl - 1)])
        # advance H1 index past exit
        while i < n and h1.ep[i] <= busy_until_ep:
            i += 1
    return out


def summarize(rows, n_bars):
    if not rows:
        return dict(n=0, exp=float("nan"), win=float("nan"),
                    oos_n=0, oos_exp=float("nan"), oos_win=float("nan"))
    cut = int(n_bars * 0.7)
    r = np.asarray([x[1] for x in rows], float)
    oos = np.asarray([x[1] for x in rows if x[2] >= cut], float)
    return dict(
        n=int(len(r)),
        exp=float(r.mean()),
        win=float((r > 0).mean()),
        oos_n=int(len(oos)),
        oos_exp=float(oos.mean()) if len(oos) else float("nan"),
        oos_win=float((oos > 0).mean()) if len(oos) else float("nan"),
    )


def pooled(rows_by_sym, bars_by_sym):
    all_rows = []
    # OOS flag already encoded via bar index relative to each series length —
    # recompute with per-symbol cut stored as third element; summarize again
    # by stitching with artificial cut markers.
    full = []
    oos = []
    for sym, rows in rows_by_sym.items():
        cut = int(len(bars_by_sym[sym].c) * 0.7)
        for ep, r, i in rows:
            full.append(r)
            if i >= cut:
                oos.append(r)
    full = np.asarray(full, float)
    oos = np.asarray(oos, float)
    return dict(
        n=int(len(full)),
        exp=float(full.mean()) if len(full) else float("nan"),
        win=float((full > 0).mean()) if len(full) else float("nan"),
        oos_n=int(len(oos)),
        oos_exp=float(oos.mean()) if len(oos) else float("nan"),
        oos_win=float((oos > 0).mean()) if len(oos) else float("nan"),
        sym_oos_pos=sum(
            1 for sym, rows in rows_by_sym.items()
            if summarize(rows, len(bars_by_sym[sym].c))["oos_exp"] > 0
        ),
        n_sym=len(rows_by_sym),
    )


def main():
    cache = {}
    for tf in ("H1", "M15", "M5"):
        for sym in SYMBOLS:
            b = load_bars(tf, sym)
            if b is not None:
                cache[(tf, sym)] = b

    arms = []

    def add_native(name, tf, mb, pending, hold):
        arms.append(("native", name, tf, mb, pending, hold, 0.0))

    def add_hybrid(name, ltf, pending, hold, confirm):
        arms.append(("hybrid", name, ltf, pending, hold, confirm))

    add_native("H1_NATIVE", "H1", 6, 3, 8)
    add_native("M15_NATIVE", "M15", 6, 3, 8)
    add_native("M5_NATIVE", "M5", 6, 3, 8)
    add_native("M15_CLOCK", "M15", 24, 12, 32)
    add_native("M5_CLOCK", "M5", 72, 36, 96)
    add_hybrid("HYBRID_H1_M15", "M15", 12, 32, 0.0)
    add_hybrid("HYBRID_H1_M5", "M5", 36, 96, 0.0)
    add_hybrid("HYBRID_CONFIRM_M15", "M15", 12, 32, 0.15)
    add_hybrid("HYBRID_CONFIRM_M5", "M5", 36, 96, 0.15)

    results = {}
    for stress in (False, True):
        tag = "E2" if stress else "E1"
        for arm in arms:
            kind = arm[0]
            per = {}
            rows_by = {}
            bars_by = {}
            if kind == "native":
                _, name, tf, mb, pending, hold, _ = arm
                for sym in SYMBOLS:
                    b = cache.get((tf, sym))
                    if b is None:
                        continue
                    rows = run_native(b, mb, pending, hold, stress=stress, buf_frac=0.0)
                    per[sym] = summarize(rows, len(b.c))
                    rows_by[sym] = rows
                    bars_by[sym] = b
            else:
                _, name, ltf, pending, hold, confirm = arm
                for sym in SYMBOLS:
                    h1 = cache.get(("H1", sym))
                    lx = cache.get((ltf, sym))
                    if h1 is None or lx is None:
                        continue
                    # Restrict H1 to overlap with LTF availability for fair OOS
                    # (Yahoo M15/M5 only ~60d). Use full H1 signal history that
                    # overlaps LTF span.
                    lo, hi = int(lx.ep[0]), int(lx.ep[-1])
                    mask = (h1.ep >= lo - 7 * 3600) & (h1.ep <= hi)
                    if mask.sum() < 50:
                        continue
                    idx = np.where(mask)[0]
                    h1o = Bars(
                        h1.name, h1.ep[idx], h1.o[idx], h1.h[idx], h1.l[idx],
                        h1.c[idx], h1.atr[idx], h1.spread[idx],
                    )
                    rows = run_hybrid(h1o, lx, pending, hold, confirm_wick=confirm,
                                      stress=stress, buf_frac=0.0)
                    per[sym] = summarize(rows, len(h1o.c))
                    rows_by[sym] = rows
                    bars_by[sym] = h1o
            results[f"{tag}:{name}"] = {
                "per_symbol": per,
                "pooled": pooled(rows_by, bars_by),
                "core_pooled": pooled(
                    {k: v for k, v in rows_by.items() if k in CORE},
                    {k: v for k, v in bars_by.items() if k in CORE},
                ),
            }
            p = results[f"{tag}:{name}"]["pooled"]
            c = results[f"{tag}:{name}"]["core_pooled"]
            print(
                f"{tag:2} {name:22} pooled n={p['n']:4} exp={p['exp']:+.4f} "
                f"oos_n={p['oos_n']:3} oos={p['oos_exp']:+.4f} "
                f"sym+={p['sym_oos_pos']}/{p['n_sym']} | "
                f"core oos={c['oos_exp']:+.4f} n={c['oos_n']}"
            )

    out_path = os.path.join(HERE, "ltf_hybrid_entry_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
