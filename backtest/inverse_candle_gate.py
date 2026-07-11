"""Full house gate for the INVERSE candle-anatomy filter (favor wicky signals /
drop clean-climax signal bars).

Pre-registered: docs/CANDLE_INVERSE_SPEC_2026-07-10.md
  (SHA256 5c7763300ee04bf00e7224a25ff2b9e774fdab6ca962c4fb988153ce85902b47)
Frame: calendar-quarter stitched walk-forward at REAL per-instrument spread cost
(walkforward_dsr machinery), pure-bracket deployed config. Six locked cells; each
must clear ALL seven gates. FTMO US30/US100 M15 = direction-only corroboration.
"""
import math
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr
from scalper_confluence import CParams, simulate_symbol_c
from experiment import psr, stt
from walkforward_dsr import (load_spreadgated, real_cost_per_side, dsr_hurdle,
                             quarter_walkforward, SPREAD_GATED)
from candle_anatomy_study import candle_features

RNG = np.random.default_rng(20260711)
N_TRIALS = 94   # cumulative research-trial count for DSR deflation (see spec)

PURE_BRACKET = dict(direction="cont", entry_style="limit", entry_offset_atr=0.6,
                    pending_expiry_bars=3, stop_atr=1.0, tp_atr=3.0,
                    lock_trigger_atr=99.0, trail_atr=99.0, max_hold_bars=8,
                    momentum_bars=6, momentum_atr=2.0, atr_period=14,
                    block_overlap=True)

CELLS = [
    ("W1", lambda f: f["adv_wick_atr"] >= 0.20, "keep adv_wick>=0.20"),
    ("W2", lambda f: f["adv_wick_atr"] >= 0.30, "keep adv_wick>=0.30"),
    ("W3", lambda f: f["adv_wick_atr"] >= 0.50, "keep adv_wick>=0.50"),
    ("K1", lambda f: f["body_frac"] < 0.80, "drop body>=0.80"),
    ("K2", lambda f: f["body_frac"] < 0.70, "drop body>=0.70"),
    ("K3", lambda f: not (f["adv_wick_atr"] < 0.20 and f["body_frac"] >= 0.70), "drop clean-climax"),
]


def tape(data, costs, mult=1.0):
    """Stitched trade tape with candle features per trade."""
    recs = []
    for sym, df in data.items():
        cost = costs.get(sym, float("nan"))
        if not np.isfinite(cost):
            continue
        o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        atr = wilder_atr(h, l, c, 14)
        p = CParams(**{**PURE_BRACKET, "cost_atr_frac": cost * mult})
        tr, _ = simulate_symbol_c(df, p, 0, len(df))
        times = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            ft = candle_features(o, h, l, c, atr, t["i"], t["side"])
            if ft is None:
                continue
            ft.update(time=times[t["i"]], sym=sym, r=float(t["r"]))
            recs.append(ft)
    out = pd.DataFrame(recs).sort_values("time").reset_index(drop=True)
    return out


def gate_cell(name, keep_fn, desc, tr, oos_qs, tr2x):
    q = pd.PeriodIndex(pd.to_datetime(tr["time"]), freq="Q")
    oos = tr[q.isin(oos_qs)].copy()
    q2 = pd.PeriodIndex(pd.to_datetime(tr2x["time"]), freq="Q")
    oos2 = tr2x[q2.isin(oos_qs)].copy()

    keep = oos.apply(lambda row: keep_fn(row), axis=1)
    keep2 = oos2.apply(lambda row: keep_fn(row), axis=1)
    filt, filt2 = oos[keep], oos2[keep2]
    base_exp, filt_exp = oos.r.mean(), filt.r.mean()
    base2_exp, filt2_exp = oos2.r.mean(), filt2.r.mean()

    # G2 random-drop placebo (same drop COUNT, 200 draws)
    ndrop = int((~keep).sum())
    idx = np.arange(len(oos))
    pl = np.empty(200)
    rvals = oos.r.to_numpy()
    for b in range(200):
        rd = RNG.choice(idx, size=ndrop, replace=False)
        pl[b] = rvals[np.setdiff1d(idx, rd)].mean()
    p95 = np.percentile(pl, 95)

    # G3 quarters
    qq = pd.PeriodIndex(pd.to_datetime(oos["time"]), freq="Q")
    qtab = oos.assign(q=qq, keep=keep).groupby("q").apply(
        lambda g: g[g.keep].r.mean() - g.r.mean() if g.keep.sum() >= 3 else np.nan,
        include_groups=False).dropna()
    q_ok = int((qtab >= 0).sum())

    # G4 symbols
    stab = oos.assign(keep=keep).groupby("sym").apply(
        lambda g: g[g.keep].r.mean() - g.r.mean() if g.keep.sum() >= 10 else np.nan,
        include_groups=False).dropna()
    sym_ok = int((stab >= 0).sum())

    # G5 DSR
    fr = filt.r.to_numpy(float)
    dsr = psr(fr, dsr_hurdle(n_trials=N_TRIALS, n_obs=fr.size)) if fr.size > 10 else float("nan")

    gates = {
        "G1 filt>base": filt_exp > base_exp,
        "G2 >placebo95": filt_exp > p95,
        "G3 quarters>=60%": len(qtab) > 0 and q_ok >= math.ceil(len(qtab) * 0.6),
        "G4 symbols>=8/12": sym_ok >= 8,
        "G5 DSR>=0.95": np.isfinite(dsr) and dsr >= 0.95,
        "G6 2xcost ok": (filt2_exp > 0) and (filt2_exp > base2_exp),
        "G7 n>=250": len(filt) >= 250,
    }
    npass = sum(gates.values())
    verdict = "PASS" if npass == 7 else "no"
    print(f"\n{name} ({desc}): kept {len(filt)}/{len(oos)} ({len(filt)/len(oos):.1%})")
    print(f"  base OOS {base_exp:+.4f}R | filtered {filt_exp:+.4f}R | placebo95 {p95:+.4f} | DSR {dsr:.3f}")
    print(f"  2x cost: base {base2_exp:+.4f} filt {filt2_exp:+.4f} | quarters {q_ok}/{len(qtab)} | symbols {sym_ok}/{len(stab)}")
    print(f"  gates: {' '.join(k.split()[0]+('Y' if v else 'N') for k, v in gates.items())}  -> {verdict} ({npass}/7)")
    return verdict == "PASS"


