"""ATR-ADAPTIVE TP STUDY — widen TP in high realized-vol regimes, tighten in quiet.

Hypothesis: a fixed 3 ATR TP may be too ambitious in compressed vol (more time-exit
grinders) and too tight in expansion (caps the right tail). Causal rv_pct at the
signal bar picks the TP multiple.

PRE-REGISTERED cells (4):
  low/high TP pairs {(2.5, 3.5), (2.0, 4.0), (3.0, 4.0), (2.5, 4.5)} with rv_pct
  tertile cutoffs 0.33 / 0.67 (mid band keeps tp_atr=3.0).

Baseline = v1.23 pure bracket. Protocol identical to exit_ladder_study.
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
    ("tp low2.5 / high3.5", 2.5, 3.5),
    ("tp low2.0 / high4.0", 2.0, 4.0),
    ("tp low3.0 / high4.0", 3.0, 4.0),
    ("tp low2.5 / high4.5", 2.5, 4.5),
]
N_TRIALS = 68 + len(CANDIDATES)


def mkp(cost, block, tp_lo, tp_hi, cost_mult=1.0):
    return CParams(**BRACKET, cost_atr_frac=cost * cost_mult, block_overlap=block,
                   adaptive_tp=True, tp_atr_low_vol=tp_lo, tp_atr_high_vol=tp_hi,
                   adaptive_tp_lo=0.33, adaptive_tp_hi=0.67)


def collect(data, costs, tp_lo, tp_hi, block=True, cost_mult=1.0):
    recs = []
    for sym, df in data.items():
        c = costs[sym] * cost_mult
        if not np.isfinite(c):
            continue
        tr, _ = simulate_symbol_c(df, mkp(c, block, tp_lo, tp_hi), 0, len(df))
        tt = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            recs.append((tt[t["i"]], sym, t["i"], float(t["r"])))
    return pd.DataFrame(recs, columns=["time", "sym", "sig_i", "r"]).sort_values("time").reset_index(drop=True)


def q_split(trades, is_frac=0.70):
    t = trades.copy()
    t["q"] = pd.PeriodIndex(pd.to_datetime(t["time"]), freq="Q")
    qs = sorted(t["q"].unique())
    n_is = max(1, int(len(qs) * is_frac))
    return t[t["q"].isin(set(qs[:n_is]))], t[t["q"].isin(set(qs[n_is:]))]


def win_metrics(r):
    r = np.asarray(r, float)
    w = r[r > 0]
    return dict(avg_win=(w.mean() if w.size else 0.0),
                pct_ge2R=float((r >= 2.0).mean() * 100))


def main():
    data = load_spreadgated()
    costs = {s: real_cost_per_side(df) for s, df in data.items()}
    print(f"ATR-ADAPTIVE TP STUDY — {len(data)} majors, real cost, DSR N={N_TRIALS}\n")

    def base_collect(block=True, cost_mult=1.0):
        recs = []
        for sym, df in data.items():
            c = costs[sym] * cost_mult
            if not np.isfinite(c):
                continue
            p = CParams(**BRACKET, cost_atr_frac=c, block_overlap=block)
            tr, _ = simulate_symbol_c(df, p, 0, len(df))
            tt = pd.to_datetime(df["time"]).to_numpy()
            for t in tr:
                recs.append((tt[t["i"]], sym, t["i"], float(t["r"])))
        return pd.DataFrame(recs, columns=["time", "sym", "sig_i", "r"]).sort_values("time").reset_index(drop=True)

    base_blk = base_collect()
    _, base_oos = q_split(base_blk)
    bs_oos = stt(base_oos["r"].to_numpy())
    base_prd_oos = q_split(base_collect(block=False))[1].set_index(["sym", "sig_i"])["r"]
    bwm = win_metrics(base_oos["r"])
    b2x = stt(q_split(base_collect(cost_mult=2.0))[1]["r"].to_numpy())["exp"]
    print(f"BASELINE (pure bracket tp3) OOS: N={bs_oos['n']} exp={bs_oos['exp']:+.4f} "
          f"avgWin={bwm['avg_win']:+.2f}R >=2R {bwm['pct_ge2R']:.1f}% 2x={b2x:+.4f}\n")

    var_null = 1.0 / max(2, bs_oos["n"] - 1)
    z1 = nppf(1 - 1.0 / N_TRIALS)
    z2 = nppf(1 - 1.0 / N_TRIALS * math.exp(-1))
    sr0 = math.sqrt(var_null) * ((1 - EMC) * z1 + EMC * z2)

    hdr = (f"{'candidate':28s}{'N':>6s}{'exp':>8s}{'dExp':>8s}{'pair_t':>7s}{'WFE':>6s}"
           f"{'avgWin':>7s}{'>=2R%':>7s}{'exp2x':>8s}{'Qpos':>6s}{'Sym+':>6s}{'DSR':>6s}  VERDICT")
    print(hdr)
    print("-" * len(hdr))

    for label, tp_lo, tp_hi in CANDIDATES:
        blk = collect(data, costs, tp_lo, tp_hi)
        c_is, c_oos = q_split(blk)
        so, si = stt(c_oos["r"].to_numpy()), stt(c_is["r"].to_numpy())
        dexp = so["exp"] - bs_oos["exp"]
        wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else float("nan")
        wm = win_metrics(c_oos["r"])
        prd = q_split(collect(data, costs, tp_lo, tp_hi, block=False))[1].set_index(["sym", "sig_i"])["r"]
        joined = pd.concat([base_prd_oos.rename("b"), prd.rename("c")], axis=1).dropna()
        d = (joined["c"] - joined["b"]).to_numpy()
        pair_t = ((d.mean() / (d.std(ddof=1) / math.sqrt(len(d))))
                  if len(d) > 5 and d.std(ddof=1) > 0 else float("nan"))
        exp2 = stt(q_split(collect(data, costs, tp_lo, tp_hi, cost_mult=2.0))[1]["r"].to_numpy())["exp"]
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
