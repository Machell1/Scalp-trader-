"""CLUSTER-ROBUST RE-CHECK of the SHIP gate's correlation blind spot.

The study SHIP gate tests the RAW pooled paired t on ~17k correlated per-signal deltas
(12 instruments, N_eff~2.6). This re-tests the decisions that actually MATTER under an
honest correlation-adjusted standard:

  A) LIVE v1.23 PURE BRACKET vs the prior v1.2 LADDER (lock .25 / trail .5)  -- the change
     that is ALREADY LIVE on real money. Must survive to trust the live ship.
  B) partial scale-out 50% @+1.5R vs v1.23 pure bracket  -- the WATCH candidate, for the
     record (should FAIL, confirming the workflow verdict).

For each paired comparison (same signals, block_overlap=False, OOS quarters only):
  raw pooled t, N_eff, haircut t = raw * sqrt(N_eff/N_sym), and a DAY-clustered block
  bootstrap 95% CI on the mean delta (whole calendar days resampled together).
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

from scalper_confluence import CParams, simulate_symbol_c
from walkforward_dsr import SHIPPED, load_spreadgated, real_cost_per_side
from experiment import n_eff_symbols

LADDER = dict(SHIPPED)                                         # v1.2: lock .25 / trail .5
BRACKET = dict(SHIPPED, lock_trigger_atr=99.0, trail_atr=99.0)  # v1.23 live pure bracket
SEED = 20260702


def paired_oos(data, costs, cfg, extra=None, is_frac=0.70):
    recs = []
    for sym, df in data.items():
        c = costs[sym]
        if not np.isfinite(c):
            continue
        kw = dict(cfg, cost_atr_frac=c, block_overlap=False)
        if extra:
            kw.update(extra)
        tr, _ = simulate_symbol_c(df, CParams(**kw), 0, len(df))
        tt = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            recs.append((tt[t["i"]], sym, t["i"], float(t["r"])))
    out = pd.DataFrame(recs, columns=["time", "sym", "sig_i", "r"]).sort_values("time").reset_index(drop=True)
    q = pd.PeriodIndex(pd.to_datetime(out["time"]), freq="Q")
    qs = sorted(q.unique())
    n_is = max(1, int(len(qs) * is_frac))
    return out[q.isin(qs[n_is:])]


def cluster_robust(base_oos, cand_oos, n_eff, n_sym, label):
    b = base_oos.set_index(["sym", "sig_i"])["r"].rename("b")
    c = cand_oos.set_index(["sym", "sig_i"])["r"].rename("c")
    j = pd.concat([b, c], axis=1).dropna()
    d = (j["c"] - j["b"]).to_numpy()
    n = len(d)
    raw_t = d.mean() / (d.std(ddof=1) / math.sqrt(n))
    haircut_t = raw_t * math.sqrt(n_eff / n_sym)
    # day-clustered block bootstrap
    times = pd.to_datetime(cand_oos.set_index(["sym", "sig_i"]).loc[j.index, "time"])
    day = times.dt.floor("D").to_numpy()
    days, inv = np.unique(day, return_inverse=True)
    groups = [d[inv == k] for k in range(len(days))]
    rng = np.random.default_rng(SEED)
    boots = np.empty(5000)
    nd = len(days)
    for it in range(5000):
        pick = rng.integers(0, nd, nd)
        boots[it] = np.concatenate([groups[p] for p in pick]).mean()
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"\n{label}")
    print(f"  paired N={n}  mean dExp={d.mean():+.5f}  raw pooled t={raw_t:+.3f}")
    print(f"  N_eff={n_eff:.2f}/{n_sym}  ->  haircut t={haircut_t:+.3f}  ({'PASS' if abs(haircut_t)>1.96 else 'FAIL'} vs 1.96)")
    print(f"  day-clustered 95% CI on mean dExp = [{lo:+.5f}, {hi:+.5f}]  "
          f"-> {'EXCLUDES 0 (significant)' if (lo>0 or hi<0) else 'includes 0 (not significant)'}")
    return dict(label=label, n=n, dexp=float(d.mean()), raw_t=float(raw_t),
                haircut_t=float(haircut_t), ci_lo=float(lo), ci_hi=float(hi),
                excludes_zero=bool(lo > 0 or hi < 0))


def main():
    data = load_spreadgated()
    costs = {s: real_cost_per_side(df) for s, df in data.items()}
    n_eff, _ = n_eff_symbols(data)
    n_sym = len(data)
    print(f"CLUSTER-ROBUST GATE RE-CHECK — {n_sym} spread-gated majors, N_eff={n_eff:.2f}, "
          f"mean pairwise correlation implied.  OOS quarters only, seed {SEED}.")

    ladder_oos = paired_oos(data, costs, LADDER)
    bracket_oos = paired_oos(data, costs, BRACKET)
    so_oos = paired_oos(data, costs, BRACKET, extra=dict(scaleout_r=1.5, scaleout_frac=0.5))

    # A) LIVE decision: pure bracket vs ladder
    cluster_robust(ladder_oos, bracket_oos, n_eff, n_sym,
                   "A) LIVE v1.23 PURE BRACKET  vs  v1.2 LADDER  (the change already on real money)")
    # B) WATCH candidate: scale-out vs pure bracket (should fail)
    cluster_robust(bracket_oos, so_oos, n_eff, n_sym,
                   "B) partial scale-out 50%@+1.5R  vs  v1.23 pure bracket  (the WATCH candidate)")


if __name__ == "__main__":
    main()
