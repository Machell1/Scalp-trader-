"""Candle-anatomy filter study — does SIGNAL-BAR wick/tail structure predict
per-trade R for the validated momentum-pullback engine?

Pre-registered: docs/CANDLE_SPEC_2026-07-10.md
  (SHA256 eec7e43b49eac8bce957ff3624af6361de0ef4ce76c277ddc05b42e1336d7b9f)
Origin: 2026-07-10 fishbone (US30 loss = terminal flush that looked like
continuation). Prior: entry filters 0-for-N on this EA — stated up front.

S1 information gate: per-feature Spearman IC vs per-trade R on the OOS window
(last 30%), pooled + per symbol, against a 200-permutation null envelope.
PASS = >=1 feature with pooled OOS |IC| beyond the 97.5th pct of its own null
AND same IC sign in >=8/12 symbols.  Fail => program ends, no EA change.
S2 (auto-runs only on S1 pass): 6 pre-registered drop-rule cells, paired vs
baseline, each must beat a matched RANDOM-DROP placebo (200 draws, >=95th pct)
with no per-symbol sign-flip. All joins on integer bar indexes (no datetimes).
"""
import glob
import os
import sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scalper_backtest as sb

RNG = np.random.default_rng(20260710)
FEATURES = ["adv_wick_atr", "adv_wick_frac", "clv_dir", "body_frac", "range_atr", "tail3_atr"]


def params(cost=0.03):
    return sb.Params(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
                     entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
                     stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
                     max_hold_bars=8, cost_atr_frac=cost)


def candle_features(o, h, l, c, atr, i, side):
    """All features use only bars <= i (info available at signal-bar close)."""
    rng = h[i] - l[i]
    if rng <= 0 or not np.isfinite(atr[i]) or atr[i] <= 0:
        return None
    body_top, body_bot = max(o[i], c[i]), min(o[i], c[i])
    up_wick, dn_wick = h[i] - body_top, body_bot - l[i]
    adv = up_wick if side > 0 else dn_wick          # wick AGAINST the continuation thesis
    clv = (c[i] - l[i]) / rng if side > 0 else (h[i] - c[i]) / rng
    tail3 = 0.0
    for k in (i, i - 1, i - 2):
        if k < 0:
            continue
        bt, bb = max(o[k], c[k]), min(o[k], c[k])
        tail3 += (h[k] - bt) if side > 0 else (bb - l[k])
    return dict(adv_wick_atr=adv / atr[i], adv_wick_frac=adv / rng, clv_dir=clv,
                body_frac=abs(c[i] - o[i]) / rng, range_atr=rng / atr[i],
                tail3_atr=tail3 / atr[i])


def load_all():
    """Per-symbol signal records with features; OOS flag = signal bar >= 0.7n."""
    rows = []
    p = params()
    for f in sorted(glob.glob(os.path.join(HERE, "data", "derivM15_spreadgated", "*.csv"))):
        sym = os.path.basename(f).replace(".csv", "").replace("_M15", "")
        df = pd.read_csv(f)
        ncols = {cn.lower(): cn for cn in df.columns}
        df = df.rename(columns={ncols[k]: k for k in ("time", "open", "high", "low", "close") if k in ncols})
        o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        atr = sb.wilder_atr(h, l, c, p.atr_period)
        n = len(df); split = int(0.7 * n)
        sigs = []
        sb.simulate_symbol(df, p, 0, n, signals_out=sigs)
        for (i, eb, side, r) in sigs:
            ft = candle_features(o, h, l, c, atr, i, side)
            if ft is None:
                continue
            ft.update(symbol=sym, sig_bar=i, side=side, r=r, oos=(i >= split))
            rows.append(ft)
        print(f"  {sym}: {len(sigs)} filled signals")
    return pd.DataFrame(rows)


