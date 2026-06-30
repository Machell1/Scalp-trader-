"""Ship-gate runner for the swing-strategy edge search (Daily/H4, TradingView
data). The Daily/H4 analogue of experiment.py — same statistical bar, applied
to genuinely different strategy families (see EDGE_SEARCH_PLAN.md).

Key difference from experiment.py's permutation test: there, "filter"
candidates were judged against random SUBSETS of an already-known-OK baseline
pool. Here the candidates are full entry mechanisms, so the right null is
RANDOM-TIMED ENTRIES run through the *identical* exit/risk machinery (same
stop_atr / trail_atr / tp_atr / max_hold_bars / cost). This matters: a
trailing-stop exit is asymmetric (cuts losers fast, lets winners run), so even
literally random entries can show a positive expectancy on trending markets
(verified empirically below) — the gate must show a candidate beats THAT null,
not just zero.
"""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pandas as pd

import swing_backtest as B
from swing_backtest import SParams

RNG = np.random.default_rng(20260630)
COST_REAL = 0.02
COST_STRESS = 0.04
EMC = 0.5772156649015329
N_NULL_DRAWS = 40  # random-entry null simulations per candidate (different seeds)

# Mirrors the M15 study's asset-class breakdown: a coarse class map used only to
# build optional universe-restriction candidates (e.g. "index+energy only").
ASSET_CLASS = {
    "EURUSD": "FX", "GBPUSD": "FX", "USDJPY": "FX", "AUDUSD": "FX", "USDCAD": "FX",
    "USDCHF": "FX", "NZDUSD": "FX", "EURJPY": "FX", "GBPJPY": "FX", "EURGBP": "FX", "AUDJPY": "FX",
    "XAUUSD": "METAL", "XAGUSD": "METAL", "XPTUSD": "METAL", "COPPER": "METAL",
    "WTI": "ENERGY", "BRENT": "ENERGY", "NATGAS": "ENERGY",
    "BTCUSD": "CRYPTO", "ETHUSD": "CRYPTO", "LTCUSD": "CRYPTO", "XRPUSD": "CRYPTO", "SOLUSD": "CRYPTO", "BCHUSD": "CRYPTO",
    "GER40": "INDEX", "UK100": "INDEX", "JPN225": "INDEX", "EU50": "INDEX", "AUS200": "INDEX", "HK50": "INDEX",
    "SPX500": "INDEX", "US30": "INDEX", "NAS100": "INDEX",
}


# ---------------------------------------------------------------------------
# normal cdf / inverse (Acklam) for PSR/DSR -- identical formulas to experiment.py
# ---------------------------------------------------------------------------
def ncdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def nppf(p):
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    pl = 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p <= 1 - pl:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)


def psr(r, sr0_per_obs):
    r = np.asarray(r, float)
    T = len(r)
    if T < 5 or r.std(ddof=1) == 0:
        return float("nan")
    sr = r.mean() / r.std(ddof=1)
    s = pd.Series(r)
    g3 = float(s.skew())
    g4 = float(s.kurtosis()) + 3.0
    denom = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4.0 * sr * sr))
    return ncdf((sr - sr0_per_obs) * math.sqrt(T - 1) / denom)


def stt(a):
    a = np.asarray(a, float)
    if a.size == 0:
        return dict(n=0, exp=0, t=0, win=0, tot=0, sd=0, sr=0)
    sd = a.std(ddof=1) if a.size > 1 else 0.0
    return dict(n=a.size, exp=a.mean(), t=(a.mean() / (sd / np.sqrt(a.size)) if sd > 0 else 0.0),
                win=(a > 0).mean() * 100, tot=a.sum(), sd=sd, sr=(a.mean() / sd if sd > 0 else 0.0))


def n_eff_symbols(data):
    rets = {}
    for sym, df in data.items():
        rets[sym] = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["time"])).pct_change()
    M = pd.concat(rets, axis=1).dropna(how="all")
    M = M.fillna(0.0)
    C = M.corr().to_numpy()
    ev = np.linalg.eigvalsh(C)
    ev = ev[ev > 0]
    pr = (ev.sum() ** 2) / (np.square(ev).sum())
    mean_r = (C.sum() - len(C)) / (len(C) * (len(C) - 1))
    return pr, mean_r


