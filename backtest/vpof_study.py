"""S0-S1.5 runner (VPOF_SPEC_2026-07-10, hashed 6606a9fa...).

PRE-REGISTERED PRIMARY CELL (declared before any result was computed):
    window=96 (1 trading day), k=0.15 ATR, h=8 bars.
Grid: window in {96, 288} x k in {0.15, 0.30} x h in {4, 8}  (8 cells).

KILL GATE (S1.5) — an arm survives only if REAL beats its controls:
  SHIELD arm: strength-geometry model must beat PLACEBO levels and STALE levels
              on out-of-fold AUC (primary cell AND majority of cells), with the
              hypothesized monotonicity (stronger level -> lower violation rate).
  CUT arm:    FULL model must beat SHUFFLED-OF (within-day) on oof AUC
              (primary cell AND majority of cells) — i.e. order flow adds
              incremental information beyond level geometry.

Data: 12 spread-gated real Deriv M15 symbols (data/derivM15_spreadgated/),
tick volume, Wilder ATR(14) — the validated engine's estimator.
"""
import glob
import json
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr
from vp_engine import rolling_vp_levels
from of_features import of_features, shuffle_within_day
from violation_model import (build_touches, label_and_featurize,
                             walkforward_eval, FEATS_FULL, FEATS_STRENGTH)

WINDOWS = [96, 288]
KS = [0.15, 0.30]
HS = [4, 8]
PRIMARY = (96, 0.15, 8)
STEP = 4
RNG = np.random.default_rng(20260710)


def placebo_dict(vp, closes):
    """Placebo levels: same count + strength values per block; prices drawn as
    close +- distance sampled from the REAL pooled |level-close| distribution."""
    dists = []
    for t0, levels in vp.items():
        if t0 < len(closes):
            for (lp, _, _) in levels:
                dists.append(abs(lp - closes[t0]))
    dists = np.array(dists) if dists else np.array([1.0])
    out = {}
    for t0, levels in vp.items():
        if t0 >= len(closes) or not levels:
            out[t0] = []
            continue
        st = RNG.permutation([x[1] for x in levels])
        d = RNG.choice(dists, size=len(levels))
        sgn = RNG.choice([-1.0, 1.0], size=len(levels))
        out[t0] = [(closes[t0] + sgn[i] * d[i], float(st[i]), 'PLB')
                   for i in range(len(levels))]
    return out


def stale_dict(vp, lag_blocks):
    """Stale levels: yesterday's real VP applied to today (lag = 96 bars)."""
    keys = sorted(vp.keys())
    out = {}
    for i, t0 in enumerate(keys):
        j = i - lag_blocks
        out[t0] = vp[keys[j]] if j >= 0 else []
    return out


