"""Volatility-regime sync study: sizing (V1a/V1b) vs confluence (V2) on the live tape.

Pre-registered: docs/VOLSYNC_SPEC_2026-07-11.md
  (SHA256 a9b1fb95a844dd0325ef8d13f3535f9ff488954070e8b78b9703fac4b2180d02)
Gate order: OOS monotonicity kill-point -> MC vs flat baseline -> 20-draw
relabeling placebo -> per-symbol sign stability. All numbers reported verbatim.
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr, Params, simulate_symbol
from walkforward_dsr import real_cost_per_side
from prop_mc_scalper import challenge

RNG = np.random.default_rng(20260716)
TRIO = [("Wall_Street_30", "Wall_Street_30.csv"), ("US_Tech_100", "US_Tech_100.csv"),
        ("Japan_225", "Japan_225.csv")]
P = dict(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
         entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
         stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
         max_hold_bars=8)


def build():
    rows = []
    for sym, fn in TRIO:
        raw = pd.read_csv(os.path.join(HERE, "data", "derivM15_spreadgated", fn))
        n = {c.lower(): c for c in raw.columns}
        df = raw.rename(columns={n[k]: k for k in ("time", "open", "high", "low", "close") if k in n})
        cost = real_cost_per_side(raw)
        o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        atr = wilder_atr(h, l, c, 14)
        atr_pct = pd.Series(atr).rolling(2000, min_periods=200).rank(pct=True).to_numpy()
        up = h - np.maximum(o, c); dn = np.minimum(o, c) - l
        sigs = []
        simulate_symbol(df, Params(**P, cost_atr_frac=cost), 0, len(df), signals_out=sigs)
        dt = pd.to_datetime(df["time"])
        ep = ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy()
        q = pd.PeriodIndex(dt, freq="Q")
        qs = sorted(q.unique()); oos_qs = set(qs[int(len(qs) * 0.7):])
        for (i, eb, side, r) in sigs:
            if not (np.isfinite(atr[i]) and atr[i] > 0):
                continue
            if ((up[i] if side > 0 else dn[i]) / atr[i]) < 0.30:
                continue
            if not np.isfinite(atr_pct[i]):
                continue
            terc = 0 if atr_pct[i] < 1/3 else (1 if atr_pct[i] < 2/3 else 2)
            rows.append((int(ep[i]), sym, float(r), terc, str(q[i]), q[i] in oos_qs))
    t = pd.DataFrame(rows, columns=["ep", "sym", "r", "terc", "quarter", "oos"]).sort_values("ep")
    return t.reset_index(drop=True)


def mc_both(t, mults, nsim=8000):
    days = {}
    for ep, r, terc in zip(t.ep, t.r, t.terc):
        days.setdefault(ep // 86400, []).append(r * mults[terc])
    dl = [v for v in days.values() if v]
    rng = np.random.default_rng(7)
    r1 = np.array([challenge(dl, rng, 0.3, 10.0, 365) for _ in range(nsim)])
    p1 = float(np.mean(r1[:, 0] == 1)); bust = float(np.mean(r1[:, 0] == 0))
    r2 = np.array([challenge(dl, rng, 0.3, 5.0, 365)[0] for _ in range(nsim // 2)])
    p2 = float(np.mean(r2 == 1))
    return p1 * p2, bust


def main():
    t = build()
    oos = t[t.oos]
    print(f"trio W2 tape: {len(t)} trades ({len(oos)} OOS) | tercile counts {t.terc.value_counts().sort_index().tolist()}")

    # GATE 1: OOS monotonicity kill-point
    print("\nGATE 1 — OOS tercile expectancy (kill-point):")
    for k, lbl in ((0, "lowVol"), (1, "midVol"), (2, "highVol")):
        g = oos[oos.terc == k]
        print(f"  {lbl:8s} n={len(g):4d} exp={g.r.mean():+.4f}R")
    from scipy.stats import spearmanr
    qok = qn = 0
    for qq, g in oos.groupby("quarter"):
        if len(g) < 60:
            continue
        means = g.groupby("terc").r.mean()
        if len(means) == 3:
            qn += 1
            if spearmanr(means.index, means.values).statistic > 0:
                qok += 1
    mono = qn > 0 and qok >= np.ceil(0.6 * qn)
    print(f"  quarters with positive tercile-rank ordering: {qok}/{qn} -> {'PASS' if mono else 'FAIL -> all arms dead'}")
    if not mono:
        print("\n==== VERDICT: T4 monotonicity does not hold OOS — in-sample artifact; no arm proceeds. ====")
        return

    ARMS = [("V1a sizing {0.5,0.75,1.0}", {0: 0.50, 1: 0.75, 2: 1.00}, None),
            ("V1b sizing {0.6,0.9,1.2}", {0: 0.60, 1: 0.90, 2: 1.20}, None),
            ("V2 drop lowVol", {0: 0.0, 1: 1.0, 2: 1.0}, None)]
    base_both, base_bust = mc_both(t, {0: 1.0, 1: 1.0, 2: 1.0})
    print(f"\nBASELINE flat 0.3%: both={base_both:.1%} bust={base_bust:.1%}")

    for name, mults, _ in ARMS:
        both, bust = mc_both(t, mults)
        g2 = both > base_both and bust <= base_bust
        # GATE 3 placebo: shuffle tercile labels within symbol (20 draws)
        pl = []
        for b in range(20):
            tp = t.copy()
            tp["terc"] = tp.groupby("sym")["terc"].transform(lambda s: RNG.permutation(s.to_numpy()))
            pl.append(mc_both(tp, mults, nsim=3000)[0])
        p95 = np.percentile(pl, 95)
        g3 = both > p95
        # GATE 4 per-symbol OOS sign
        flips = 0
        for sym, g in oos.groupby("sym"):
            armr = g.r * g.terc.map(mults)
            armr = armr[g.terc.map(mults) > 0]
            if len(armr) > 30 and armr.mean() < 0:
                flips += 1
        g4 = flips == 0
        verdict = "PASS all gates" if (g2 and g3 and g4) else "no"
        print(f"{name:26s}: both={both:.1%} bust={bust:.1%} | placebo95={p95:.1%} | symFlips={flips} "
              f"| G2 {'Y' if g2 else 'N'} G3 {'Y' if g3 else 'N'} G4 {'Y' if g4 else 'N'} -> {verdict}")

    print("\nDone. Ship rule per spec: a passing arm -> v1.30 flag-gated module + shadow + sign-off.")


if __name__ == "__main__":
    main()