# ---------------------------------------------------------------------------
# Pooled run helpers
# ---------------------------------------------------------------------------
def pooled_split(data, p, split="oos"):
    per = {}
    trade_times = {}
    for sym, df in data.items():
        n = len(df)
        lo, hi = (0, int(n * 0.7)) if split == "is" else (int(n * 0.7), n) if split == "oos" else (0, n)
        tr = B.simulate_symbol(df, p, lo, hi)
        per[sym] = np.array(B.rs_of(tr), float)
        t = pd.to_datetime(df["time"]).to_numpy()
        trade_times[sym] = [t[trd["i"]] for trd in tr]
    pool = np.concatenate([a for a in per.values() if a.size]) if any(a.size for a in per.values()) else np.array([])
    return pool, per, trade_times


def quarter_signs(data, p, split="oos"):
    pool, per, times = pooled_split(data, p, split)
    recs = []
    for sym, arr in per.items():
        for r, t in zip(arr, times[sym]):
            recs.append((t, r))
    if not recs:
        return {}
    s = pd.DataFrame(recs, columns=["t", "r"])
    s["q"] = pd.PeriodIndex(pd.to_datetime(s["t"]), freq="Q")
    return {str(q): (g.r.mean(), len(g)) for q, g in s.groupby("q")}


def null_distribution(data, p, n_draws=N_NULL_DRAWS, split="oos"):
    """Random-entry null with IDENTICAL exit/risk machinery as candidate p,
    matched approximate trade frequency. Returns array of pooled OOS
    expectancies, one per random seed."""
    # Match the null's signal frequency to the candidate's observed trade
    # density so the comparison isn't confounded by trade count.
    cand_pool, _, _ = pooled_split(data, p, split)
    total_bars = sum(len(df) for df in data.values())
    target_n = max(30, len(cand_pool))
    rp = min(0.5, max(0.001, target_n / max(1, total_bars)))
    exps = []
    for d in range(n_draws):
        null_p = replace(p, family="random", random_p=rp, random_seed=20000 + d)
        pool, _, _ = pooled_split(data, null_p, split)
        exps.append(stt(pool)["exp"] if pool.size else 0.0)
    return np.array(exps)


def perm_p(cand_exp, null_exps):
    if null_exps.size == 0:
        return float("nan")
    return float((null_exps >= cand_exp).mean())


