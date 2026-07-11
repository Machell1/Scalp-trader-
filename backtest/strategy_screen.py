"""Screen five candle/wick strategy candidates as ADDITIONS to the desk.

Pre-registered: docs/STRATS_SCREEN_SPEC_2026-07-10.md
  (SHA256 0af1cc05acaadedd72cca17678d39e7d905efa86d7e3aaf748414b182ac6c16c)

Every cell must beat a random-entry control (same trade count + side mix, same
bracket) before anything else matters — entry engines fake edges on trends.
Survivors advance to the full 7-gate battery + live-engine overlap report.
"""
import math
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr, Params, simulate_symbol
from experiment import psr
from walkforward_dsr import load_spreadgated, real_cost_per_side, dsr_hurdle

RNG = np.random.default_rng(20260712)
N_TRIALS = 110
HOLD = 8
SL_ATR, TP_ATR = 1.0, 3.0


# ---------------------------------------------------------------- simulator
def simulate_signals(o, h, l, c, atr, signals, cost_side):
    """Engine-identical bracket replay for external (bar, side) signals.
    Entry at open of bar+1; SL/TP from entry using signal-bar ATR; pessimistic
    SL-first intrabar; time exit at close of entry_bar+HOLD-1; one at a time;
    cost = 2*cost_side*ATR per round turn. Returns list of (signal_bar, r)."""
    n = len(c)
    out = []
    busy_until = -1
    for (i, side) in signals:
        if i <= busy_until or i + 1 >= n:
            continue
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        entry_bar = i + 1
        entry = o[entry_bar]
        risk = SL_ATR * a
        sl = entry - side * risk
        tp = entry + side * TP_ATR * a
        exit_price = None
        exit_bar = entry_bar
        for k in range(entry_bar, min(entry_bar + HOLD, n)):
            if side > 0:
                if l[k] <= sl:
                    exit_price, exit_bar = sl, k; break
                if h[k] >= tp:
                    exit_price, exit_bar = tp, k; break
            else:
                if h[k] >= sl:
                    exit_price, exit_bar = sl, k; break
                if l[k] <= tp:
                    exit_price, exit_bar = tp, k; break
        if exit_price is None:
            exit_bar = min(entry_bar + HOLD - 1, n - 1)
            exit_price = c[exit_bar]
        gross = (exit_price - entry) * side
        r = (gross - 2 * cost_side * a) / risk
        out.append((i, r))
        busy_until = exit_bar
    return out


# ---------------------------------------------------------------- features
def wicks(o, h, l, c):
    body_top = np.maximum(o, c)
    body_bot = np.minimum(o, c)
    return h - body_top, body_bot - l   # upper, lower


# ---------------------------------------------------------------- strategies
def s1_wick_rejection(o, h, l, c, atr, wick_min):
    up, dn = wicks(o, h, l, c)
    sig = []
    n = len(c)
    for i in range(30, n - 1):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        imp = c[i - 3] - c[i - 9]                 # 6-bar impulse ending 3 bars ago
        if abs(imp) < 1.5 * a:
            continue
        D = 1 if imp > 0 else -1
        pull = c[i] - c[i - 3]                    # last-3-bar net move
        if D * pull > -0.3 * a:                   # must be a pullback against D
            continue
        anti = dn[i] if D > 0 else up[i]          # wick against D = rejection of the pullback
        rng = h[i] - l[i]
        if rng <= 0 or anti < wick_min * a:
            continue
        clv = (c[i] - l[i]) / rng if D > 0 else (h[i] - c[i]) / rng
        if clv < 0.6:                             # close in the D-ward 40%
            continue
        sig.append((i, D))
    return sig


def s2_pin_bar(o, h, l, c, atr, tail_min):
    up, dn = wicks(o, h, l, c)
    body = np.abs(c - o)
    sig = []
    for i in range(30, len(c) - 1):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        for N, tail in ((1, dn[i]), (-1, up[i])):
            if tail < tail_min * a or tail < 2.0 * max(body[i], 1e-12):
                continue
            if N * (c[i] - c[i - 6]) < 1.0 * a:   # momentum WITH the nose
                continue
            sig.append((i, N))
            break
    return sig


def s3_sweep_continuation(o, h, l, c, atr, poke_min):
    sig = []
    for i in range(40, len(c) - 1):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        move = c[i] - c[i - 12]
        if abs(move) < 1.5 * a:
            continue
        D = 1 if move > 0 else -1
        if D > 0:                                  # sweep = poke below the 20-bar low, close back inside
            ext = l[i - 20:i].min()
            if l[i] <= ext - poke_min * a and c[i] > ext:
                sig.append((i, D))
        else:
            ext = h[i - 20:i].max()
            if h[i] >= ext + poke_min * a and c[i] < ext:
                sig.append((i, D))
    return sig


