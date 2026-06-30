"""Overfit-resistant edge hunt on the reproducible crypto M15 feed.

Runs a small, deliberately-bounded set of STRUCTURALLY DISTINCT strategies
(momentum continuation, momentum fade, RSI(2) reversion, Bollinger reversion/
breakout, Donchian breakout, VWAP reversion, opening-range breakout) through the
*same* validated exit/cost/fill engine (strategies.simulate) and the *same* ship
gate used elsewhere in this repo:

  * out-of-sample only (last 30% of every series),
  * a correlation breadth haircut (crypto is highly correlated -> few effective bets),
  * a Deflated Sharpe hurdle computed over EVERY cell tried (multiple-testing honest),
  * a 2x-cost stress and an honest crypto cost calibration (fees as a fraction of M15 ATR),
  * walk-forward efficiency (OOS/IS) and per-quarter sign stability.

Cost trick: in this engine the per-side cost is a constant shift in R
(shift = 2*cost_atr_frac/stop_atr because risk = stop_atr*ATR), so each config is
simulated ONCE at cost 0 and the whole cost sweep is applied analytically. Exact,
and fast enough to keep the trial count (and therefore the DSR penalty) honest.

Honest expectation: most or all candidates fail at realistic cost. The runner's
job is to say NO reliably and to flag anything that genuinely survives.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

import scalper_backtest as B
from strategies import ExecParams, simulate, SIGNALS
from experiment import nppf, psr, stt, EMC

# Cost levels as a fraction of M15 ATR. The crypto calibration (median ATR ~0.45%
# of price) makes these roughly:  0.02 ~ 0.9 bps/side (HFT/rebate-grade),
# 0.06 ~ 2.7 bps (VIP/futures maker),  0.12 ~ 5.4 bps (standard maker),
# and retail spot taker (10 bps) ~ 0.22 -- far off this chart.
COSTS = [0.0, 0.02, 0.06, 0.12]
SHIP_COST = 0.06          # the cost a config must still be positive at to "ship"
STRESS_COST = 0.12        # 2x of ship cost

# Each candidate is ONE configuration: (label, signal_name, signal_kwargs, exec_overrides).
# The list is deliberately bounded -- every cell raises the DSR multiple-testing hurdle.
CANDIDATES = [
    # --- structurally-distinct references (context; expected to fail at real cost) ---
    ("momo cont pull0.6 mom2", "momentum", dict(direction="cont"),
        dict(entry_style="limit", entry_offset_atr=0.6, tp_atr=3.0, stop_atr=1.0)),
    ("momo fade market mom2", "momentum", dict(direction="fade"),
        dict(entry_style="market", tp_atr=1.5, stop_atr=1.0)),
    ("rsi2 10/90 sma200", "rsi2", dict(lo=10, hi=90, trend_sma=200),
        dict(entry_style="market", tp_atr=1.0, stop_atr=2.0, max_hold_bars=12)),
    ("bb revert 20/2.5", "bollinger", dict(bb_period=20, k=2.5, mode="revert"),
        dict(entry_style="market", tp_atr=1.5, stop_atr=2.0, max_hold_bars=12)),
    ("donchian 96 tp4 trail", "donchian", dict(channel=96),
        dict(entry_style="stop", entry_offset_atr=0.05, tp_atr=4.0, stop_atr=1.5, trail_atr=1.0, max_hold_bars=16)),
    ("vwap revert 2.0atr", "vwap_revert", dict(stretch_atr=2.0),
        dict(entry_style="market", tp_atr=1.0, stop_atr=1.5, max_hold_bars=12)),
    ("orb 4bar break", "orb", dict(range_bars=4, stretch_atr=0.0),
        dict(entry_style="stop", entry_offset_atr=0.02, tp_atr=3.0, stop_atr=1.0, max_hold_bars=24)),
    # --- the lead: EXTREME-momentum continuation, deep pullback (gross edge >> cost) ---
    # Hypothesis: a >=4 ATR impulse in 6 bars is a genuine liquidation/regime event whose
    # continuation pays enough per trade to clear a realistic fee, unlike the common >=2 ATR move.
    ("xmom3 pull0.6 tp3",  "momentum", dict(direction="cont", momentum_atr=3.0),
        dict(entry_style="limit", entry_offset_atr=0.6, tp_atr=3.0, stop_atr=1.0, pending_expiry_bars=4)),
    ("xmom3 pull1.0 tp3",  "momentum", dict(direction="cont", momentum_atr=3.0),
        dict(entry_style="limit", entry_offset_atr=1.0, tp_atr=3.0, stop_atr=1.0, pending_expiry_bars=4)),
    ("xmom4 pull0.6 tp3",  "momentum", dict(direction="cont", momentum_atr=4.0),
        dict(entry_style="limit", entry_offset_atr=0.6, tp_atr=3.0, stop_atr=1.0, pending_expiry_bars=4)),
    ("xmom4 pull1.0 tp3",  "momentum", dict(direction="cont", momentum_atr=4.0),
        dict(entry_style="limit", entry_offset_atr=1.0, tp_atr=3.0, stop_atr=1.0, pending_expiry_bars=4)),
    ("xmom4 pull1.0 tp4 trail", "momentum", dict(direction="cont", momentum_atr=4.0),
        dict(entry_style="limit", entry_offset_atr=1.0, tp_atr=4.0, stop_atr=1.5, trail_atr=1.0,
             pending_expiry_bars=4, max_hold_bars=16)),
    ("xmom5 pull1.0 tp4",  "momentum", dict(direction="cont", momentum_atr=5.0),
        dict(entry_style="limit", entry_offset_atr=1.0, tp_atr=4.0, stop_atr=1.5,
             pending_expiry_bars=4, max_hold_bars=16)),
    ("xmom4 chase tp3",    "momentum", dict(direction="cont", momentum_atr=4.0),
        dict(entry_style="stop", entry_offset_atr=0.05, tp_atr=3.0, stop_atr=1.0, pending_expiry_bars=4)),
]


def n_eff(data):
    rets = {}
    for sym, df in data.items():
        rets[sym] = pd.Series(df["close"].astype(float).values,
                              index=pd.to_datetime(df["time"])).pct_change()
    M = pd.concat(rets, axis=1, sort=True).dropna()
    C = M.corr().to_numpy()
    ev = np.linalg.eigvalsh(C); ev = ev[ev > 0]
    pr = (ev.sum() ** 2) / np.square(ev).sum()
    mr = (C.sum() - len(C)) / (len(C) * (len(C) - 1))
    return pr, mr, len(C)


def atr_pct_summary(data):
    vals = []
    for df in data.values():
        h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        atr = B.wilder_atr(h, l, c, 14)
        vals.append(np.nanmedian(atr / c))
    return float(np.median(vals))


def sim_cost0(data, sig_name, sig_kw, ex, split):
    """Simulate once at cost 0. Return dict sym -> array of {r0, ts} and pooled list.
    Caches the signal array per (sym, sig_name, sig_kw)."""
    sig = SIGNALS[sig_name]
    per = {}
    for sym, df in data.items():
        n = len(df)
        lo, hi = (0, int(n * 0.7)) if split == "is" else (int(n * 0.7), n) if split == "oos" else (0, n)
        side = sig(df, **sig_kw)
        p0 = ExecParams(**{**ex.__dict__, "cost_atr_frac": 0.0})
        tr, _ = simulate(df, side, p0, lo, hi)
        ts = pd.to_datetime(df["time"]).to_numpy().astype("datetime64[ns]").astype("int64")
        per[sym] = np.array([(t["r"], ts[t["i"]]) for t in tr],
                            dtype=[("r0", float), ("t", "int64")]) if tr else \
            np.array([], dtype=[("r0", float), ("t", "int64")])
    return per


def shift_for(ex, cost):
    return 2.0 * cost / ex.stop_atr


def pooled_r(per, shift):
    arrs = [a["r0"] - shift for a in per.values() if a.size]
    return np.concatenate(arrs) if arrs else np.array([])


def quarter_signs(per, shift):
    recs = []
    for a in per.values():
        if a.size:
            recs.append(pd.DataFrame({"t": pd.to_datetime(a["t"]), "r": a["r0"] - shift}))
    if not recs:
        return 0, 0
    s = pd.concat(recs, ignore_index=True)
    s["q"] = pd.PeriodIndex(s["t"], freq="Q")
    g = s.groupby("q").r.mean()
    return int((g > 0).sum()), int(len(g))


def main():
    data = B.load_dataset("cryptoM15")
    pr, mr, k = n_eff(data)
    haircut = math.sqrt(pr / k)
    atrp = atr_pct_summary(data)
    print(f"CRYPTO M15: {k} instruments  mean pairwise r={mr:.3f}  N_eff={pr:.2f}  -> breadth t-haircut x{haircut:.2f}")
    print(f"median M15 ATR = {atrp*100:.3f}% of price  =>  cost_atr_frac 0.06 ~ {0.06*atrp*1e4:.1f} bps/side, "
          f"0.12 ~ {0.12*atrp*1e4:.1f} bps; retail 10bps taker ~ {0.001/atrp:.2f} ATR-frac\n")

    # --- evaluate every cell once (cost 0), collect OOS Sharpe for the DSR hurdle ---
    rows = []; trial_sr = []
    for label, sig_name, sig_kw, ex_over in CANDIDATES:
        ex = ExecParams(**ex_over)
        oos = sim_cost0(data, sig_name, sig_kw, ex, "oos")
        iss = sim_cost0(data, sig_name, sig_kw, ex, "is")
        sh = shift_for(ex, SHIP_COST)
        pool_ship = pooled_r(oos, sh)
        so = stt(pool_ship)
        si = stt(pooled_r(iss, sh))
        exp = {c: stt(pooled_r(oos, shift_for(ex, c)))["exp"] for c in COSTS}
        wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else (float("nan") if so["exp"] <= 0 else float("inf"))
        qpos, qn = quarter_signs(oos, sh)
        n_eff_tr = so["n"] * (pr / k)
        mde = 1.3 * (1.96 + 0.84) / math.sqrt(max(1, n_eff_tr))
        trial_sr.append(so["sr"])
        rows.append(dict(label=label, so=so, exp=exp, wfe=wfe, qpos=qpos, qn=qn,
                         t_hc=so["t"] * haircut, n_eff_tr=n_eff_tr, mde=mde, pool=pool_ship))

    sr = np.array([s for s in trial_sr if np.isfinite(s)]); N = max(2, len(sr))
    var = float(np.var(sr, ddof=1)) if len(sr) > 1 else 0.0
    z1 = nppf(1 - 1.0 / N); z2 = nppf(1 - 1.0 / N * math.exp(-1))
    sr0 = math.sqrt(var) * ((1 - EMC) * z1 + EMC * z2) if var > 0 else 0.0
    print(f"DSR hurdle: searched N={N} cells; expected-max per-obs Sharpe under null = {sr0:.4f} "
          f"(ship cost = {SHIP_COST} ATR-frac)\n")

    hdr = (f"{'candidate':24s}{'N':>6s}{'exp@0':>8s}{'exp.02':>8s}{'exp.06':>8s}{'exp.12':>8s}"
           f"{'t':>6s}{'t_hc':>6s}{'WFE':>6s}{'Qpos':>7s}{'DSR':>6s}  VERDICT")
    print(hdr); print("-" * len(hdr))
    ship = 0
    for r in sorted(rows, key=lambda r: -r["exp"][SHIP_COST]):
        dsr = psr(r["pool"], sr0)
        gates = [
            r["exp"][SHIP_COST] > 0,
            (np.isfinite(r["wfe"]) and r["wfe"] >= 0.3),
            (np.isfinite(dsr) and dsr >= 0.95),
            (r["n_eff_tr"] >= 250 and r["so"]["exp"] > r["mde"]),
            r["exp"][STRESS_COST] > 0,
            (r["qn"] > 0 and r["qpos"] >= math.ceil(r["qn"] * 0.6)),
            r["t_hc"] >= 1.96,
        ]
        verdict = "SHIP" if all(gates) else ("watch" if r["exp"][SHIP_COST] > 0 else "NO-SHIP")
        ship += verdict == "SHIP"
        wfe = f"{r['wfe']:6.2f}" if np.isfinite(r["wfe"]) else "   nan"
        dv = dsr if np.isfinite(dsr) else 0.0
        print(f"{r['label']:24s}{r['so']['n']:6d}{r['exp'][0.0]:+8.4f}{r['exp'][0.02]:+8.4f}"
              f"{r['exp'][0.06]:+8.4f}{r['exp'][0.12]:+8.4f}{r['so']['t']:+6.2f}{r['t_hc']:+6.2f}{wfe}"
              f"{r['qpos']:4d}/{r['qn']:<2d}{dv:6.2f}  {verdict}")
    print("\nLegend: exp@X = OOS expectancy (R) at cost_atr_frac X; t_hc = breadth-haircut t; "
          f"WFE = OOS/IS exp; Qpos = OOS quarters positive; SHIP needs all gates incl. exp@{STRESS_COST}>0 & DSR>=0.95.")
    print(f"\n>>> SHIP: {ship} of {len(rows)} candidates." + ("" if ship else "  (none cleared the ship gate)"))


if __name__ == "__main__":
    main()