# ---------------------------------------------------------------------------
# Candidates (planned in EDGE_SEARCH_PLAN.md section 3-3.5)
# ---------------------------------------------------------------------------
CANDIDATES = [
    ("F1 donchian N20 trail3",      dict(family="donchian", don_entry_n=20, stop_atr=2.0, trail_atr=3.0, use_trail=True)),
    ("F1 donchian N55 trail3",      dict(family="donchian", don_entry_n=55, stop_atr=2.0, trail_atr=3.0, use_trail=True)),
    ("F1 donchian N20 turtle-exit", dict(family="donchian", don_entry_n=20, stop_atr=2.0, use_trail=False, use_don_exit=True, don_exit_n=10)),
    ("F1 donchian N20 long-only",   dict(family="donchian", don_entry_n=20, stop_atr=2.0, trail_atr=3.0, long_only=True)),
    ("F2 ema20/100 pb40",           dict(family="ema_pullback", ema_fast=20, ema_slow=100, pullback_th=40.0, stop_atr=2.0, trail_atr=3.0)),
    ("F2 ema20/100 pb50",           dict(family="ema_pullback", ema_fast=20, ema_slow=100, pullback_th=50.0, stop_atr=2.0, trail_atr=3.0)),
    ("F2 ema50/200 pb40",           dict(family="ema_pullback", ema_fast=50, ema_slow=200, pullback_th=40.0, stop_atr=2.0, trail_atr=3.0)),
    ("F3 squeeze .20 buf.1",        dict(family="squeeze", bb_width_pct_max=0.20, breakout_buffer_atr=0.1, stop_atr=2.0, trail_atr=3.0)),
    ("F3 squeeze .15 buf.2",        dict(family="squeeze", bb_width_pct_max=0.15, breakout_buffer_atr=0.2, stop_atr=2.0, trail_atr=3.0)),
    ("F4 rsi2 10/90 trend200",      dict(family="rsi2", rsi_entry_long=10.0, rsi_entry_short=90.0, stop_atr=2.5, trend_filter_sma=200)),
    ("F4 rsi2 5/95 trend200",       dict(family="rsi2", rsi_entry_long=5.0, rsi_entry_short=95.0, stop_atr=2.5, trend_filter_sma=200)),
    ("F4 rsi2 10/90 no-trend",      dict(family="rsi2", rsi_entry_long=10.0, rsi_entry_short=90.0, stop_atr=2.5, trend_filter_sma=0)),
    ("F5 random control",          dict(family="random", random_p=0.04, stop_atr=2.0, trail_atr=3.0)),
    # --- round 2: follow-ups on the round-1 leads (F4 rsi2+trend was "watch") ---
    ("F4 rsi2 5/95 trend100",        dict(family="rsi2", rsi_entry_long=5.0, rsi_entry_short=95.0, stop_atr=2.5, trend_filter_sma=100)),
    ("F4 rsi2 5/95 trend200 stop2.0", dict(family="rsi2", rsi_entry_long=5.0, rsi_entry_short=95.0, stop_atr=2.0, trend_filter_sma=200)),
    ("F4 rsi2 5/95 trend200 stop3.0", dict(family="rsi2", rsi_entry_long=5.0, rsi_entry_short=95.0, stop_atr=3.0, trend_filter_sma=200)),
    ("F4 rsi2 15/85 trend200",       dict(family="rsi2", rsi_entry_long=15.0, rsi_entry_short=85.0, stop_atr=2.5, trend_filter_sma=200)),
    ("F4 rsi2 5/95 trend200 long-only", dict(family="rsi2", rsi_entry_long=5.0, rsi_entry_short=95.0, stop_atr=2.5, trend_filter_sma=200, long_only=True)),
    ("F2 ema20/100 pb40 long-only",   dict(family="ema_pullback", ema_fast=20, ema_slow=100, pullback_th=40.0, stop_atr=2.0, trail_atr=3.0, long_only=True)),
    ("F3 squeeze .20 buf.1 long-only", dict(family="squeeze", bb_width_pct_max=0.20, breakout_buffer_atr=0.1, stop_atr=2.0, trail_atr=3.0, long_only=True)),
    # --- round 3: F4 was the only family to beat its matched-exit null; check
    # whether restricting to the asset classes where it works best (mirroring
    # the M15 study's crypto+index universe restriction) clears the gate ---
    ("F4 rsi2 5/95 trend200 idx+nrg", dict(family="rsi2", rsi_entry_long=5.0, rsi_entry_short=95.0, stop_atr=2.0, trend_filter_sma=200, _universe=("INDEX", "ENERGY"))),
    ("F4 rsi2 5/95 trend200 idx+nrg s2.5", dict(family="rsi2", rsi_entry_long=5.0, rsi_entry_short=95.0, stop_atr=2.5, trend_filter_sma=200, _universe=("INDEX", "ENERGY"))),
]


def mk(overrides, cost):
    ov = {k: v for k, v in overrides.items() if k != "_universe"}
    return SParams(**{**ov, "cost_atr_frac": cost})


def universe_data(data, overrides):
    classes = overrides.get("_universe")
    if not classes:
        return data
    return {s: df for s, df in data.items() if ASSET_CLASS.get(s) in classes}


def decide(r, sr0):
    so = r["so"]
    dsr = psr(r["oos_r"], sr0)
    gates = [
        so["exp"] > 0,
        (np.isfinite(r["pperm"]) and r["pperm"] < 0.05),
        (np.isfinite(r["wfe"]) and r["wfe"] >= 0.3),
        (np.isfinite(dsr) and dsr >= 0.95),
        (r["n_eff_tr"] >= 250 and so["exp"] > r["mde"]),
        r["exp2"] > 0,
        (r["qn"] > 0 and r["qpos"] >= math.ceil(r["qn"] * 0.6)),
    ]
    verdict = "SHIP" if all(gates) else ("watch" if (so["exp"] > 0 and r["pperm"] < 0.2) else "NO-SHIP")
    return dict(verdict=verdict, dsr=(dsr if np.isfinite(dsr) else 0.0), gates=gates)