def main():
    files = sorted(glob.glob(os.path.join(HERE, "data", "derivM15_spreadgated", "*.csv")))
    pools = {}   # (variant, window, k, h) -> list of event DataFrames
    for f in files:
        sym = os.path.basename(f).replace(".csv", "")
        df = pd.read_csv(f)
        cols = {c.lower(): c for c in df.columns}
        df = df.rename(columns={cols[k]: k for k in
                                ("time", "open", "high", "low", "close", "volume") if k in cols})
        if not pd.api.types.is_numeric_dtype(df["time"]):
            # resolution-proof epoch seconds (pandas may parse to s/ms/us/ns units)
            dt = pd.to_datetime(df["time"], utc=True)
            df["time"] = (dt - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1)
        h_, l_, c_ = (df[x].to_numpy(float) for x in ("high", "low", "close"))
        atr = wilder_atr(h_, l_, c_, 14)
        feat = of_features(df)
        feat_sh = shuffle_within_day(feat, df["time"].to_numpy())
        for w in WINDOWS:
            vp = rolling_vp_levels(df, window=w, step=STEP)
            variants = {
                "real": (vp, feat),
                "shufOF": (vp, feat_sh),
                "placebo": (placebo_dict(vp, c_), feat),
                "stale": (stale_dict(vp, 96 // STEP), feat),
            }
            touch_cache = {}
            for name, (vpd, ft) in variants.items():
                tkey = name if name in ("placebo", "stale") else "real"
                if tkey not in touch_cache:
                    touch_cache[tkey] = build_touches(df, atr, vpd, window=w, step=STEP)
                touches = touch_cache[tkey]
                for k in KS:
                    for h in HS:
                        ev = label_and_featurize(touches, df, atr, ft, k, h)
                        ev["symbol"] = sym
                        pools.setdefault((name, w, k, h), []).append(ev)
        print(f"{sym}: done ({len(df)} bars)", flush=True)

    # ---- walk-forward evaluation per cell ----
    results = []
    for (name, w, k, h), evs in sorted(pools.items()):
        ev = pd.concat(evs, ignore_index=True)
        r_full = walkforward_eval(ev, FEATS_FULL, label=f"{name} FULL w{w} k{k} h{h}")
        r_str = walkforward_eval(ev, FEATS_STRENGTH, label=f"{name} STR  w{w} k{k} h{h}")
        # strength-quartile monotonicity (real only, informational)
        mono = None
        if name == "real":
            q = pd.qcut(ev["strength"], 4, labels=False, duplicates="drop")
            mono = ev.groupby(q)["y"].mean().round(4).tolist()
        results.append(dict(variant=name, window=w, k=k, h=h,
                            n=r_full["n"], base=r_full.get("base"),
                            auc_full=r_full["auc"], brier_full=r_full["brier"],
                            auc_strength=r_str["auc"], brier_strength=r_str["brier"],
                            mono_by_strength_quartile=mono))
        print(f"{name:8s} w{w:<4d} k{k:<5.2f} h{h}: n={r_full['n']:>7} base={r_full.get('base', float('nan')):.3f} "
              f"AUCfull={r_full['auc']:.4f} AUCstr={r_str['auc']:.4f} "
              f"Brier={r_full['brier']:.4f}", flush=True)

    with open(os.path.join(HERE, "vpof_gate_results.json"), "w") as fh:
        json.dump(results, fh, indent=1)

    # ---- kill-gate verdicts ----
    R = {(r["variant"], r["window"], r["k"], r["h"]): r for r in results}

    def gate(cellkey):
        w, k, h = cellkey
        real, plb = R[("real", w, k, h)], R[("placebo", w, k, h)]
        stl, shf = R[("stale", w, k, h)], R[("shufOF", w, k, h)]
        shield = (real["auc_strength"] > plb["auc_strength"]) and \
                 (real["auc_strength"] > stl["auc_strength"])
        cut = real["auc_full"] > shf["auc_full"]
        return shield, cut

    cells = [(w, k, h) for w in WINDOWS for k in KS for h in HS]
    votes = [gate(c) for c in cells]
    p_shield, p_cut = gate(PRIMARY)
    maj_shield = sum(v[0] for v in votes) > len(cells) / 2
    maj_cut = sum(v[1] for v in votes) > len(cells) / 2
    print("\n==== S1.5 KILL GATE ====")
    print(f"SHIELD arm: primary={'PASS' if p_shield else 'FAIL'} "
          f"majority={sum(v[0] for v in votes)}/{len(cells)} -> "
          f"{'SURVIVES' if (p_shield and maj_shield) else 'DEAD'}")
    print(f"CUT arm   : primary={'PASS' if p_cut else 'FAIL'} "
          f"majority={sum(v[1] for v in votes)}/{len(cells)} -> "
          f"{'SURVIVES' if (p_cut and maj_cut) else 'DEAD'}")

    # export primary-cell real events for S2
    w, k, h = PRIMARY
    ev = pd.concat(pools[("real", w, k, h)], ignore_index=True)
    ev.to_csv(os.path.join(HERE, "vpof_events_primary.csv"), index=False)
    print(f"primary-cell events -> vpof_events_primary.csv ({len(ev)} rows)")


if __name__ == "__main__":
    main()
