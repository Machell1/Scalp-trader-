"""Crypto microstructure probe — alignment, features, and the information gate.

Pre-registered: docs/CRYPTO_MICRO_SPEC_2026-07-11.md
  (SHA256 8af19185498fa14cc7ced6adedcb902d82a5a37c7d1980d6528de03f3aeea734)
Real Binance BTCUSDT-perp microstructure vs the gate-grade Deriv BTCUSD W2 tape.
Steps: A) venue clock alignment (unambiguous peak required)  B) per-bar features
C) S1.5-analog gate: OOS Spearman IC vs 200-perm null + quarter stability +
fresh-beats-stale(24h) + n>=200. All failures reported verbatim.
"""
import glob
import io
import os
import sys
import zipfile

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr, Params, simulate_symbol
from walkforward_dsr import real_cost_per_side

DC = os.path.join(HERE, "data_crypto")
RNG = np.random.default_rng(20260715)
BAR = 900  # 15m seconds


def ep_s(series):
    dt = pd.to_datetime(series)
    return ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy()


def load_klines():
    rows = []
    for f in sorted(glob.glob(os.path.join(DC, "klines", "*.zip"))):
        with zipfile.ZipFile(f) as z:
            raw = z.read(z.namelist()[0])
        df = pd.read_csv(io.BytesIO(raw), header=None, comment="o")  # skip header line if present
        df = df[pd.to_numeric(df[0], errors="coerce").notna()]
        rows.append(pd.DataFrame({
            "ep": df[0].astype("int64") // 1000,
            "open": df[1].astype(float), "high": df[2].astype(float),
            "low": df[3].astype(float), "close": df[4].astype(float),
            "vol": df[5].astype(float), "taker_buy": df[9].astype(float)}))
    k = pd.concat(rows).drop_duplicates("ep").sort_values("ep").reset_index(drop=True)
    k["delta"] = 2 * k.taker_buy - k.vol
    return k


def load_metrics():
    rows = []
    for f in sorted(glob.glob(os.path.join(DC, "metrics", "*.zip"))):
        with zipfile.ZipFile(f) as z:
            raw = z.read(z.namelist()[0])
        df = pd.read_csv(io.BytesIO(raw))
        rows.append(pd.DataFrame({
            "ep": ep_s(df["create_time"]),
            "oi": df["sum_open_interest"].astype(float),
            "top_ls": df["sum_toptrader_long_short_ratio"].astype(float),
            "taker_ls": df["sum_taker_long_short_vol_ratio"].astype(float)}))
    m = pd.concat(rows).dropna().sort_values("ep").reset_index(drop=True)
    return m