def main(tf="D1"):
    full_data = B.load_dataset(tf)
    pr_full, mean_r = n_eff_symbols(full_data)
    haircut_full = math.sqrt(pr_full / len(full_data))
    print(f"TRADINGVIEW {tf}: {len(full_data)} symbols  mean pairwise r={mean_r:.3f}  N_eff(symbols)={pr_full:.2f}  -> t-haircut x{haircut_full:.2f}\n")

    rows = []
    trial_sr = []
    for label, ov in CANDIDATES:
        data = universe_data(full_data, ov)
        if ov.get("_universe"):
            pr, _ = n_eff_symbols(data)
            haircut = math.sqrt(pr / len(data))
        else:
            pr, haircut = pr_full, haircut_full

        oos, _, _ = pooled_split(data, mk(ov, COST_REAL), "oos")
        iss, _, _ = pooled_split(data, mk(ov, COST_REAL), "is")
        oos0, _, _ = pooled_split(data, mk(ov, 0.0), "oos")
        oos2, _, _ = pooled_split(data, mk(ov, COST_STRESS), "oos")
        so, si = stt(oos), stt(iss)
        wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else (float("nan") if so["exp"] <= 0 else float("inf"))

        null_exps = null_distribution(data, mk(ov, COST_REAL))
        pperm = perm_p(so["exp"], null_exps)

        t_hair = so["t"] * haircut
        n_eff_tr = so["n"] * (pr / len(data))
        mde = 1.3 * (1.96 + 0.84) / math.sqrt(max(1, n_eff_tr))

        qs = quarter_signs(data, mk(ov, COST_REAL), "oos")
        qpos = sum(1 for v in qs.values() if v[0] > 0)
        qn = len(qs)

        trial_sr.append(so["sr"])
        rows.append(dict(label=label, so=so, wfe=wfe, pperm=pperm, null_mean=null_exps.mean() if null_exps.size else 0.0,
                          t_hair=t_hair, n_eff_tr=n_eff_tr, mde=mde, exp0=stt(oos0)["exp"], exp2=stt(oos2)["exp"],
                          qpos=qpos, qn=qn, oos_r=oos))

    sr_arr = np.array([s for s in trial_sr if np.isfinite(s)])
    N = len(sr_arr)
    var_sr = float(np.var(sr_arr, ddof=1)) if N > 1 else 0.0
    z1 = nppf(1 - 1.0 / N) if N > 1 else 0.0
    z2 = nppf(1 - 1.0 / N * math.exp(-1)) if N > 1 else 0.0
    sr0 = math.sqrt(var_sr) * ((1 - EMC) * z1 + EMC * z2)
    print(f"DSR hurdle: searched N={N} cells; expected-max per-obs Sharpe under null = {sr0:.4f}\n")

    hdr = (f"{'candidate':28s}{'N':>6s}{'exp.02':>8s}{'t':>6s}{'t_hc':>6s}{'WFE':>6s}{'perm_p':>7s}"
           f"{'nullExp':>8s}{'exp0':>8s}{'exp.04':>8s}{'Qpos':>7s}{'DSR':>6s}  VERDICT")
    print(hdr)
    print("-" * len(hdr))
    for r in sorted(rows, key=lambda r: -r["so"]["exp"]):
        so = r["so"]
        ship = decide(r, sr0)
        wfe = f"{r['wfe']:6.2f}" if np.isfinite(r["wfe"]) else "   nan"
        pp = f"{r['pperm']:7.3f}" if np.isfinite(r["pperm"]) else "    -- "
        print(f"{r['label']:28s}{so['n']:6d}{so['exp']:+8.4f}{so['t']:+6.2f}{r['t_hair']:+6.2f}{wfe}{pp}"
              f"{r['null_mean']:+8.4f}{r['exp0']:+8.4f}{r['exp2']:+8.4f}{r['qpos']:4d}/{r['qn']:<2d}{ship['dsr']:6.2f}  {ship['verdict']}")
    print("\nLegend: exp.02=OOS expectancy at realistic cost; t_hc=breadth-haircut t; WFE=OOS/IS exp;")
    print("  perm_p=P(random-entry null with the SAME exit machinery >= candidate); nullExp=mean null OOS exp;")
    print("  exp0/exp.04=OOS exp frictionless/2x-cost stress; Qpos=OOS quarters positive; DSR>=0.95+all gates=>SHIP.")
    ship_rows = [r for r in rows if decide(r, sr0)["verdict"] == "SHIP"]
    watch_rows = [r for r in rows if decide(r, sr0)["verdict"] == "watch"]
    print(f"\n>>> SHIP: {len(ship_rows)} of {len(rows)} candidates." + ("" if ship_rows else "  (none cleared the ship gate)"))
    print(f">>> watch: {len(watch_rows)} of {len(rows)} candidates" + (f" ({', '.join(r['label'] for r in watch_rows)})" if watch_rows else ""))
    return rows, sr0


if __name__ == "__main__":
    import sys
    tf = sys.argv[1] if len(sys.argv) > 1 else "D1"
    main(tf)
