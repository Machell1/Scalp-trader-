"""Session/liquidity-gate study on the PULLBACK config (HANDOFF backlog #4 / brief P2).

Motivation (day-1 live, 2026-07-01, N tiny, descriptive only): thin-hours bucket
-1.97R vs +2.82R elsewhere. The old session test that failed was on the CHASE entry;
it has never been run on the validated pullback config. This runner does that,
through the FULL HANDOFF anti-overfit gate:

  * marginal OOS expectancy vs the SHIPPED pullback baseline (not vs zero)
  * permutation test: kept subset must beat same-N random subsets of baseline
  * WFE (OOS/IS) >= 0.30
  * DSR >= 0.95, deflated for every session cell tried here + prior research
  * 2x cost stress positive
  * >= 60% OOS quarters positive
  * powered sample (N_eff >= 250)

PRE-REGISTERED candidate windows (do NOT add cells after seeing results; every cell
added must stay in CANDIDATES so the DSR deflation counts it):
  * server-clock windows target the Deriv thin-hours pattern seen on day-1
  * ET windows target US cash-session liquidity

Data: real Deriv M15 spread-gated CSVs (fetch_spreadgated.py) at per-instrument
REAL spread cost — same source as the walk-forward SHIP verdict.

Verdict semantics: adopt a session gate ONLY on SHIP. WATCH/NO-SHIP => drop (the
day-1 bucket was noise). Run:  python session_gate_study.py
"""
from __future__ import annotations
import math
import sys

import numpy as np
import pandas as pd

from scalper_confluence import CParams, simulate_symbol_c, rs_of
from experiment import EMC, nppf, psr, stt, n_eff_symbols, perm_test
from walkforward_dsr import (SHIPPED, SPREAD_GATED, DATA_DIR, load_spreadgated,
                             real_cost_per_side, N_RESEARCH_TRIALS)

IS_FRAC = 0.70

# ---------------------------------------------------------------------------
# PRE-REGISTERED session windows. sess_tz="" = Deriv server clock (data native);
# otherwise IANA tz. (start_hm, end_hm) half-open, wrap-around supported.
# ---------------------------------------------------------------------------
CANDIDATES = [
    ("srv 05:00-23:00 (drop 23-05 thin)",  dict(sess_start_hm=500,  sess_end_hm=2300, sess_tz="")),
    ("srv 06:00-22:00",                    dict(sess_start_hm=600,  sess_end_hm=2200, sess_tz="")),
    ("srv 07:00-17:00 (EU+US morning)",    dict(sess_start_hm=700,  sess_end_hm=1700, sess_tz="")),
    ("ET 09:30-16:00 (US RTH)",            dict(sess_start_hm=930,  sess_end_hm=1600)),
    ("ET 03:00-16:00 (EU open-US close)",  dict(sess_start_hm=300,  sess_end_hm=1600)),
]


def pooled(data, costs, overrides, split, block=True):
    """Pooled R across symbols at per-symbol REAL cost. split: 'is'|'oos'|'all'."""
    pools = []
    for sym, df in data.items():
        cost = costs.get(sym, float("nan"))
        if not np.isfinite(cost):
            continue
        n = len(df)
        lo, hi = ((0, int(n * IS_FRAC)) if split == "is"
                  else (int(n * IS_FRAC), n) if split == "oos" else (0, n))
        p = CParams(**{**SHIPPED, **overrides, "cost_atr_frac": cost, "block_overlap": block})
        tr, _ = simulate_symbol_c(df, p, lo, hi)
        pools.append(np.array(rs_of(tr), float))
    return np.concatenate([a for a in pools if a.size]) if any(a.size for a in pools) else np.array([])


def quarter_signs(data, costs, overrides):
    recs = []
    for sym, df in data.items():
        cost = costs.get(sym, float("nan"))
        if not np.isfinite(cost):
            continue
        n = len(df)
        lo, hi = int(n * IS_FRAC), n
        p = CParams(**{**SHIPPED, **overrides, "cost_atr_frac": cost, "block_overlap": True})
        tr, _ = simulate_symbol_c(df, p, lo, hi)
        tt = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            recs.append((tt[t["i"]], t["r"]))
    if not recs:
        return 0, 0
    s = pd.DataFrame(recs, columns=["t", "r"])
    s["q"] = pd.PeriodIndex(pd.to_datetime(s["t"]), freq="Q")
    g = s.groupby("q")["r"].mean()
    return int((g > 0).sum()), int(len(g))


