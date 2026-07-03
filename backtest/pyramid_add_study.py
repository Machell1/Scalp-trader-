"""SINGLE PYRAMIDING ADD STUDY — add once at +1R with stop-to-BE for the whole position.

Hypothesis: the exit-ladder study proved the right tail is where the money is (avg win
1.72R, 16.6% of trades >= +2R under the pure bracket). A trade that reaches +1R is
disproportionately likely to be in that tail, so ADDING there — financed by moving the
whole position's stop to break-even — scales exposure INTO the tail and should raise
avg win R and expectancy per signal without adding initial risk. The known failure mode
(also from the ladder study): the BE stop is itself a truncation — shakeouts through
entry will now stop BOTH units where the baseline would have survived to TP. The paired
test decides which force wins. This is NEW territory (position sizing after entry), not
a re-skin of any rejected lock/trail idea — but the BE move is mechanically related to
the rejected BE-lock, so the honest prior is skeptical.

PRE-REGISTERED cells (3, fixed before running — no scanning):
    add 100% @+1R, stop->BE     (double up; classic pyramid)
    add  50% @+1R, stop->BE     (half-size add; gentler truncation trade-off)
    add 100% @+1.5R, stop->BE   (later add: stronger tail evidence, less room to TP)

Baseline = v1.23 LIVE (pure bracket: SL 1 ATR / TP 3 ATR / hold 8, no lock/trail).

Mechanics (simulate_symbol_c, additive params, default OFF, baseline byte-exact):
  * Trigger on bar CLOSE (unrealized r >= pyr_add_r, close-based like the lock/trail
    engine); the add fills at the NEXT bar's OPEN (causal, no look-ahead).
  * Stop moves to entry (BE) at the trigger close for the WHOLE position, so the fresh
    add is never carried with the original -1R stop.
  * Both units share SL/TP/time exit. R is reported per SIGNAL in units of the INITIAL
    1-unit risk, cost charged on all notional in/out (the add pays its own 2x cost).
  * Worst case AFTER the add ~ -(add_frac * pyr_add_r)R + costs (BE on unit1, add
    stopped at entry); initial risk before the trigger is unchanged at -1R.

Protocol (identical to exit_ladder_study.py / the SHIP gate):
  * 12 spread-gated majors, REAL per-instrument Deriv cost; stitched-OOS quarters
    (first 70% of calendar quarters = IS); PAIRED per-signal t-stat
    (block_overlap=False, identical entries); DSR deflated for the CUMULATIVE research
    count (82 = 68 prior + the 14 cells pre-registered in this 4-study batch);
    2x cost stress; per-quarter/per-symbol stability; win-size metrics.

Sizing caveat (report, don't hide): per-signal R is measured against the initial unit,
but the pyramid deploys up to 2x notional on its best trades. Equal-margin live sizing
would halve the base unit; the per-signal expectancy gain must therefore clear the gate
by enough to survive that normalization — flagged in the output as exp/maxNotional.
"""
from __future__ import annotations
import math
import sys
import numpy as np
import pandas as pd

from scalper_confluence import CParams, simulate_symbol_c
from walkforward_dsr import load_spreadgated, real_cost_per_side
from experiment import EMC, nppf, psr, stt, n_eff_symbols

BRACKET = dict(direction="cont", entry_style="limit", entry_offset_atr=0.6,
               pending_expiry_bars=3, stop_atr=1.0, tp_atr=3.0,
               lock_trigger_atr=99.0, trail_atr=99.0, max_hold_bars=8,
               momentum_bars=6, momentum_atr=2.0, atr_period=14)
N_TRIALS_CUM = 82   # 68 prior + 14 cells in this 4-study batch

# label, pyr_add_r, pyr_add_frac   (BASELINE first: feature OFF)
BASELINE = ("BASELINE pure bracket", 0.0, 1.0)
CANDIDATES = [
    ("add 100% @+1R  ->BE",   1.0, 1.0),
    ("add  50% @+1R  ->BE",   1.0, 0.5),
    ("add 100% @+1.5R ->BE",  1.5, 1.0),
]


def mkp(cell, cost, block=True):
    _, add_r, frac = cell
    return CParams(**BRACKET, pyr_add_r=add_r, pyr_add_frac=frac,
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
                med_win=(np.median(w) if w.size else 0.0),
                pct_ge2R=float((r >= 2.0).mean() * 100))


