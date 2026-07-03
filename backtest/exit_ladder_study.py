"""EXIT-LADDER STUDY — can a different lock/trail/TP/hold make wins LARGER without
hurting expectancy? (The one major parameter block never swept; day-1 live forensics
showed winners reaching 1.3-1.5R MFE but trailed out at ~0.9R, with 6/15 shakeouts.)

PRE-REGISTERED grid (13 cells, fixed before running — no scanning):
  lock trigger {0.25 (current), 0.5, OFF} x trail {0.5 (current), 0.75, 1.0, OFF}
  x TP {3 (current), 4, none} x hold {8 (current), 12, 16} — economically-motivated
  combinations only, each ONE coherent idea vs the live config.

Protocol (identical to the SHIP gate):
  * Real per-instrument Deriv spread cost (0.5*median spread/median ATR per side).
  * Calendar-quarter walk-forward split (first 70% of quarters = IS, rest stitched OOS).
  * PAIRED per-signal analysis (block_overlap=False): entries are IDENTICAL across exit
    variants, so per-signal r_candidate - r_baseline gives a sharp paired t-stat.
  * Portfolio realism (block_overlap=True) for the headline numbers.
  * DSR deflated for the CUMULATIVE research count (62 trials: 25 prior + 19 confluence
    + 5 session + 13 here), 2x cost stress, per-quarter and per-symbol stability.
  * Win-size metrics (the actual question): avg win R, median win, % of trades >= +2R.

Exit-change caveat: permutation-vs-random-subset does not apply (exits TRANSFORM every
trade rather than selecting a subset); the paired test replaces it and is stronger.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

from scalper_confluence import CParams, simulate_symbol_c
from walkforward_dsr import (SPREAD_GATED, SHIPPED, load_spreadgated, real_cost_per_side)
from experiment import EMC, nppf, psr, stt, n_eff_symbols

OFF = 99.0
N_TRIALS_CUM = 62   # 25 prior + 19 confluence + 5 session + 13 here (honest deflation)

# label, lock_trigger, trail, tp, hold  (current live config first = BASELINE)
BASELINE = ("BASELINE lock.25 tr.5 tp3 h8", 0.25, 0.5, 3.0, 8)
CANDIDATES = [
    ("later lock .5",            0.50, 0.5, 3.0, 8),
    ("wider trail .75",          0.25, 0.75, 3.0, 8),
    ("wider trail 1.0",          0.25, 1.0, 3.0, 8),
    ("lock.5 + trail1.0",        0.50, 1.0, 3.0, 8),
    ("BE-only (no trail)",       0.25, OFF, 3.0, 8),
    ("pure bracket",             OFF,  OFF, 3.0, 8),
    ("tp4 ladder",               0.25, 0.5, 4.0, 8),
    ("trail-only (no TP)",       0.25, 0.5, 0.0, 8),
    ("hold 12",                  0.25, 0.5, 3.0, 12),
    ("hold 16",                  0.25, 0.5, 3.0, 16),
    ("bracket + hold16",         OFF,  OFF, 3.0, 16),
    ("breathe: lock.5 tr1 h12",  0.50, 1.0, 3.0, 12),
    ("bracket tp4 h16",          OFF,  OFF, 4.0, 16),
]

def mkp(cell, cost, block=True):
    _, lock, trail, tp, hold = cell
    base = dict(SHIPPED)
    base.update(lock_trigger_atr=lock, trail_atr=trail, tp_atr=tp, max_hold_bars=hold)
    return CParams(**base, cost_atr_frac=cost, block_overlap=block)

def collect(data, costs, cell, block=True, cost_mult=1.0):
    """Full-history trade tape: list of (time, sym, sig_index, r)."""
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
    pr, mean_r = n_eff_symbols(data)
    haircut = math.sqrt(pr / len(data))
    print(f"EXIT-LADDER STUDY — {len(data)} spread-gated majors, real per-instrument cost, "
          f"N_eff={pr:.1f} (t-haircut x{haircut:.2f})")
    print(f"DSR deflation: {N_TRIALS_CUM} cumulative research trials\n")

    # ---------- baseline ----------
    base_blk = collect(data, costs, BASELINE, block=True)
    base_is, base_oos, oos_qs = q_split(base_blk)
    bs_oos = stt(base_oos["r"].to_numpy())
    base_prd = collect(data, costs, BASELINE, block=False)          # paired (signal-level)
    base_prd_oos = q_split(base_prd)[1].set_index(["sym", "sig_i"])["r"]
    base_2x_oos = q_split(collect(data, costs, BASELINE, block=True, cost_mult=2.0))[1]
    bwm = win_metrics(base_oos["r"])
    print(f"BASELINE OOS (stitched quarters, real cost): N={bs_oos['n']} exp={bs_oos['exp']:+.4f} "
          f"t={bs_oos['t']:+.2f}  avgWin={bwm['avg_win']:+.2f}R medWin={bwm['med_win']:+.2f}R "
          f">=2R {bwm['pct_ge2R']:.1f}%  2x-cost exp={stt(base_2x_oos['r'].to_numpy())['exp']:+.4f}\n")

    # DSR hurdle: principled null floored at 1/(N-1) of the OOS sample
    var_null = 1.0 / max(2, bs_oos["n"] - 1)
    z1 = nppf(1 - 1.0 / N_TRIALS_CUM)
    z2 = nppf(1 - 1.0 / N_TRIALS_CUM * math.exp(-1))
    sr0 = math.sqrt(var_null) * ((1 - EMC) * z1 + EMC * z2)

    hdr = (f"{'candidate':28s}{'N':>6s}{'exp':>8s}{'dExp':>8s}{'pair_t':>7s}{'WFE':>6s}"
           f"{'avgWin':>7s}{'>=2R%':>7s}{'exp2x':>8s}{'Qpos':>6s}{'Sym+':>6s}{'DSR':>6s}  VERDICT")
    print(hdr); print("-" * len(hdr))

    results = []
    for cell in CANDIDATES:
        blk = collect(data, costs, cell, block=True)
        c_is, c_oos, _ = q_split(blk)
        so, si = stt(c_oos["r"].to_numpy()), stt(c_is["r"].to_numpy())
        dexp = so["exp"] - bs_oos["exp"]
        wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else float("nan")
        wm = win_metrics(c_oos["r"])
        # paired per-signal OOS comparison
        prd = q_split(collect(data, costs, cell, block=False))[1].set_index(["sym", "sig_i"])["r"]
        joined = pd.concat([base_prd_oos.rename("b"), prd.rename("c")], axis=1).dropna()
        d = (joined["c"] - joined["b"]).to_numpy()
        pair_t = (d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))) if len(d) > 5 and d.std(ddof=1) > 0 else float("nan")
        # 2x cost + stability
        oos2 = q_split(collect(data, costs, cell, block=True, cost_mult=2.0))[1]
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
        verdict = "SHIP" if all(gates) else ("watch" if (dexp > 0 and so["exp"] > 0) else "no"
                 )
        results.append((cell[0], verdict, dexp, wm))
        print(f"{cell[0]:28s}{so['n']:6d}{so['exp']:+8.4f}{dexp:+8.4f}{pair_t:+7.2f}"
              f"{wfe:6.2f}{wm['avg_win']:+7.2f}{wm['pct_ge2R']:7.1f}{exp2:+8.4f}"
              f"{qpos:3d}/{qn:<2d}{sym_pos:3d}/{sym_tot:<2d}{dsr:6.2f}  {verdict}")

    ships = [r for r in results if r[1] == "SHIP"]
    print(f"\n>>> SHIP: {len(ships)} of {len(CANDIDATES)}")
    for s in ships:
        print(f"    {s[0]}  (dExp {s[2]:+.4f}, avgWin {s[3]['avg_win']:+.2f}R, >=2R {s[3]['pct_ge2R']:.1f}%)")

if __name__ == "__main__":
    main()
