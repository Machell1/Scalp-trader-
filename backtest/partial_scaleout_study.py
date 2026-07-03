"""PARTIAL SCALE-OUT STUDY — bank part of a winner at a fixed R, runner to TP.

Hypothesis: the pure-bracket right tail is real but many trades retrace before TP;
locking partial profit at +1.5R (etc.) while leaving a BE-protected runner may lift
realized win size without the ladder's truncation failure mode.

PRE-REGISTERED cells (4, fixed before running):
  scale_out_frac=0.5 at trigger R in {1.0, 1.5, 2.0}; plus 33% at +1.5R.

Baseline = v1.23 pure bracket (SL 1 ATR / TP 3 ATR / hold 8, no lock/trail).
Protocol: real per-instrument Deriv cost, stitched-OOS quarters, PAIRED per-signal t,
DSR deflated for cumulative trials, 2x cost stress, win-size metrics.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

from scalper_confluence import CParams, simulate_symbol_c
from walkforward_dsr import load_spreadgated, real_cost_per_side
from experiment import EMC, nppf, psr, stt

BRACKET = dict(
    direction="cont", entry_style="limit", entry_offset_atr=0.6,
    pending_expiry_bars=3, stop_atr=1.0, tp_atr=3.0,
    lock_trigger_atr=99.0, trail_atr=99.0, max_hold_bars=8,
    momentum_bars=6, momentum_atr=2.0, atr_period=14,
)
CANDIDATES = [
    ("scale 50% at +1.0R", 1.0, 0.5),
    ("scale 50% at +1.5R", 1.5, 0.5),
    ("scale 50% at +2.0R", 2.0, 0.5),
    ("scale 33% at +1.5R", 1.5, 0.33),
]
N_TRIALS = 68 + len(CANDIDATES)


def mkp(cost, block, scale_r, scale_frac, cost_mult=1.0):
    return CParams(**BRACKET, cost_atr_frac=cost * cost_mult, block_overlap=block,
                   scale_out_r=scale_r, scale_out_frac=scale_frac)


def collect(data, costs, scale_r, scale_frac, block=True, cost_mult=1.0):
    recs = []
    for sym, df in data.items():
        c = costs[sym] * cost_mult
        if not np.isfinite(c):
            continue
        tr, _ = simulate_symbol_c(df, mkp(c, block, scale_r, scale_frac), 0, len(df))
        tt = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            recs.append((tt[t["i"]], sym, t["i"], float(t["r"])))
    return pd.DataFrame(recs, columns=["time", "sym", "sig_i", "r"]).sort_values("time").reset_index(drop=True)


def q_split(trades, is_frac=0.70):
    t = trades.copy()
    t["q"] = pd.PeriodIndex(pd.to_datetime(t["time"]), freq="Q")
    qs = sorted(t["q"].unique())
    n_is = max(1, int(len(qs) * is_frac))
    is_qs, oos_qs = set(qs[:n_is]), qs[n_is:]
    return t[t["q"].isin(is_qs)], t[t["q"].isin(oos_qs)], oos_qs


def win_metrics(r):
    r = np.asarray(r, float)
    w = r[r > 0]
    return dict(avg_win=(w.mean() if w.size else 0.0),
                med_win=(np.median(w) if w.size else 0.0),
                pct_ge2R=float((r >= 2.0).mean() * 100))


def main():
    data = load_spreadgated()
    costs = {s: real_cost_per_side(df) for s, df in data.items()}
    print(f"PARTIAL SCALE-OUT STUDY — {len(data)} spread-gated majors, real cost, "
          f"DSR deflation N={N_TRIALS}\n")

    base_blk = collect(data, costs, 0.0, 0.5)
    base_is, base_oos, _ = q_split(base_blk)
    bs_oos = stt(base_oos["r"].to_numpy())
    base_prd_oos = q_split(collect(data, costs, 0.0, 0.5, block=False))[1].set_index(["sym", "sig_i"])["r"]
    base_2x_oos = q_split(collect(data, costs, 0.0, 0.5, cost_mult=2.0))[1]
    bwm = win_metrics(base_oos["r"])
    print(f"BASELINE (pure bracket) OOS: N={bs_oos['n']} exp={bs_oos['exp']:+.4f} "
          f"t={bs_oos['t']:+.2f} avgWin={bwm['avg_win']:+.2f}R >=2R {bwm['pct_ge2R']:.1f}% "
          f"2x-cost={stt(base_2x_oos['r'].to_numpy())['exp']:+.4f}\n")

    var_null = 1.0 / max(2, bs_oos["n"] - 1)
    z1 = nppf(1 - 1.0 / N_TRIALS)
    z2 = nppf(1 - 1.0 / N_TRIALS * math.exp(-1))
    sr0 = math.sqrt(var_null) * ((1 - EMC) * z1 + EMC * z2)

    hdr = (f"{'candidate':28s}{'N':>6s}{'exp':>8s}{'dExp':>8s}{'pair_t':>7s}{'WFE':>6s}"
           f"{'avgWin':>7s}{'>=2R%':>7s}{'exp2x':>8s}{'Qpos':>6s}{'Sym+':>6s}{'DSR':>6s}  VERDICT")
    print(hdr)
    print("-" * len(hdr))

    for label, scale_r, scale_frac in CANDIDATES:
        blk = collect(data, costs, scale_r, scale_frac)
        c_is, c_oos, _ = q_split(blk)
        so, si = stt(c_oos["r"].to_numpy()), stt(c_is["r"].to_numpy())
        dexp = so["exp"] - bs_oos["exp"]
        wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else float("nan")
        wm = win_metrics(c_oos["r"])
        prd = q_split(collect(data, costs, scale_r, scale_frac, block=False))[1].set_index(["sym", "sig_i"])["r"]
        joined = pd.concat([base_prd_oos.rename("b"), prd.rename("c")], axis=1).dropna()
        d = (joined["c"] - joined["b"]).to_numpy()
        pair_t = ((d.mean() / (d.std(ddof=1) / math.sqrt(len(d))))
                  if len(d) > 5 and d.std(ddof=1) > 0 else float("nan"))
        oos2 = q_split(collect(data, costs, scale_r, scale_frac, cost_mult=2.0))[1]
        exp2 = stt(oos2["r"].to_numpy())["exp"]
        qg = c_oos.groupby(pd.PeriodIndex(pd.to_datetime(c_oos["time"]), freq="Q"))["r"].mean()
        qpos, qn = int((qg > 0).sum()), len(qg)
        sg = c_oos.groupby("sym")["r"].agg(["mean", "count"])
        sym_pos = int(((sg["mean"] > 0) & (sg["count"] >= 10)).sum())
        sym_tot = int((sg["count"] >= 10).sum())
        dsr = psr(c_oos["r"].to_numpy(), sr0)
        gates = [dexp > 0, np.isfinite(pair_t) and pair_t > 1.96,
                 np.isfinite(wfe) and wfe >= 0.3, np.isfinite(dsr) and dsr >= 0.95,
                 exp2 > 0, qn > 0 and qpos >= math.ceil(qn * 0.6),
                 sym_tot > 0 and sym_pos >= math.ceil(sym_tot * 0.6), so["n"] >= 250]
        verdict = "SHIP" if all(gates) else ("watch" if (dexp > 0 and so["exp"] > 0) else "no")
        print(f"{label:28s}{so['n']:6d}{so['exp']:+8.4f}{dexp:+8.4f}{pair_t:+7.2f}"
              f"{wfe:6.2f}{wm['avg_win']:+7.2f}{wm['pct_ge2R']:7.1f}{exp2:+8.4f}"
              f"{qpos:3d}/{qn:<2d}{sym_pos:3d}/{sym_tot:<2d}{dsr:6.2f}  {verdict}")


if __name__ == "__main__":
    main()