def ftmo_corroboration():
    print("\n==== FTMO corroboration (direction-only, never-used data) ====")
    try:
        import MetaTrader5 as mt5
        assert mt5.initialize(path=r"C:/Program Files/FTMO Global Markets MT5 Terminal/terminal64.exe")
        for sym in ("US30.cash", "US100.cash"):
            mt5.symbol_select(sym, True)
            r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 20000)
            if r is None or len(r) < 3000:
                print(f"  {sym}: insufficient history"); continue
            df = pd.DataFrame({"time": r["time"], "open": r["open"], "high": r["high"],
                               "low": r["low"], "close": r["close"],
                               "spread": r["spread"] * mt5.symbol_info(sym).point})
            m = (df["spread"] > 0)
            cost = 0.5 * df.loc[m, "spread"].median() / np.nanmedian(
                wilder_atr(df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(), 14))
            o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
            atr = wilder_atr(h, l, c, 14)
            p = CParams(**{**PURE_BRACKET, "cost_atr_frac": float(cost)})
            tr, _ = simulate_symbol_c(df, p, 0, len(df))
            rows = []
            for t in tr:
                ft = candle_features(o, h, l, c, atr, t["i"], t["side"])
                if ft:
                    rows.append((ft["adv_wick_atr"], float(t["r"])))
            arr = pd.DataFrame(rows, columns=["w", "r"])
            wik, cln = arr[arr.w >= 0.30], arr[arr.w < 0.30]
            print(f"  {sym}: n={len(arr)} cost={cost:.4f} | wicky(w>=0.3) n={len(wik)} R={wik.r.mean():+.4f} "
                  f"| clean n={len(cln)} R={cln.r.mean():+.4f} | direction {'AGREES' if wik.r.mean() > cln.r.mean() else 'DISAGREES'}")
        mt5.shutdown()
    except Exception as e:
        print(f"  (FTMO pull unavailable: {e})")


def main():
    data = load_spreadgated()
    print(f"loaded {len(data)}/12 spread-gated symbols")
    costs = {s: real_cost_per_side(df) for s, df in data.items()}
    for s, cx in sorted(costs.items()):
        print(f"  {s:22s} cost/side {cx:.4f}")
    print("\nbuilding stitched tapes (real cost + 2x cost)...")
    tr = tape(data, costs, 1.0)
    tr2x = tape(data, costs, 2.0)
    wf = quarter_walkforward(tr.rename(columns={"r": "r"})[["time", "sym", "r"]], is_frac=0.70)
    print(f"tape: {len(tr)} trades | stitched OOS quarters: {len(wf['oos_qs'])} | "
          f"OOS n={wf['oos_r'].size} baseline OOS exp={wf['oos_r'].mean():+.4f}R")
    passed = []
    for name, fn, desc in CELLS:
        if gate_cell(name, fn, desc, tr, wf["oos_qs"], tr2x):
            passed.append(name)
    ftmo_corroboration()
    print(f"\n==== FINAL VERDICT: {'PASS on ' + ','.join(passed) if passed else 'ALL 6 CELLS FAIL — inverse filter does not clear the house gate; EA unchanged.'} ====")


if __name__ == "__main__":
    main()
