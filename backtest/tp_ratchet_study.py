"""TP-RATCHET STUDY — user idea 2026-07-03: "when a TP is about to get hit, move the TP
further into reasonable profitable areas and trail the SL into where the TP was."

Causal translation (bar-close engine, broker-legal): at bar CLOSE, when unrealized r is
within rat_gap_r of the CURRENT TP, extend the TP by rat_ext_r and raise the SL to
(old TP - rat_buf_r), clamped 0.05R below the trigger close (a long's SL cannot sit above
price). Repeats at each rung. A touch of the old TP on the trigger bar still exits at the
old TP (intrabar exit checks run first - pessimistic). This is the smartest version of
"bigger wins" so far because the giveback is CAPPED near the old TP; unlike the rejected
BE-lock/trail it cannot turn a winner into a scratch.

HONEST PRIORS (both directions, stated before running):
  against - unconditional TP4 was pure noise (bracket_tp: paired t ~ 0.1); every prior
  SL-tightening showed its cost in the paired test; and coverage is structurally low:
  most TP hits arrive via an intrabar spike THROUGH the TP, not a close hovering just
  under it, so few trades ever trigger.
  for - it only engages deep in profit (>=TP-gap), the floor rescues trades that stall
  just under TP and would have faded to a small time-exit, and among +1.5R touchers more
  run than fade (favorable raw material for letting-run mechanics).

PRE-REGISTERED cells (4, fixed before running - no scanning):
    gap .25 ext 1 buf .50   trigger 2.75R close -> TP4, floor 2.50R  (snug)
    gap .50 ext 1 buf .75   trigger 2.50R close -> TP4, floor 2.25R  (earlier, more coverage)
    gap .25 ext 2 buf .50   trigger 2.75R close -> TP5, floor 2.50R  (bigger extension)
    gap .25 ext 1 buf .25   trigger 2.75R close -> floor = close-0.05R (the most literal
                            "SL where the TP was"; the legality clamp binds)

Baseline = v1.23/v1.24 LIVE (pure bracket: SL 1 ATR / TP 3 ATR / hold 8, no lock/trail).

DECISION GATE (corrected 2026-07-02 standard - the raw pooled pair_t is RETIRED):
  * experiment.cluster_robust_paired on the OOS per-signal deltas: the DAY-clustered
    block-bootstrap 95% CI must EXCLUDE ZERO (equivalently haircut t >= ~1.96).
  * plus the usual: dExp>0, WFE>=0.3, DSR>=0.95 (92 cumulative trials: 82 prior + 6
    bracket/stop-buffer cells + these 4), 2x cost stress, >=60% quarters/symbols, N>=250.
Win-size metrics (avgWin, >=2R, >=3R, >=4R) are reported per cell - the user's actual
objective - but a win-size gain with negative/unresolvable dExp is a NO, not a SHIP.
"""
from __future__ import annotations
import math
import sys
import numpy as np
import pandas as pd

from scalper_confluence import CParams, simulate_symbol_c
from walkforward_dsr import load_spreadgated, real_cost_per_side
from experiment import EMC, nppf, psr, stt, n_eff_symbols, cluster_robust_paired

BRACKET = dict(direction="cont", entry_style="limit", entry_offset_atr=0.6,
               pending_expiry_bars=3, stop_atr=1.0, tp_atr=3.0,
               lock_trigger_atr=99.0, trail_atr=99.0, max_hold_bars=8,
               momentum_bars=6, momentum_atr=2.0, atr_period=14)
N_TRIALS_CUM = 92   # 82 claimed through the 4-study batch + 6 bracket/stop-buffer + 4 here

# label, rat_gap_r, rat_ext_r, rat_buf_r   (BASELINE first: feature OFF)
BASELINE = ("BASELINE pure bracket", 0.0, 1.0, 0.5)
CANDIDATES = [
    ("gap.25 ext1 buf.50", 0.25, 1.0, 0.50),
    ("gap.50 ext1 buf.75", 0.50, 1.0, 0.75),
    ("gap.25 ext2 buf.50", 0.25, 2.0, 0.50),
    ("gap.25 ext1 buf.25", 0.25, 1.0, 0.25),
]


def mkp(cell, cost, block=True):
    _, gap, ext, buf = cell
    return CParams(**BRACKET, rat_gap_r=gap, rat_ext_r=ext, rat_buf_r=buf,
                   cost_atr_frac=cost, block_overlap=block)


def collect(data, costs, cell, block=True, cost_mult=1.0):
    recs = []
    for sym, df in data.items():
        c = costs[sym] * cost_mult
        if not np.isfinite(c):
            continue
        tr, _ = simulate_symbol_c(df, mkp(cell, c, block), 0, len(df))
        tt = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            recs.append((tt[t["i"]], sym, t["i"], float(t["r"])))
    out = pd.DataFrame(recs, columns=["time", "sym", "sig_i", "r"]).sort_values("time")
    return out.reset_index(drop=True)


def q_split(trades, is_frac=0.70):
    t = trades.copy()
    t["q"] = pd.PeriodIndex(pd.to_datetime(t["time"]), freq="Q")
    qs = sorted(t["q"].unique())
    n_is = max(1, int(len(qs) * is_frac))
    return t[t["q"].isin(set(qs[:n_is]))], t[t["q"].isin(qs[n_is:])], qs[n_is:]


def win_metrics(r):
    r = np.asarray(r, float)
    w = r[r > 0]
    return dict(avg_win=(w.mean() if w.size else 0.0),
                ge2=float((r >= 2.0).mean() * 100),
                ge3=float((r >= 3.0).mean() * 100),
                ge4=float((r >= 4.0).mean() * 100))


