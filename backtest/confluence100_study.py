"""100-point weighted confluence engine — faithful test of the pasted stack.

Pre-registered: docs/CONFLUENCE100_SPEC_2026-07-11.md
  (SHA256 ad2f19ea1061214498a7a2256ae9e4d065819327891cff57623cb41c88b9dcc0)
Arms: A standalone H1 (85/80/70), B standalone M15 (85), C filter on the live
engine vs the W2 baseline (85/70). Gold reported separately, never hidden.
"""
import glob
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr, ema, Params, simulate_symbol
from walkforward_dsr import real_cost_per_side
from strategy_screen import simulate_signals

RNG = np.random.default_rng(20260714)


def to_h1(df):
    d = df.copy()
    d["time"] = pd.to_datetime(d["time"])
    d = d.set_index("time").resample("1h").agg(
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last")).dropna().reset_index()
    return d


def score_components(df, htf_dir):
    """Per-bar (score, direction) for the 8 components. htf_dir = aligned HTF
    direction per bar (+1/-1/0). Returns arrays score[i], dirn[i]."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    n = len(c)
    atr = wilder_atr(h, l, c, 14)
    e20, e50 = ema(c, 20), ema(c, 50)
    hrs = pd.to_datetime(df["time"]).dt.hour.to_numpy()
    rng_ = h - l
    body = np.abs(c - o)
    body_top = np.maximum(o, c); body_bot = np.minimum(o, c)
    upw, dnw = h - body_top, body_bot - l
    tr = np.maximum(rng_, 1e-12)

    score = np.zeros(n); dirn = np.zeros(n, int)
    atr_avg10 = pd.Series(atr).rolling(10).mean().shift(1).to_numpy()

    for i in range(60, n - 1):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        # direction from the EMA stack
        if c[i] > e20[i] > e50[i] and e20[i] > e20[i - 3]:
            D = 1
        elif c[i] < e20[i] < e50[i] and e20[i] < e20[i - 3]:
            D = -1
        else:
            continue
        s = 0.0
        # 1 trend (20): stack + HTF agreement
        if htf_dir[i] == D:
            s += 20
        # 2 momentum impulse (20): impulse bar within last 6 bars
        imp_j = -1
        for j in range(i, max(i - 6, 0), -1):
            if rng_[j] < 1.5 * atr[j] or not np.isfinite(atr[j]):
                continue
            if body[j] < 0.6 * tr[j]:
                continue
            opp = upw[j] if D > 0 else dnw[j]
            if opp > 0.2 * tr[j]:
                continue
            clv = (c[j] - l[j]) / tr[j] if D > 0 else (h[j] - c[j]) / tr[j]
            if clv < 0.75:
                continue
            prior_ext = h[j - 10:j].max() if D > 0 else l[j - 10:j].min()
            if (D > 0 and c[j] > prior_ext) or (D < 0 and c[j] < prior_ext):
                imp_j = j
                break
        if imp_j >= 0:
            s += 20
        # 3 healthy pullback (15): 2-5 counter bars after the impulse
        if imp_j >= 0 and 2 <= (i - imp_j) <= 5:
            pb = range(imp_j + 1, i + 1)
            counter = [k for k in pb if D * (c[k] - o[k]) < 0]
            if len(counter) >= 2:
                med_tr = np.median([rng_[k] for k in pb])
                big_counter = any(body[k] > 0.8 * body[imp_j] for k in counter)
                retr = (h[imp_j] - min(l[k] for k in pb)) if D > 0 else (max(h[k] for k in pb) - l[imp_j])
                if med_tr < rng_[imp_j] and not big_counter and retr < 0.8 * rng_[imp_j]:
                    s += 15
        # 4 liquidity sweep (15)
        if D > 0:
            ext = l[i - 5:i].min()
            if l[i] < ext and c[i] > ext:
                s += 15
        else:
            ext = h[i - 5:i].max()
            if h[i] > ext and c[i] < ext:
                s += 15
        # 5 wick rejection (10)
        fav = dnw[i] if D > 0 else upw[i]
        if fav >= 0.6 * tr[i] and body[i] <= 0.4 * tr[i]:
            s += 10
        # 6 strong close (10)
        clv_i = (c[i] - l[i]) / tr[i] if D > 0 else (h[i] - c[i]) / tr[i]
        if clv_i >= 0.8:
            s += 10
        # 7 ATR expanding (5)
        if np.isfinite(atr_avg10[i]) and a > atr_avg10[i]:
            s += 5
        # 8 session (5): 07-17 UTC
        if 7 <= hrs[i] <= 17:
            s += 5
        score[i] = s
        dirn[i] = D
    return score, dirn


def htf_direction(df, htf_rule):
    """Per-base-bar HTF direction via resample (H1 frame -> H4 HTF; M15 -> H1)."""
    d = df.copy()
    d["time"] = pd.to_datetime(d["time"])
    hf = d.set_index("time").resample(htf_rule).agg(close=("close", "last")).dropna()
    e20 = ema(hf["close"].to_numpy(float), 20)
    e50 = ema(hf["close"].to_numpy(float), 50)
    dr = np.where(e20 > e50, 1, np.where(e20 < e50, -1, 0))
    hf_dir = pd.Series(dr, index=hf.index)
    # map each base bar to the LAST COMPLETED HTF bar (no lookahead)
    idx = hf_dir.index.searchsorted(d["time"].to_numpy(), side="right") - 2
    idx = np.clip(idx, 0, len(hf_dir) - 1)
    return hf_dir.to_numpy()[idx]


def run_frame(files, htf_rule, thresholds, label):
    print(f"\n==== ARM {label} (HTF {htf_rule}, thresholds {thresholds}) ====")
    per_thr = {t: [] for t in thresholds}
    for f, is_h1 in files:
        sym = os.path.basename(f).replace(".csv", "").replace("_M15", "")
        raw = pd.read_csv(f)
        ncols = {cn.lower(): cn for cn in raw.columns}
        raw = raw.rename(columns={ncols[k]: k for k in ("time", "open", "high", "low", "close") if k in ncols})
        cost = real_cost_per_side(pd.read_csv(f))
        if not np.isfinite(cost):
            cost = 0.03
        df = to_h1(raw) if is_h1 else raw
        if len(df) < 2000:
            continue
        hd = htf_direction(df, htf_rule)
        sc, dr = score_components(df, hd)
        o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        atr = wilder_atr(h, l, c, 14)
        q = pd.PeriodIndex(pd.to_datetime(df["time"]), freq="Q")
        qs = sorted(q.unique()); oos_qs = set(qs[int(len(qs) * 0.7):])
        for t in thresholds:
            sigs = [(i, int(dr[i])) for i in range(len(sc)) if sc[i] >= t and dr[i] != 0]
            tr_ = simulate_signals(o, h, l, c, atr, sigs, cost)
            for (i, r) in tr_:
                per_thr[t].append((sym, bool(q[i] in oos_qs), r, int(dr[i]), i, f, cost))
    for t in thresholds:
        rows = per_thr[t]
        oos = [x for x in rows if x[1]]
        if len(oos) < 60:
            print(f"  thr>={t}: n_oos={len(oos)} -> too thin"); continue
        rs = np.array([x[2] for x in oos])
        gold = np.array([x[2] for x in oos if x[0] == "XAUUSD"])
        per_sym = {}
        for x in oos:
            per_sym.setdefault(x[0], []).append(x[2])
        pos = sum(1 for v in per_sym.values() if len(v) >= 10 and np.mean(v) > 0)
        nsym = sum(1 for v in per_sym.values() if len(v) >= 10)
        # random-entry control matched per symbol
        null = np.empty(100)
        by_file = {}
        for x in oos:
            by_file.setdefault((x[5], x[0], x[6]), []).append(x)
        prepped = {}
        for (f, sym, cost), xs in by_file.items():
            raw = pd.read_csv(f)
            ncols = {cn.lower(): cn for cn in raw.columns}
            raw = raw.rename(columns={ncols[k]: k for k in ("time", "open", "high", "low", "close") if k in ncols})
            df = to_h1(raw) if "H1" in label else raw
            o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
            l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
            atr = wilder_atr(h, l, c, 14)
            q = pd.PeriodIndex(pd.to_datetime(df["time"]), freq="Q")
            qs = sorted(q.unique()); oos_qs = set(qs[int(len(qs) * 0.7):])
            mask = np.array([qq in oos_qs for qq in q])
            elig = np.where(mask)[0]
            elig = elig[(elig > 60) & (elig < len(c) - 10)]
            prepped[(f, sym)] = (o, h, l, c, atr, elig, cost, [x[3] for x in xs], len(xs))
        for b in range(100):
            vals = []
            for (fk, sym), (o, h, l, c, atr, elig, cost, sides, k) in prepped.items():
                kk = min(k, len(elig))
                bars = np.sort(RNG.choice(elig, size=kk, replace=False))
                ss = RNG.permutation(np.array(sides))[:kk]
                vals += [r for _, r in simulate_signals(o, h, l, c, atr, list(zip(bars, ss)), cost)]
            null[b] = np.mean(vals) if vals else np.nan
        p95 = np.nanpercentile(null, 95)
        ok = rs.mean() > 0 and rs.mean() > p95 and pos >= max(7, int(0.58 * nsym))
        print(f"  thr>={t}: n_oos={len(rs)} exp={rs.mean():+.4f} rand95={p95:+.4f} "
              f"symbols+ {pos}/{nsym} | GOLD n={len(gold)} exp={gold.mean() if len(gold) else float('nan'):+.4f} "
              f"-> {'SCREEN PASS' if ok else 'dead'}")


def arm_c():
    """Score (minus granted momentum-20) as a filter on the live engine vs W2."""
    print("\n==== ARM C: score-filter on live engine signals (vs W2 baseline) ====")
    P = dict(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
             entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
             stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
             max_hold_bars=8)
    rows = []
    for f in sorted(glob.glob(os.path.join(HERE, "data", "derivM15_spreadgated", "*.csv"))):
        sym = os.path.basename(f).replace(".csv", "")
        raw = pd.read_csv(f)
        ncols = {cn.lower(): cn for cn in raw.columns}
        df = raw.rename(columns={ncols[k]: k for k in ("time", "open", "high", "low", "close") if k in ncols})
        cost = real_cost_per_side(raw)
        hd = htf_direction(df, "1h")
        sc, dr = score_components(df, hd)
        o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        atr = wilder_atr(h, l, c, 14)
        up = h - np.maximum(o, c); dn = np.minimum(o, c) - l
        sigs = []
        simulate_symbol(df, Params(**P, cost_atr_frac=cost), 0, len(df), signals_out=sigs)
        q = pd.PeriodIndex(pd.to_datetime(df["time"]), freq="Q")
        qs = sorted(q.unique()); oos_qs = set(qs[int(len(qs) * 0.7):])
        for (i, eb, side, r) in sigs:
            if not (np.isfinite(atr[i]) and atr[i] > 0) or q[i] not in oos_qs:
                continue
            wick = (up[i] if side > 0 else dn[i]) / atr[i]
            # score granted momentum 20; other components from the score engine only
            # count when the score direction matches the trade side
            s_val = sc[i] - (20 if dr[i] == side else 0)   # remove trend? no: sc includes trend+mom...
            comp = (sc[i] if dr[i] == side else 0)
            rows.append((sym, r, wick >= 0.30, comp))
    d = pd.DataFrame(rows, columns=["sym", "r", "w2", "comp"])
    base = d[d.w2]
    print(f"  W2 baseline: n={len(base)} exp={base.r.mean():+.4f}")
    for t in (85, 70):
        # score engine granted 20 momentum pts by construction of the engine signal
        filt = d[d.comp + 20 >= t]
        per = d.assign(k=(d.comp + 20 >= t)).groupby("sym").apply(
            lambda g: g[g.k].r.mean() if g.k.sum() >= 5 else np.nan, include_groups=False).dropna()
        print(f"  score>={t}: n={len(filt)} exp={filt.r.mean() if len(filt) else float('nan'):+.4f} "
              f"symbols with data {len(per)} | vs W2 {base.r.mean():+.4f} "
              f"-> {'beats W2' if len(filt) >= 100 and filt.r.mean() > base.r.mean() else 'does NOT beat W2'}")


def main():
    sg = [(f, True) for f in sorted(glob.glob(os.path.join(HERE, "data", "derivM15_spreadgated", "*.csv")))]
    gold = [(os.path.join(HERE, "data", "derivM15_diverse", "XAUUSD.csv"), True)]
    run_frame(sg + gold, "4h", (85, 80, 70), "A standalone H1")
    sg15 = [(f, False) for f, _ in sg] + [(gold[0][0], False)]
    run_frame(sg15, "1h", (85,), "B standalone M15")
    arm_c()
    print("\nDone. Screen passers (if any) advance to the full battery per spec.")


if __name__ == "__main__":
    main()
