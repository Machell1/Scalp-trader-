"""Closed-loop edge discovery for the pullback momentum scalper.

Tests NEW hypotheses beyond the original 19-candidate grid (see docs/EDGE_PLAN.md).
Uses the same ship gate as experiment.py. Run after fetch_yahoo.py or fetch_diverse.py.

Usage:
  python fetch_yahoo.py          # proxy data on Linux
  python edge_loop.py            # default: yahooH1 (longer history)
  python edge_loop.py --tf derivM15_diverse   # real Deriv data when available
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np

import scalper_backtest as B
from scalper_confluence import CParams, simulate_symbol_c, rs_of
from experiment import COST_REAL, COST_STRESS, EMC, decide, n_eff_symbols, perm_test, pooled_oos, psr, stt

RNG = np.random.default_rng(20260630)

# Asset classes for universe filters (Yahoo + Deriv names)
CLASS = {
    **{s: "FX" for s in ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "NZDUSD",
                          "EURJPY", "GBPJPY", "EURGBP", "AUDJPY"]},
    **{s: "METAL" for s in ["XAUUSD", "XAGUSD", "XPTUSD", "XCUUSD"]},
    **{s: "ENERGY" for s in ["US_Oil", "UK_Brent_Oil", "NGAS"]},
    **{s: "CRYPTO" for s in ["BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD", "SOLUSD", "BCHUSD"]},
    **{s: "INDEX" for s in ["Germany_40", "UK_100", "Japan_225", "France_40",
                              "Australia_200", "Hong_Kong_50", "NDX", "SPX", "DJI"]},
}

BASE = dict(tp_atr=3.0, entry_style="stop", entry_offset_atr=0.05, pending_expiry_bars=2)

# Shipped config (v1.2): pullback 0.6, 4-bar expiry, no AVWAP
PULLBACK = dict(entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=4)
SHIPPED = {**PULLBACK, "tp_atr": 4.0}  # best WATCH combo from M15 crypto+index proxy

CANDIDATES = [
    # --- shipped / reference ---
    ("SHIPPED pull0.6 exp4 tp4", "geom", SHIPPED),
    ("baseline chase STOP", "geom", {}),
    ("pullback 0.6 exp4", "geom", PULLBACK),

    # --- A: geometry sweep ---
    ("pullback 0.4", "geom", {**PULLBACK, "entry_offset_atr": 0.4}),
    ("pullback 0.5", "geom", {**PULLBACK, "entry_offset_atr": 0.5}),
    ("pullback 0.7", "geom", {**PULLBACK, "entry_offset_atr": 0.7}),
    ("pullback 0.8", "geom", {**PULLBACK, "entry_offset_atr": 0.8}),
    ("pullback 0.6 exp2", "geom", {**PULLBACK, "pending_expiry_bars": 2}),
    ("pullback 0.6 exp3", "geom", {**PULLBACK, "pending_expiry_bars": 3}),

    # --- B: combos (no AVWAP — failed OOS) ---
    ("pull0.6 + ADX20", "filter", {**PULLBACK, "adx_min": 20.0}),
    ("pull0.6 + H1 EMA50", "filter", {**PULLBACK, "htf_minutes": 60, "htf_ema": 50}),
    ("pull0.6 + struct stop", "geom", {**PULLBACK, "stop_mode": "struct"}),

    # --- C: signal tuning ---
    ("pull0.6 mom4", "geom", {**PULLBACK, "momentum_bars": 4}),
    ("pull0.6 mom8", "geom", {**PULLBACK, "momentum_bars": 8}),
    ("pull0.6 atr1.5", "geom", {**PULLBACK, "momentum_atr": 1.5}),
    ("pull0.6 atr2.5", "geom", {**PULLBACK, "momentum_atr": 2.5}),
    ("pull0.6 tp2.5", "geom", {**PULLBACK, "tp_atr": 2.5}),
    ("pull0.6 tp4.0", "geom", {**PULLBACK, "tp_atr": 4.0}),
    ("pull0.6 stop0.8", "geom", {**PULLBACK, "stop_atr": 0.8}),
    ("pull0.6 stop1.5", "geom", {**PULLBACK, "stop_atr": 1.5}),

    # --- D: anti-thesis ---
    ("pull0.6 FADE", "geom", {**PULLBACK, "direction": "fade"}),
    ("pull0.6 MARKET", "geom", {**PULLBACK, "entry_style": "market", "entry_offset_atr": 0.0}),
]


def mk(overrides, cost):
    return CParams(**{**BASE, **overrides, "cost_atr_frac": cost})


def filter_universe(data: dict, classes: set[str]) -> dict:
    return {s: df for s, df in data.items() if CLASS.get(s, "?") in classes}


def run_grid(data: dict, candidates: list, haircut: float):
    base_oos = pooled_oos(data, mk({}, COST_REAL), "oos", block=True)[0]
    base_oos_nb = pooled_oos(data, mk({}, COST_REAL), "oos", block=False)[0]
    bs = stt(base_oos)
    print(f"BASELINE chase STOP  OOS cost{COST_REAL}: exp={bs['exp']:+.4f}  t={bs['t']:+.2f}  N={bs['n']}\n")

    rows = []
    for label, kind, ov in candidates:
        oos = pooled_oos(data, mk(ov, COST_REAL), "oos", block=True)[0]
        iss = pooled_oos(data, mk(ov, COST_REAL), "is", block=True)[0]
        oos0 = pooled_oos(data, mk(ov, 0.0), "oos", block=True)[0]
        oos2 = pooled_oos(data, mk(ov, COST_STRESS), "oos", block=True)[0]
        so, si = stt(oos), stt(iss)
        dExp = so["exp"] - bs["exp"]
        dTot = so["tot"] - bs["tot"]
        wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else float("nan")
        if kind == "filter":
            kept_nb = pooled_oos(data, mk(ov, COST_REAL), "oos", block=False)[0]
            pperm = perm_test(base_oos_nb, kept_nb)
        else:
            pperm = float("nan")
        t_hair = so["t"] * haircut
        n_eff_tr = so["n"] * (haircut ** 2)  # rough trade-level haircut
        mde = 1.3 * (1.96 + 0.84) / math.sqrt(max(1, n_eff_tr))
        # quarter signs
        from experiment import quarter_signs
        qs = quarter_signs(data, mk(ov, COST_REAL), COST_REAL)
        qpos = sum(1 for v in qs.values() if v[0] > 0)
        qn = len(qs)
        rows.append(dict(label=label, kind=kind, so=so, dExp=dExp, dTot=dTot, wfe=wfe,
                         pperm=pperm, t_hair=t_hair, n_eff_tr=n_eff_tr, mde=mde,
                         exp0=stt(oos0)["exp"], exp2=stt(oos2)["exp"], qpos=qpos, qn=qn,
                         oos_r=oos))

    # DSR hurdle
    sr_arr = np.array([r["so"]["sr"] for r in rows if np.isfinite(r["so"]["sr"])])
    N = len(sr_arr)
    var_sr = float(np.var(sr_arr, ddof=1)) if N > 1 else 0.0
    from experiment import nppf
    z1 = nppf(1 - 1.0 / max(N, 1))
    z2 = nppf(1 - 1.0 / max(N, 1) * math.exp(-1))
    sr0 = math.sqrt(var_sr) * ((1 - EMC) * z1 + EMC * z2) if var_sr > 0 else 0.0

    hdr = (f"{'candidate':28s}{'kind':7s}{'N':>6s}{'exp.02':>8s}{'dExp':>8s}{'t_hc':>7s}"
           f"{'WFE':>6s}{'exp0':>8s}{'exp.04':>8s}{'Q':>5s}  VERDICT")
    print(hdr)
    print("-" * len(hdr))
    for r in sorted(rows, key=lambda x: -x["dExp"]):
        so = r["so"]
        ship = decide(r, sr0)
        wfe = f"{r['wfe']:6.2f}" if np.isfinite(r["wfe"]) else "   nan"
        print(f"{r['label']:28s}{r['kind']:7s}{so['n']:6d}{so['exp']:+8.4f}{r['dExp']:+8.4f}"
              f"{r['t_hair']:+7.2f}{wfe}{r['exp0']:+8.4f}{r['exp2']:+8.4f}"
              f"{r['qpos']:2d}/{r['qn']:<2d}  {ship['verdict']}")

    ships = [r for r in rows if decide(r, sr0)["verdict"] == "SHIP"]
    watches = [r for r in rows if decide(r, sr0)["verdict"] == "watch"]
    print(f"\n>>> SHIP: {len(ships)}  WATCH: {len(watches)}  NO-SHIP: {len(rows) - len(ships) - len(watches)}")
    if ships:
        print("\nPromote these configs to TradingView + EA:")
        for r in ships:
            print(f"  * {r['label']}: exp={r['so']['exp']:+.4f}R  t_hc={r['t_hair']:+.2f}")
    elif watches:
        best = max(watches, key=lambda r: r["so"]["exp"])
        print(f"\nBest WATCH candidate: {best['label']}  exp={best['so']['exp']:+.4f}R  dExp={best['dExp']:+.4f}")
    return rows, ships


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="yahooH1", help="dataset folder under data/")
    ap.add_argument("--universe", default="all", choices=["all", "crypto_index"],
                    help="restrict to crypto+index symbols")
    args = ap.parse_args()

    data = B.load_dataset(args.tf)
    if not data:
        print(f"No data in data/{args.tf}/. Run: python fetch_yahoo.py", file=sys.stderr)
        sys.exit(1)

    if args.universe == "crypto_index":
        data = filter_universe(data, {"CRYPTO", "INDEX"})
        print(f"Universe filter: crypto + index ({len(data)} symbols)")

    pr, mean_r = n_eff_symbols(data)
    haircut = math.sqrt(pr / len(data))
    print(f"Dataset: {args.tf}  {len(data)} symbols  mean r={mean_r:.3f}  N_eff={pr:.1f}  haircut x{haircut:.2f}\n")

    run_grid(data, CANDIDATES, haircut)

    # Second pass: best geometry on restricted universe
    if args.universe == "all":
        print("\n" + "=" * 70)
        print("PASS 2: crypto + index universe only")
        print("=" * 70 + "\n")
        ci = filter_universe(data, {"CRYPTO", "INDEX"})
        if ci:
            pr2, mr2 = n_eff_symbols(ci)
            h2 = math.sqrt(pr2 / len(ci))
            run_grid(ci, CANDIDATES, h2)


if __name__ == "__main__":
    main()