def s4_candle_pullback(o, h, l, c, atr, engulf):
    sig = []
    n = len(c)
    for j in range(30, n - 6):
        a = atr[j]
        if not np.isfinite(a) or a <= 0:
            continue
        imp = c[j] - c[j - 5]
        if abs(imp) < 2.0 * a:
            continue
        D = 1 if imp > 0 else -1
        if D * (c[j] - o[j]) <= 0:                 # aligned signal candle (engine-style)
            continue
        seen_counter = False
        for i in range(j + 1, min(j + 5, n - 1)):
            if D * (c[i] - o[i]) < 0:
                seen_counter = True
                continue
            if seen_counter and D * (c[i] - o[i]) > 0:
                if engulf and not (abs(c[i] - o[i]) > abs(c[i - 1] - o[i - 1])
                                   and D * (c[i] - o[i - 1]) > 0):
                    break
                sig.append((i, D))
                break
    return sig


def s5_wick_pressure(o, h, l, c, atr, thr):
    up, dn = wicks(o, h, l, c)
    sig = []
    for i in range(30, len(c) - 1):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        press = float(np.sum(dn[i - 7:i + 1] - up[i - 7:i + 1])) / a
        if press >= thr:
            sig.append((i, 1))
        elif press <= -thr:
            sig.append((i, -1))
    return sig


CELLS = [
    ("S1a wick-reject 0.50", lambda O, H, L, C, A: s1_wick_rejection(O, H, L, C, A, 0.50)),
    ("S1b wick-reject 0.75", lambda O, H, L, C, A: s1_wick_rejection(O, H, L, C, A, 0.75)),
    ("S2a pin-bar 0.6", lambda O, H, L, C, A: s2_pin_bar(O, H, L, C, A, 0.6)),
    ("S2b pin-bar 1.0", lambda O, H, L, C, A: s2_pin_bar(O, H, L, C, A, 1.0)),
    ("S3a sweep 0.10", lambda O, H, L, C, A: s3_sweep_continuation(O, H, L, C, A, 0.10)),
    ("S3b sweep 0.25", lambda O, H, L, C, A: s3_sweep_continuation(O, H, L, C, A, 0.25)),
    ("S4a candle-pullback", lambda O, H, L, C, A: s4_candle_pullback(O, H, L, C, A, False)),
    ("S4b engulfing", lambda O, H, L, C, A: s4_candle_pullback(O, H, L, C, A, True)),
    ("S5a wick-pressure 1.5", lambda O, H, L, C, A: s5_wick_pressure(O, H, L, C, A, 1.5)),
    ("S5b wick-pressure 2.5", lambda O, H, L, C, A: s5_wick_pressure(O, H, L, C, A, 2.5)),
]


def live_engine_windows(df, cost):
    """Signal/holding windows of the LIVE engine (v1.29: W2-filtered) for overlap."""
    p = Params(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
               entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
               stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
               max_hold_bars=8, cost_atr_frac=cost)
    sigs = []
    simulate_symbol(df, p, 0, len(df), signals_out=sigs)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    up, dn = wicks(o, h, l, c)
    win = set()
    for (i, eb, side, r) in sigs:
        adv = (up[i] if side > 0 else dn[i]) / atr[i] if atr[i] > 0 else 0
        if adv < 0.30:                       # live W2 filter
            continue
        for k in range(i, eb + HOLD + 1):
            win.add(k)
    return win