def main():
    data = load_spreadgated()
    if len(data) < 8:
        print(f"Need spread-gated CSVs in {DATA_DIR}/ "
              f"({len(data)}/{len(SPREAD_GATED)} found). Run fetch_spreadgated.py "
              "with the MT5 terminal open.", file=sys.stderr)
        return 1
    costs = {sym: real_cost_per_side(df) for sym, df in data.items()}

    pr, mean_r = n_eff_symbols(data)
    haircut = math.sqrt(pr / len(data))
    print(f"SPREAD-GATED: {len(data)} symbols  N_eff={pr:.2f}  t-haircut x{haircut:.2f}\n")

    # SHIPPED pullback baseline (the thing a session gate must marginally beat)
    base_oos = pooled(data, costs, {}, "oos", block=True)
    base_oos_nb = pooled(data, costs, {}, "oos", block=False)   # signal-level for perm test
    base_is = pooled(data, costs, {}, "is", block=True)
    bs, bi = stt(base_oos), stt(base_is)
    print(f"BASELINE (SHIPPED pullback, real cost): "
          f"IS exp{bi['exp']:+.4f} N{bi['n']}   OOS exp{bs['exp']:+.4f} t{bs['t']:+.2f} N{bs['n']}\n")

    rows, trial_sr = [], []
    for label, ov in CANDIDATES:
        oos = pooled(data, costs, ov, "oos", block=True)
        iss = pooled(data, costs, ov, "is", block=True)
        # 2x stress: double every per-symbol cost
        costs2 = {s: c * 2 for s, c in costs.items()}
        oos2 = pooled(data, costs2, ov, "oos", block=True)
        so, si = stt(oos), stt(iss)
        dExp = so["exp"] - bs["exp"]
        dTot = so["tot"] - bs["tot"]
        wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else float("nan")
        kept_nb = pooled(data, costs, ov, "oos", block=False)
        pperm = perm_test(base_oos_nb, kept_nb)
        qpos, qn = quarter_signs(data, costs, ov)
        n_eff_tr = so["n"] * (pr / len(data))
        mde = 1.3 * (1.96 + 0.84) / math.sqrt(max(1, n_eff_tr))
        trial_sr.append(so["sr"])
        rows.append(dict(label=label, so=so, dExp=dExp, dTot=dTot, wfe=wfe, pperm=pperm,
                         exp2=stt(oos2)["exp"], qpos=qpos, qn=qn, n_eff_tr=n_eff_tr,
                         mde=mde, oos_r=oos))

    # DSR hurdle deflated for these cells + the prior research trials
    sr_arr = np.array([s for s in trial_sr if np.isfinite(s)])
    n_trials = N_RESEARCH_TRIALS + len(CANDIDATES)
    var_sr = float(np.var(sr_arr, ddof=1)) if len(sr_arr) > 1 else 0.0
    # The candidate windows OVERLAP heavily, so their trial-SR variance can collapse toward 0
    # and make the hurdle vacuous (a noise window could then clear DSR trivially). Floor the
    # null at the sampling variance of a per-trade Sharpe under H0, 1/(N-1), using the SMALLEST
    # candidate N (most conservative) — same principled floor as walkforward_dsr.dsr_hurdle.
    min_n = min((r["so"]["n"] for r in rows if r["so"]["n"] > 1), default=max(2, bs["n"]))
    var_sr = max(var_sr, 1.0 / max(2, min_n - 1))
    z1 = nppf(1 - 1.0 / n_trials)
    z2 = nppf(1 - 1.0 / n_trials * math.exp(-1))
    sr0 = math.sqrt(var_sr) * ((1 - EMC) * z1 + EMC * z2)
    print(f"DSR hurdle sr0={sr0:.4f} (deflated for {n_trials} trials: "
          f"{N_RESEARCH_TRIALS} prior + {len(CANDIDATES)} session cells)\n")

    hdr = (f"{'session window':38s}{'N':>6s}{'exp':>8s}{'dExp':>8s}{'t_hc':>6s}{'WFE':>6s}"
           f"{'perm_p':>8s}{'exp2x':>8s}{'Qpos':>7s}{'DSR':>6s}  VERDICT")
    print(hdr)
    print("-" * len(hdr))
    any_ship = False
    for r in sorted(rows, key=lambda r: -r["dExp"]):
        so = r["so"]
        dsr = psr(r["oos_r"], sr0)
        gates = [
            r["dExp"] > 0,
            np.isfinite(r["pperm"]) and r["pperm"] < 0.05,
            np.isfinite(r["wfe"]) and r["wfe"] >= 0.30,
            np.isfinite(dsr) and dsr >= 0.95,
            r["n_eff_tr"] >= 250 and so["exp"] > r["mde"],
            r["exp2"] > 0,
            r["qn"] > 0 and r["qpos"] >= math.ceil(r["qn"] * 0.6),
        ]
        verdict = "SHIP" if all(gates) else ("watch" if (r["dExp"] > 0 and so["exp"] > 0) else "NO-SHIP")
        any_ship = any_ship or verdict == "SHIP"
        wfe = f"{r['wfe']:6.2f}" if np.isfinite(r["wfe"]) else "   nan"
        pp = f"{r['pperm']:8.3f}" if np.isfinite(r["pperm"]) else "     -- "
        print(f"{r['label']:38s}{so['n']:6d}{so['exp']:+8.4f}{r['dExp']:+8.4f}"
              f"{so['t']*haircut:+6.2f}{wfe}{pp}{r['exp2']:+8.4f}"
              f"{r['qpos']:4d}/{r['qn']:<2d}{(dsr if np.isfinite(dsr) else 0):6.2f}  {verdict}")

    print("\nRules: adopt a session gate ONLY on SHIP (all gates). A 'watch' or NO-SHIP")
    print("means the day-1 thin-hours bucket was noise - drop the idea (HANDOFF #4).")
    if not any_ship:
        print(">>> No session window cleared the gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