def main():
    data = load_spreadgated()
    if len(data) < 8:
        print("Need spread-gated CSVs in data/derivM15_spreadgated/ — run fetch_spreadgated.py "
              "(MT5 terminal open).", file=sys.stderr)
        return 1
    costs = {s: real_cost_per_side(df) for s, df in data.items()}
    pr, _ = n_eff_symbols(data)
    haircut = math.sqrt(pr / len(data))
    print(f"SINGLE PYRAMIDING ADD STUDY — {len(data)} spread-gated majors, real "
          f"per-instrument cost, N_eff={pr:.1f} (t-haircut x{haircut:.2f})")
    print(f"DSR deflation: {N_TRIALS_CUM} cumulative research trials\n")

    base_blk = collect(data, costs, BASELINE, block=True)
    base_is, base_oos, oos_qs = q_split(base_blk)
    bs_oos = stt(base_oos["r"].to_numpy())
    base_prd_oos = q_split(collect(data, costs, BASELINE, block=False))[1] \
        .set_index(["sym", "sig_i"])["r"]
    base_2x = stt(q_split(collect(data, costs, BASELINE, block=True, cost_mult=2.0))[1]["r"].to_numpy())
    bwm = win_metrics(base_oos["r"])
    print(f"BASELINE OOS (stitched quarters, real cost): N={bs_oos['n']} exp={bs_oos['exp']:+.4f} "
          f"t={bs_oos['t']:+.2f}  avgWin={bwm['avg_win']:+.2f}R medWin={bwm['med_win']:+.2f}R "
          f">=2R {bwm['pct_ge2R']:.1f}%  2x-cost exp={base_2x['exp']:+.4f}\n")

    var_null = 1.0 / max(2, bs_oos["n"] - 1)
    z1 = nppf(1 - 1.0 / N_TRIALS_CUM)
    z2 = nppf(1 - 1.0 / N_TRIALS_CUM * math.exp(-1))
    sr0 = math.sqrt(var_null) * ((1 - EMC) * z1 + EMC * z2)

    hdr = (f"{'candidate':24s}{'N':>6s}{'exp':>8s}{'dExp':>8s}{'e/maxNot':>9s}{'pair_t':>7s}"
           f"{'WFE':>6s}{'avgWin':>7s}{'>=2R%':>7s}{'exp2x':>8s}{'Qpos':>6s}{'Sym+':>6s}"
           f"{'DSR':>6s}  VERDICT")
    print(hdr); print("-" * len(hdr))

    results = []
    for cell in CANDIDATES:
        blk = collect(data, costs, cell, block=True)
        c_is, c_oos, _ = q_split(blk)
        so, si = stt(c_oos["r"].to_numpy()), stt(c_is["r"].to_numpy())
        dexp = so["exp"] - bs_oos["exp"]
        wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else float("nan")
        wm = win_metrics(c_oos["r"])
        # notional-normalized expectancy: pessimistic equal-margin view (every trade
        # sized as if it will deploy the full 1 + add_frac notional)
        exp_norm = so["exp"] / (1.0 + cell[2])
        prd = q_split(collect(data, costs, cell, block=False))[1].set_index(["sym", "sig_i"])["r"]
        joined = pd.concat([base_prd_oos.rename("b"), prd.rename("c")], axis=1).dropna()
        d = (joined["c"] - joined["b"]).to_numpy()
        pair_t = (d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))) if len(d) > 5 and d.std(ddof=1) > 0 else float("nan")
        exp2 = stt(q_split(collect(data, costs, cell, block=True, cost_mult=2.0))[1]["r"].to_numpy())["exp"]
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
        results.append((cell[0], verdict, dexp, wm))
        print(f"{cell[0]:24s}{so['n']:6d}{so['exp']:+8.4f}{dexp:+8.4f}{exp_norm:+9.4f}"
              f"{pair_t:+7.2f}{wfe:6.2f}{wm['avg_win']:+7.2f}{wm['pct_ge2R']:7.1f}{exp2:+8.4f}"
              f"{qpos:3d}/{qn:<2d}{sym_pos:3d}/{sym_tot:<2d}{dsr:6.2f}  {verdict}")

    print("\nNote: e/maxNot = OOS exp divided by (1 + add_frac) — the pessimistic "
          "equal-margin normalization; compare it to the baseline exp, not to 0.")
    ships = [r for r in results if r[1] == "SHIP"]
    print(f"\n>>> SHIP: {len(ships)} of {len(CANDIDATES)}")
    for s in ships:
        print(f"    {s[0]}  (dExp {s[2]:+.4f}, avgWin {s[3]['avg_win']:+.2f}R, "
              f">=2R {s[3]['pct_ge2R']:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