def s1_gate(df):
    oos = df[df.oos].copy()
    print(f"\n==== S1 INFORMATION GATE (OOS only: {len(oos)} filled signals, {oos.symbol.nunique()} symbols) ====")
    print(f"{'feature':14s} {'pooled IC':>9s} {'null 2.5/97.5 pct':>18s} {'beyond?':>8s} {'sign agree':>10s}  verdict")
    passed = []
    for feat in FEATURES:
        x = oos[feat].to_numpy(); y = oos.r.to_numpy()
        ic = spearmanr(x, y).statistic
        # within-symbol permutation null (destroys feature-R link, keeps symbol mix)
        null = np.empty(200)
        for b in range(200):
            xp = oos.groupby("symbol")[feat].transform(lambda s: RNG.permutation(s.to_numpy()))
            null[b] = spearmanr(xp.to_numpy(), y).statistic
        lo_, hi_ = np.percentile(null, [2.5, 97.5])
        beyond = (ic < lo_) or (ic > hi_)
        per = oos.groupby("symbol", group_keys=False).apply(
            lambda g: spearmanr(g[feat], g.r).statistic if len(g) > 30 else np.nan,
            include_groups=False).dropna()
        agree = max((per > 0).sum(), (per < 0).sum())
        ok = beyond and agree >= 8
        if ok:
            passed.append(feat)
        print(f"{feat:14s} {ic:+9.4f} [{lo_:+7.4f},{hi_:+7.4f}] {str(beyond):>8s} {agree:>6d}/12   {'PASS' if ok else 'no'}")
    return passed


def s2_arms(df, passed):
    print("\n==== S2 FILTER ARMS (pre-registered cells) ====")
    oos = df[df.oos]
    base = oos.r.mean()
    cells = [("A1", "adv_wick_atr", ">", 0.30), ("A2", "adv_wick_atr", ">", 0.50),
             ("B1", "clv_dir", "<", 0.30), ("B2", "clv_dir", "<", 0.20),
             ("C1", "tail3_atr", ">", 0.75), ("C2", "tail3_atr", ">", 1.20)]
    print(f"baseline OOS: n={len(oos)} exp={base:+.4f}R")
    for name, feat, op, thr in cells:
        drop = (oos[feat] > thr) if op == ">" else (oos[feat] < thr)
        kept = oos[~drop]
        if drop.sum() < 30 or len(kept) < 200:
            print(f"{name} {feat}{op}{thr}: insufficient n (dropped {drop.sum()})")
            continue
        # random-drop placebo: same drop COUNT, random rows, 200 draws
        pl = np.empty(200)
        idx = np.arange(len(oos))
        for b in range(200):
            rd = RNG.choice(idx, size=int(drop.sum()), replace=False)
            pl[b] = oos.r.to_numpy()[np.setdiff1d(idx, rd)].mean()
        p95 = np.percentile(pl, 95)
        per = oos.assign(drop=drop).groupby("symbol", group_keys=False).apply(
            lambda g: g[~g["drop"]].r.mean() - g.r.mean(), include_groups=False)
        flips = (per < 0).sum()
        verdict = "CANDIDATE" if (kept.r.mean() > base and kept.r.mean() > p95 and flips <= 4) else "no"
        print(f"{name} {feat}{op}{thr}: dropped {drop.sum():4d} ({drop.mean():4.1%}) "
              f"droppedR={oos[drop].r.mean():+.4f} keptExp={kept.r.mean():+.4f} "
              f"placebo95={p95:+.4f} symWorse={flips}/12  {verdict}")


def main():
    print("loading + simulating 12 symbols (deployed v1.27 params, cost 0.03/side)")
    df = load_all()
    df.to_csv(os.path.join(HERE, "candle_signals.csv"), index=False)
    print(f"total filled signals: {len(df)} ({df.oos.sum()} OOS) -> candle_signals.csv")
    passed = s1_gate(df)
    if not passed:
        print("\n==== VERDICT: S1 FAIL — no candle feature carries OOS information beyond "
              "the permutation null with cross-symbol sign agreement. Program ends; no EA change. ====")
        return
    print(f"\nS1 PASS on {passed} -> running S2 arms")
    s2_arms(df, passed)
    print("\nS2 candidates (if any) still require walk-forward + DSR + 2x-cost before any EA flag.")


if __name__ == "__main__":
    main()