def main():
    data = load_spreadgated()
    if len(data) < 8:
        print("Need spread-gated CSVs in data/derivM15_spreadgated/", file=sys.stderr)
        return 1
    costs = {s: real_cost_per_side(df) for s, df in data.items()}
    n_eff, _ = n_eff_symbols(data)
    n_sym = len(data)
    print(f"TP-RATCHET STUDY — {n_sym} spread-gated majors, real per-instrument cost, "
          f"N_eff={n_eff:.1f}; DECISION GATE = day-clustered CI excludes 0 (raw pair_t retired)")
    print(f"DSR deflation: {N_TRIALS_CUM} cumulative research trials\n")

    base_blk = collect(data, costs, BASELINE, block=True)
    _, base_oos, _ = q_split(base_blk)
    bs = stt(base_oos["r"].to_numpy())
    bwm = win_metrics(base_oos["r"])
    base_prd = collect(data, costs, BASELINE, block=False)
    _, base_prd_oos_df, _ = q_split(base_prd)
    base_prd_oos = base_prd_oos_df.set_index(["sym", "sig_i"])["r"]
    b2x = stt(q_split(collect(data, costs, BASELINE, block=True, cost_mult=2.0))[1]["r"].to_numpy())
    print(f"BASELINE OOS: N={bs['n']} exp={bs['exp']:+.4f} t={bs['t']:+.2f}  "
          f"avgWin={bwm['avg_win']:+.2f}R >=2R {bwm['ge2']:.1f}% >=3R {bwm['ge3']:.2f}% "
          f">=4R {bwm['ge4']:.2f}%  2x {b2x['exp']:+.4f}\n")

    var_null = 1.0 / max(2, bs["n"] - 1)
    z1 = nppf(1 - 1.0 / N_TRIALS_CUM)
    z2 = nppf(1 - 1.0 / N_TRIALS_CUM * math.exp(-1))
    sr0 = math.sqrt(var_null) * ((1 - EMC) * z1 + EMC * z2)

    hdr = (f"{'cell':20s}{'N':>6s}{'exp':>8s}{'dExp':>8s}{'nTrig':>6s}{'rawT':>6s}{'hcT':>6s}"
           f"{'  day-CI(95%)':>20s}{'WFE':>6s}{'avgW':>6s}{'>=3R%':>7s}{'>=4R%':>7s}"
           f"{'exp2x':>8s}{'Qp':>5s}{'Sy':>6s}{'DSR':>5s}  VERDICT")
    print(hdr); print("-" * len(hdr))

    for cell in CANDIDATES:
        blk = collect(data, costs, cell, block=True)
        c_is, c_oos, _ = q_split(blk)
        so, si = stt(c_oos["r"].to_numpy()), stt(c_is["r"].to_numpy())
        dexp = so["exp"] - bs["exp"]
        wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else float("nan")
        wm = win_metrics(c_oos["r"])
        prd = collect(data, costs, cell, block=False)
        _, prd_oos_df, _ = q_split(prd)
        prd_oos = prd_oos_df.set_index(["sym", "sig_i"])["r"]
        j = pd.concat([base_prd_oos.rename("b"), prd_oos.rename("c")], axis=1).dropna()
        d = (j["c"] - j["b"]).to_numpy()
        n_trig = int((d != 0).sum())          # signals whose outcome the ratchet changed
        times = prd_oos_df.set_index(["sym", "sig_i"]).loc[j.index, "time"]
        cr = cluster_robust_paired(d, times, n_eff, n_sym)
        e2 = stt(q_split(collect(data, costs, cell, block=True, cost_mult=2.0))[1]["r"].to_numpy())["exp"]
        qg = c_oos.groupby(pd.PeriodIndex(pd.to_datetime(c_oos["time"]), freq="Q"))["r"].mean()
        qpos, qn = int((qg > 0).sum()), len(qg)
        sg = c_oos.groupby("sym")["r"].agg(["mean", "count"])
        sp = int(((sg["mean"] > 0) & (sg["count"] >= 10)).sum())
        stot = int((sg["count"] >= 10).sum())
        dsr = psr(c_oos["r"].to_numpy(), sr0)
        gates = [dexp > 0, cr["excludes_zero"],
                 np.isfinite(wfe) and wfe >= 0.3, np.isfinite(dsr) and dsr >= 0.95,
                 e2 > 0, qn > 0 and qpos >= math.ceil(qn * 0.6),
                 stot > 0 and sp >= math.ceil(stot * 0.6), so["n"] >= 250]
        verdict = "SHIP" if all(gates) else ("watch" if (dexp > 0 and so["exp"] > 0) else "no")
        ci = f"[{cr['ci_lo']:+.4f},{cr['ci_hi']:+.4f}]"
        print(f"{cell[0]:20s}{so['n']:6d}{so['exp']:+8.4f}{dexp:+8.4f}{n_trig:6d}"
              f"{cr['raw_t']:+6.2f}{cr['haircut_t']:+6.2f}{ci:>20s}{wfe:6.2f}"
              f"{wm['avg_win']:+6.2f}{wm['ge3']:7.2f}{wm['ge4']:7.2f}{e2:+8.4f}"
              f"{qpos:2d}/{qn:<2d}{sp:2d}/{stot:<2d}{dsr:5.2f}  {verdict}")

    print("\nRead: nTrig = OOS signals whose outcome the ratchet actually changed (coverage).")
    print("SHIP requires the day-clustered CI to EXCLUDE zero — the corrected standard;")
    print("a fat right tail with an unresolvable dExp is watch/no, not ship.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