def main():
    data = load_spreadgated()
    costs = {s: real_cost_per_side(df) for s, df in data.items()}
    print(f"{len(data)}/12 symbols | spec 0af1cc05 | trials ledger {N_TRIALS}\n")

    prep = {}
    for sym, df in data.items():
        o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        atr = wilder_atr(h, l, c, 14)
        t = pd.to_datetime(df["time"])
        q = pd.PeriodIndex(t, freq="Q")
        quarters = sorted(q.unique())
        oos_qs = set(quarters[int(len(quarters) * 0.7):])
        # hoisted: per-bar OOS mask + eligible random-control bars (computed ONCE,
        # not inside the 100-draw loop - the original placement was the bottleneck)
        oos_mask = np.array([qq in oos_qs for qq in q])
        elig = np.where(oos_mask)[0]
        elig = elig[(elig > 30) & (elig < len(c) - HOLD - 2)]
        prep[sym] = (o, h, l, c, atr, q, oos_qs, costs[sym], df, oos_mask, elig)

    results = []
    for name, gen in CELLS:
        rows = []
        for sym, (o, h, l, c, atr, q, oos_qs, cost, df, oos_mask, elig) in prep.items():
            sigs = gen(o, h, l, c, atr)
            side_of = dict(sigs)
            tr = simulate_signals(o, h, l, c, atr, sigs, cost)
            for (i, r) in tr:
                rows.append((sym, i, int(oos_mask[i]), r, side_of[i]))
        d = pd.DataFrame(rows, columns=["sym", "i", "oos", "r", "side"])
        oos = d[d.oos == 1]
        if len(oos) < 100:
            print(f"{name:24s} n_oos={len(oos):5d} -> too thin, dead")
            results.append((name, d, None))
            continue
        exp = oos.r.mean()
        # random-entry control: same per-symbol OOS trade count + side mix
        null = np.empty(100)
        grouped = list(oos.groupby("sym"))
        for b in range(100):
            vals = []
            for sym, g in grouped:
                o, h, l, c, atr, q, oos_qs, cost, df, oos_mask, elig = prep[sym]
                k = min(len(g), len(elig))
                bars = np.sort(RNG.choice(elig, size=k, replace=False))
                sides = RNG.permutation(g.side.to_numpy())[:k]
                vals += [r for _, r in simulate_signals(o, h, l, c, atr, list(zip(bars, sides)), cost)]
            null[b] = np.mean(vals) if vals else np.nan
        p95 = np.nanpercentile(null, 95)
        per = oos.groupby("sym").r.mean()
        pos = int((per > 0).sum())
        ok = (exp > 0) and (exp > p95) and (pos >= 7)
        print(f"{name:24s} n_oos={len(oos):5d} exp={exp:+.4f} rand95={p95:+.4f} "
              f"symbols+ {pos}/12 -> {'SCREEN PASS' if ok else 'dead'}")
        results.append((name, d, dict(exp=exp, p95=p95, pos=pos) if ok else None))

    survivors = [(n, d) for n, d, okd in results if okd]
    if not survivors:
        print("\n==== VERDICT: no cell survives the screen; nothing to add. ====")
        return

    print("\n==== FULL GATE for screen survivors ====")
    for name, d in survivors:
        oos = d[d.oos == 1]
        fr = oos.r.to_numpy(float)
        dsr = psr(fr, dsr_hurdle(n_trials=N_TRIALS, n_obs=fr.size))
        # 2x cost rerun
        rows2 = []
        gen = dict((n, g) for n, g in CELLS)[name]
        for sym, (o, h, l, c, atr, q, oos_qs, cost, df, oos_mask, elig) in prep.items():
            tr = simulate_signals(o, h, l, c, atr, gen(o, h, l, c, atr), cost * 2)
            rows2 += [r for (i, r) in tr if oos_mask[i]]
        exp2 = float(np.mean(rows2)) if rows2 else float("nan")
        # quarters
        qq = d[d.oos == 1].copy()
        sym_first = {s: prep[s] for s in qq.sym.unique()}
        qq["q"] = [str(prep[s][5][i]) for s, i in zip(qq.sym, qq.i)]
        qtab = qq.groupby("q").r.mean()
        qpos = int((qtab > 0).sum())
        # overlap vs live engine
        tot, inwin = 0, 0
        for sym, g in oos.groupby("sym"):
            win = live_engine_windows(prep[sym][8], prep[sym][7])
            tot += len(g)
            inwin += int(g.i.isin(win).sum())
        overlap = inwin / tot if tot else float("nan")
        gates = {
            "DSR>=0.95": np.isfinite(dsr) and dsr >= 0.95,
            "2xcost>0": np.isfinite(exp2) and exp2 > 0,
            "quarters>=60%": len(qtab) > 0 and qpos >= math.ceil(len(qtab) * 0.6),
            "n>=250": len(oos) >= 250,
        }
        verdict = "FULL PASS" if all(gates.values()) else "fails full gate"
        print(f"{name}: DSR={dsr:.3f} 2xcost={exp2:+.4f} quarters {qpos}/{len(qtab)} "
              f"n={len(oos)} overlap-with-live={overlap:.1%} -> {verdict}")
        print(f"   gates: {gates}")


if __name__ == "__main__":
    main()