def load_depth():
    rows = []
    for f in sorted(glob.glob(os.path.join(DC, "bookDepth", "*.zip"))):
        with zipfile.ZipFile(f) as z:
            raw = z.read(z.namelist()[0])
        df = pd.read_csv(io.BytesIO(raw))
        df["pct"] = pd.to_numeric(df["percentage"], errors="coerce").round().astype("Int64")
        df = df[df["pct"].isin([-5, -1, 1, 5])]
        if df.empty:
            continue
        df["ep"] = ep_s(df["timestamp"])
        df["bar"] = (df.ep // BAR) * BAR
        piv = df.pivot_table(index="bar", columns="pct", values="notional", aggfunc="last")
        piv.columns = [f"p{int(c)}" for c in piv.columns]
        piv = piv.reindex(columns=["p-5", "p-1", "p1", "p5"])
        rows.append(piv)
    d = pd.concat(rows)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d.reset_index().rename(columns={d.index.name or "index": "bar"})


def main():
    print("loading Binance archives...", flush=True)
    k = load_klines(); print(f"  klines: {len(k)} bars {pd.Timestamp(k.ep.min(), unit='s')} .. {pd.Timestamp(k.ep.max(), unit='s')}", flush=True)
    m = load_metrics(); print(f"  metrics: {len(m)} rows", flush=True)
    d = load_depth(); print(f"  depth: {len(d)} bar-snapshots, bands {sorted([c for c in d.columns if c != 'bar'])}", flush=True)

    print("loading Deriv BTCUSD tape...", flush=True)
    raw = pd.read_csv(os.path.join(HERE, "data", "derivM15_spreadgated", "BTCUSD.csv"))
    ncols = {c.lower(): c for c in raw.columns}
    df = raw.rename(columns={ncols[x]: x for x in ("time", "open", "high", "low", "close") if x in ncols})
    cost = real_cost_per_side(raw)
    dep = ep_s(df["time"])

    # ---- STEP A: venue clock alignment (pre-registered) ----
    kmap = pd.Series(k.close.to_numpy(), index=k.ep.to_numpy())
    dclose = pd.Series(df.close.to_numpy(), index=(dep // BAR) * BAR)
    best = []
    for lag in range(-16, 17):
        j = kmap.reindex(dclose.index + lag * BAR)
        a = np.log(dclose.to_numpy()[1:] / dclose.to_numpy()[:-1])
        b = np.log(j.to_numpy()[1:] / j.to_numpy()[:-1])
        ok = np.isfinite(a) & np.isfinite(b)
        c = np.corrcoef(a[ok], b[ok])[0, 1] if ok.sum() > 1000 else np.nan
        best.append((lag, c))
    best.sort(key=lambda x: -(x[1] if np.isfinite(x[1]) else -9))
    (l1, c1), (l2, c2) = best[0], best[1]
    print(f"ALIGNMENT: best lag {l1} bars (corr {c1:.4f}); runner-up lag {l2} (corr {c2:.4f})", flush=True)
    if not (abs(l1) <= 4 and c1 > 0.90 and (c1 - c2) > 0.10):
        print("ALIGNMENT AMBIGUOUS OR OUTSIDE PRE-REGISTERED WINDOW -> STOP (per spec)."); return
    OFF = l1 * BAR  # binance_ep = deriv_ep + OFF

    # ---- engine trades on Deriv BTC (W2-filtered), with side ----
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    up = h - np.maximum(o, c); dn = np.minimum(o, c) - l
    p = Params(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
               entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
               stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
               max_hold_bars=8, cost_atr_frac=cost)
    sigs = []
    simulate_symbol(df, p, 0, len(df), signals_out=sigs)
    q = pd.PeriodIndex(pd.to_datetime(df["time"]), freq="Q")
    qs = sorted(q.unique()); oos_qs = set(qs[int(len(qs) * 0.7):])

    # ---- STEP B: per-bar Binance feature frame ----
    k = k.set_index("ep")
    k["delta_frac"] = k.delta / k.vol.replace(0, np.nan)
    k["delta_z"] = (k.delta - k.delta.rolling(96).mean()) / k.delta.rolling(96).std()
    katr = wilder_atr(k.high.to_numpy(), k.low.to_numpy(), k.close.to_numpy(), 14)
    dens = k.vol / np.maximum((k.high - k.low) / np.where(katr > 0, katr, np.nan), 1e-9)
    k["absorb_z"] = (dens - dens.rolling(96).mean()) / dens.rolling(96).std()
    k["cvd6"] = k.delta.rolling(6).sum() / k.vol.rolling(6).sum().replace(0, np.nan)
    m = m.set_index("ep").sort_index()
    mo = m.reindex(m.index.union(k.index)).ffill().reindex(k.index)
    k["oi"] = mo.oi; k["top_ls"] = mo.top_ls; k["taker_ls"] = mo.taker_ls
    k["oi_chg_1h"] = k.oi.pct_change(4) * 100
    d = d.set_index("bar").sort_index()
    do = d.reindex(d.index.union(k.index)).ffill(limit=2).reindex(k.index)
    with np.errstate(all="ignore"):
        k["depth_imb1"] = (do["p-1"] - do["p1"]) / (do["p-1"] + do["p1"])
        k["depth_imb5"] = ((do["p-5"] - do["p5"]) / (do["p-5"] + do["p5"]))
        tot1 = do["p-1"] + do["p1"]
        k["depth_chg"] = tot1.pct_change(4) * 100

    FEATS = [("delta_frac", 1), ("delta_z", 1), ("cvd6", 1), ("absorb_z", 0),
             ("oi_chg_1h", 0), ("taker_ls", 1), ("top_ls", 1),
             ("depth_imb1", 1), ("depth_imb5", 1), ("depth_chg", 0)]

    rows = []
    for (i, eb, side, r) in sigs:
        if not (np.isfinite(atr[i]) and atr[i] > 0):
            continue
        if ((up[i] if side > 0 else dn[i]) / atr[i]) < 0.30:   # live W2 filter
            continue
        bep = (dep[i] // BAR) * BAR + OFF
        if bep not in k.index:
            continue
        rec = {"r": r, "oos": q[i] in oos_qs, "quarter": str(q[i])}
        krow = k.loc[bep]
        krow_stale = k.loc[bep - 96 * BAR] if (bep - 96 * BAR) in k.index else None
        for name, directional in FEATS:
            v = krow[name]
            rec[name] = side * v if directional else v
            sv = krow_stale[name] if krow_stale is not None else np.nan
            rec["stale_" + name] = side * sv if directional else sv
        rows.append(rec)
    t = pd.DataFrame(rows)
    oos = t[t.oos].copy()
    print(f"\nW2 BTC trades matched to Binance bars: {len(t)} total, {len(oos)} OOS", flush=True)

    print(f"\n==== INFORMATION GATE (OOS, spec 8af19185) ====", flush=True)
    print(f"{'feature':12s} {'n':>5s} {'IC':>8s} {'null97.5':>9s} {'beyond':>7s} {'qtr-stab':>8s} {'staleIC':>8s} {'fresh>stale':>11s}  verdict")
    passed = []
    for name, _ in FEATS:
        sub = oos[np.isfinite(oos[name])]
        n = len(sub)
        if n < 200:
            print(f"{name:12s} {n:5d}  -> insufficient n"); continue
        ic = spearmanr(sub[name], sub.r).statistic
        null = np.empty(200)
        vals = sub[name].to_numpy()
        for b in range(200):
            null[b] = spearmanr(RNG.permutation(vals), sub.r).statistic
        thr = np.percentile(np.abs(null), 97.5)
        beyond = abs(ic) > thr
        qtab = sub.groupby("quarter").apply(
            lambda g: spearmanr(g[name], g.r).statistic if len(g) > 20 else np.nan,
            include_groups=False).dropna()
        stab = (np.sign(qtab) == np.sign(ic)).mean() >= 0.6 if len(qtab) else False
        ssub = sub[np.isfinite(sub["stale_" + name])]
        sic = spearmanr(ssub["stale_" + name], ssub.r).statistic if len(ssub) > 100 else np.nan
        fresh = np.isfinite(sic) and abs(sic) <= 0.5 * abs(ic)
        ok = beyond and stab and fresh
        if ok:
            passed.append(name)
        print(f"{name:12s} {n:5d} {ic:+8.4f} {thr:9.4f} {str(beyond):>7s} {str(stab):>8s} "
              f"{sic if np.isfinite(sic) else float('nan'):+8.4f} {str(fresh):>11s}  {'PASS' if ok else 'no'}", flush=True)

    if passed:
        print(f"\n==== VERDICT: INFORMATION EXISTS in {passed} -> probe ADVANCES (S2 pre-registration next; ledger charges begin there) ====")
    else:
        print("\n==== VERDICT: no real-microstructure feature clears the gate — the 'cleaner data' thesis dies at $0 for this data tier. ====")


if __name__ == "__main__":
    main()
