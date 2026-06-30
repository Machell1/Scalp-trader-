"""Walk-forward + Deflated Sharpe on the spread-gated v1.2 universe (HANDOFF backlog #1).

Acceptance (HANDOFF.md):
  * Stitched out-of-sample expectancy > 0 at REAL per-instrument Deriv spread cost
  * DSR >= 0.95 (deflated for the breadth of prior research trials)
  * Walk-forward efficiency (OOS/IS exp) >= 0.30
  * Survives 2× cost stress (positive expectancy)
  * >= 60% of OOS calendar quarters positive

Source of truth: real Deriv M15 with spread column.
  python fetch_spreadgated.py   # MT5 must be open
  python walkforward_dsr.py

Does NOT use Yahoo proxy data.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np
import pandas as pd

import scalper_backtest as B
from scalper_backtest import wilder_atr, compute_stats
from scalper_confluence import CParams, simulate_symbol_c, rs_of
from experiment import EMC, n_eff_symbols, nppf, psr, stt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data", "derivM15_spreadgated")

# EA v1.2 spread-gated whitelist (12 majors, spread/ATR <= 0.05/side in deriv_realcost study)
SPREAD_GATED = [
    "BTCUSD", "ETHUSD", "XRPUSD", "SOLUSD",
    "US Tech 100", "US SP 500", "Wall Street 30", "US Small Cap 2000",
    "Germany 40", "UK 100", "Japan 225", "France 40",
]

# Validated v1.2 config (matches deriv_realcost.PINE and HANDOFF.md)
SHIPPED = dict(
    direction="cont",
    entry_style="limit",
    entry_offset_atr=0.6,
    pending_expiry_bars=3,
    stop_atr=1.0,
    tp_atr=3.0,
    lock_trigger_atr=0.25,
    trail_atr=0.5,
    max_hold_bars=8,
    momentum_bars=6,
    momentum_atr=2.0,
    atr_period=14,
)

# Prior research trials for DSR deflation (confluence grid + diverse geometry checks)
N_RESEARCH_TRIALS = 25


def sym_to_file(sym: str) -> str:
    return sym.replace(" ", "_") + ".csv"


def file_to_sym(fn: str) -> str:
    return os.path.splitext(fn)[0].replace("_", " ")


def real_cost_per_side(df: pd.DataFrame) -> float:
    """Per-side cost in ATR units: 0.5 * median(spread_price) / median(ATR)."""
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, SHIPPED["atr_period"])
    med_atr = float(np.nanmedian(atr))
    if med_atr <= 0:
        return float("nan")
    if "spread_price" in df.columns:
        spread_price = df["spread_price"].astype(float)
    elif "spread" in df.columns:
        spread_price = df["spread"].astype(float)
    else:
        return float("nan")
    med_spread = float(np.median(spread_price[np.isfinite(spread_price)]))
    return 0.5 * med_spread / med_atr


def load_spreadgated(data_dir: str | None = None) -> dict[str, pd.DataFrame]:
    root = data_dir or DATA_DIR
    data = {}
    for sym in SPREAD_GATED:
        path = os.path.join(root, sym_to_file(sym))
        if not os.path.isfile(path):
            continue
        df = pd.read_csv(path)
        if len(df) > 500:
            data[sym] = df
    return data


def collect_trades(
    data: dict[str, pd.DataFrame],
    costs: dict[str, float],
    lo: int | None = None,
    hi: int | None = None,
) -> pd.DataFrame:
    """Run simulator per symbol; return trade tape sorted by time."""
    recs = []
    p_base = CParams(**SHIPPED, block_overlap=True)
    for sym, df in data.items():
        cost = costs.get(sym, float("nan"))
        if not np.isfinite(cost):
            continue
        n = len(df)
        a, b = (0, n) if lo is None else (lo, hi if hi is not None else n)
        p = CParams(**{**p_base.__dict__, "cost_atr_frac": cost})
        tr, _ = simulate_symbol_c(df, p, a, b)
        times = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            recs.append((times[t["i"]], sym, float(t["r"])))
    if not recs:
        return pd.DataFrame(columns=["time", "sym", "r"])
    out = pd.DataFrame(recs, columns=["time", "sym", "r"]).sort_values("time")
    return out.reset_index(drop=True)


def quarter_walkforward(trades: pd.DataFrame, is_frac: float = 0.70):
    """Calendar-quarter walk-forward on a stitched trade tape.

    Returns dict with stitched IS/OOS arrays, per-quarter fold stats, WFE.
    """
    if trades.empty:
        return dict(is_r=np.array([]), oos_r=np.array([]), wfe=float("nan"), folds=[])

    t = trades.copy()
    t["q"] = pd.PeriodIndex(pd.to_datetime(t["time"]), freq="Q")
    quarters = sorted(t["q"].unique())
    if len(quarters) < 4:
        return dict(is_r=np.array([]), oos_r=np.array([]), wfe=float("nan"), folds=[])

    n_is = max(1, int(len(quarters) * is_frac))
    is_qs = set(quarters[:n_is])
    oos_qs = quarters[n_is:]

    is_r = t.loc[t["q"].isin(is_qs), "r"].to_numpy(float)
    oos_r = t.loc[t["q"].isin(oos_qs), "r"].to_numpy(float)

    # Rolling expanding-window WFE: each OOS quarter vs all prior trades
    folds = []
    wfe_vals = []
    for q in oos_qs:
        q_start = t.loc[t["q"] == q, "time"].min()
        is_fold = t.loc[t["time"] < q_start, "r"].to_numpy(float)
        oos_fold = t.loc[t["q"] == q, "r"].to_numpy(float)
        if is_fold.size < 30 or oos_fold.size < 3:
            continue
        is_exp = float(is_fold.mean())
        oos_exp = float(oos_fold.mean())
        wfe = oos_exp / is_exp if is_exp > 0 else float("nan")
        if np.isfinite(wfe):
            wfe_vals.append(wfe)
        folds.append(dict(q=str(q), n_is=is_fold.size, n_oos=oos_fold.size,
                          is_exp=is_exp, oos_exp=oos_exp, wfe=wfe))

    wfe_mean = float(np.mean(wfe_vals)) if wfe_vals else float("nan")
    return dict(is_r=is_r, oos_r=oos_r, wfe=wfe_mean, folds=folds, is_qs=is_qs, oos_qs=oos_qs)


def dsr_hurdle(n_trials: int = N_RESEARCH_TRIALS, trial_sharpes: list[float] | None = None,
              n_obs: int | None = None) -> float:
    """Expected max per-observation Sharpe under the null, for deflation.

    The null variance of the trial Sharpe estimates is what drives the hurdle. Best is the
    measured spread of the trials' Sharpes; absent that, use the SAMPLING variance of a
    single per-observation Sharpe under H0 (true SR=0), Var(SR_hat) ~= 1/(T-1). The old
    fixed 0.05^2 prior is ~4-5x too large for a ~12k-trade sample, which forces DSR->0
    regardless of a real edge."""
    if trial_sharpes and len(trial_sharpes) > 1:
        sr_arr = np.array([s for s in trial_sharpes if np.isfinite(s)], float)
        var_sr = float(np.var(sr_arr, ddof=1))
    elif n_obs and n_obs > 2:
        var_sr = 1.0 / (n_obs - 1)          # sampling variance of a per-trade Sharpe under H0
    else:
        var_sr = 0.05 ** 2                  # last-resort prior
    N = max(2, n_trials)
    z1 = nppf(1 - 1.0 / N)
    z2 = nppf(1 - 1.0 / N * math.exp(-1))
    return math.sqrt(var_sr) * ((1 - EMC) * z1 + EMC * z2)


def quarter_signs_from_trades(oos_r: np.ndarray, oos_times: pd.Series) -> tuple[int, int]:
    if oos_r.size == 0:
        return 0, 0
    s = pd.DataFrame({"t": oos_times, "r": oos_r})
    s["q"] = pd.PeriodIndex(pd.to_datetime(s["t"]), freq="Q")
    g = s.groupby("q")["r"].mean()
    return int((g > 0).sum()), int(len(g))


def per_symbol_oos(data, costs, is_frac=0.70):
    out = {}
    for sym, df in data.items():
        n = len(df)
        lo = int(n * is_frac)
        cost = costs[sym]
        p = CParams(**{**SHIPPED, "cost_atr_frac": cost, "block_overlap": True})
        tr, _ = simulate_symbol_c(df, p, lo, n)
        out[sym] = np.array(rs_of(tr), float)
    return out


def main():
    ap = argparse.ArgumentParser(description="Walk-forward + DSR on spread-gated universe")
    ap.add_argument("--is-frac", type=float, default=0.70, help="Fraction of calendar quarters used as IS")
    ap.add_argument("--data", default=DATA_DIR, help="Directory with spread CSVs")
    args = ap.parse_args()

    data = load_spreadgated(args.data)
    missing = [s for s in SPREAD_GATED if s not in data]
    if len(data) < 8:
        print(f"Need spread-gated CSVs in {args.data}/ ({len(data)}/{len(SPREAD_GATED)} found).", file=sys.stderr)
        if missing:
            print(f"  Missing: {', '.join(missing)}", file=sys.stderr)
        print("  Run: python fetch_spreadgated.py  (MT5 terminal open + logged in)", file=sys.stderr)
        sys.exit(1)

    # Per-instrument real spread cost (ATR units per side)
    costs = {}
    print(f"SPREAD-GATED UNIVERSE: {len(data)} instruments loaded from {args.data}\n")
    print(f"{'symbol':22s}{'cost/side':>10s}{'bars':>8s}{'from':>12s}{'to':>12s}")
    print("-" * 66)
    for sym, df in sorted(data.items()):
        c = real_cost_per_side(df)
        costs[sym] = c
        print(f"{sym:22s}{c:10.3f}{len(df):8d}{str(df.time.iloc[0])[:10]:>12s}{str(df.time.iloc[-1])[:10]:>12s}")

    bad = [s for s, c in costs.items() if not np.isfinite(c)]
    if bad:
        print(f"\nWARN: no spread cost for {bad} — re-fetch with fetch_spreadgated.py", file=sys.stderr)

    # Full-history trade tape at real cost
    trades = collect_trades(data, costs)
    wf = quarter_walkforward(trades, is_frac=args.is_frac)
    is_r, oos_r = wf["is_r"], wf["oos_r"]

    if oos_r.size < 50:
        print(f"\nERROR: only {oos_r.size} stitched OOS trades — need more history/quarters.", file=sys.stderr)
        sys.exit(1)

    # 2× cost stress — re-stitch OOS quarters at doubled per-side cost
    costs2 = {s: c * 2 for s, c in costs.items() if np.isfinite(c)}
    trades2x = collect_trades(data, costs2)
    if not trades2x.empty:
        trades2x["q"] = pd.PeriodIndex(pd.to_datetime(trades2x["time"]), freq="Q")
        oos_r_2x = trades2x.loc[trades2x["q"].isin(wf["oos_qs"]), "r"].to_numpy(float)
    else:
        oos_r_2x = np.array([])

    si, so = stt(is_r), stt(oos_r)
    so2 = stt(oos_r_2x)
    sr0 = dsr_hurdle(n_obs=oos_r.size)   # principled null SD from the OOS sample size
    dsr = psr(oos_r, sr0)

    pr, mean_r = n_eff_symbols(data)
    haircut = math.sqrt(pr / len(data))
    t_hair = so["t"] * haircut

    trades["q"] = pd.PeriodIndex(pd.to_datetime(trades["time"]), freq="Q")
    oos_mask = trades["q"].isin(wf["oos_qs"])
    qpos, qn = quarter_signs_from_trades(oos_r, trades.loc[oos_mask, "time"])

    ps = per_symbol_oos(data, costs, args.is_frac)
    pos_sym = sum(1 for a in ps.values() if a.size >= 10 and a.mean() > 0)
    tot_sym = sum(1 for a in ps.values() if a.size >= 10)

    wfe = wf["wfe"]
    gates = {
        "stitched OOS exp > 0 (real cost)": so["exp"] > 0,
        "DSR >= 0.95": np.isfinite(dsr) and dsr >= 0.95,
        "WFE >= 0.30": np.isfinite(wfe) and wfe >= 0.30,
        "2× cost stress OOS exp > 0": so2["exp"] > 0,
        "OOS quarters >= 60% positive": qn > 0 and qpos >= math.ceil(qn * 0.6),
        "breadth: >= 60% symbols positive": tot_sym > 0 and pos_sym >= math.ceil(tot_sym * 0.6),
        "powered sample N>=250": so["n"] >= 250,
    }
    verdict = "SHIP" if all(gates.values()) else ("WATCH" if so["exp"] > 0 else "NO-SHIP")

    print("\n" + "=" * 72)
    print("WALK-FORWARD + DSR — spread-gated v1.2 (HANDOFF backlog #1)")
    print("=" * 72)
    print(f"Config: pullback 0.6 ATR, exp 3, TP 3.0, no AVWAP")
    print(f"IS quarters: {len(wf['is_qs'])}  |  OOS quarters: {len(wf['oos_qs'])}  |  is_frac={args.is_frac}")
    print(f"N_eff symbols: {pr:.1f}  mean pairwise r={mean_r:.3f}  t-haircut x{haircut:.2f}")
    print(f"DSR hurdle sr0={sr0:.4f}  (deflated for N={N_RESEARCH_TRIALS} research trials)\n")

    print(f"{'slice':20s}{'N':>7s}{'exp':>9s}{'t':>7s}{'t_hc':>7s}{'win%':>7s}{'PF':>6s}{'totR':>9s}")
    print("-" * 72)
    s0t = stt(quarter_walkforward(collect_trades(data, {s: 0.0 for s in costs}), args.is_frac)["oos_r"])
    pf = compute_stats(oos_r).profit_factor
    print(f"{'IS (real cost)':20s}{si['n']:7d}{si['exp']:+9.4f}{si['t']:+7.2f}{'':>7s}{si['win']:6.1f}%{'':>6s}{si['tot']:+9.1f}")
    print(f"{'OOS stitched (REAL)':20s}{so['n']:7d}{so['exp']:+9.4f}{so['t']:+7.2f}{t_hair:+7.2f}{so['win']:6.1f}%{pf:6.2f}{so['tot']:+9.1f}")
    print(f"{'OOS frictionless':20s}{s0t['n']:7d}{s0t['exp']:+9.4f}{s0t['t']:+7.2f}{'':>7s}{s0t['win']:6.1f}%{'':>6s}{s0t['tot']:+9.1f}")
    print(f"{'OOS 2× cost stress':20s}{so2['n']:7d}{so2['exp']:+9.4f}{so2['t']:+7.2f}{'':>7s}{so2['win']:6.1f}%{'':>6s}{so2['tot']:+9.1f}")
    print(f"\nWFE (mean rolling OOS/IS exp): {wfe:.3f}")
    print(f"DSR (stitched OOS): {dsr:.3f}")
    print(f"OOS quarters positive: {qpos}/{qn}")
    print(f"Symbols positive (per-symbol 30% OOS): {pos_sym}/{tot_sym}")

    print("\n--- Per-quarter OOS folds (expanding IS) ---")
    for f in wf["folds"]:
        w = f"{f['wfe']:.2f}" if np.isfinite(f["wfe"]) else " nan"
        print(f"  {f['q']}  IS n={f['n_is']:5d} exp={f['is_exp']:+.4f}  "
              f"OOS n={f['n_oos']:4d} exp={f['oos_exp']:+.4f}  WFE={w}")

    print("\n--- Per-symbol OOS @ real cost (last 30% bars) ---")
    for sym in sorted(ps, key=lambda s: -ps[s].mean() if ps[s].size else -99):
        a = ps[sym]
        if a.size:
            print(f"  {sym:22s} N={a.size:4d}  exp={a.mean():+.4f}  win={(a>0).mean()*100:4.1f}%")

    print("\n--- SHIP gate ---")
    for name, passed in gates.items():
        mark = "PASS" if passed else "FAIL"
        print(f"  [{mark}] {name}")
    print(f"\n>>> VERDICT: {verdict}")
    if verdict == "SHIP":
        print("    Promote to small-size live on Deriv demo/real with spread gate enabled.")
    elif verdict == "WATCH":
        print("    Continue observe / minimum-size; edge positive but did not clear all gates.")
    else:
        print("    Do not promote; revisit config or universe.")

    return 0 if verdict != "NO-SHIP" else 2


if __name__ == "__main__":
    sys.exit(main())
