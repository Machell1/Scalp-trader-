"""Empirical false-positive (null) rate of the ftmo_edge_test candidate filter.

For every tested symbol we destroy the serial structure (shuffle bar-to-bar
log-returns, rebuild the path -- exactly ftmo_edge_test.shuffled()) and run the
IDENTICAL candidate filter used in ftmo_edge_test.py:

    (IS exp > 0) AND (OOS exp > 0) AND (ALL-window t > 1.5) AND (n >= 60)

on the same validated Params. Under the shuffle there is BY CONSTRUCTION no
momentum edge, so any pass is a false positive. The fraction of shuffled runs
that pass = the per-test false-positive rate p0. We then ask, with K=18
non-control symbols actually tested, how many false 'candidates' we'd expect
(18*p0) and the binomial probability of >=4 hits arising by pure chance.
"""
import csv, sys, math
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

sys.path.insert(0, r"C:/Users/Sanique Richards/Documents/Homework Heroes/Pokemon/Scalp-trader/backtest")
from scalper_backtest import Params, simulate_symbol          # audited engine

FTMO_PATH = r"C:/Program Files/FTMO Global Markets MT5 Terminal/terminal64.exe"
UNIVERSE  = r"C:/Users/Sanique Richards/Documents/Homework Heroes/Pokemon/Scalp-trader/ftmo/ftmo_universe.csv"
KNOWN_GOOD = {"US30.cash", "US100.cash", "BTCUSD"}
SEEDS = range(0, 20)


def validated_params(cost):
    return Params(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
                  entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
                  stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
                  max_hold_bars=8, cost_atr_frac=cost)


def stats(rs):
    rs = np.asarray(rs, float)
    if len(rs) < 3:
        return dict(n=len(rs), exp=0.0, t=0.0)
    sd = rs.std(ddof=1)
    return dict(n=len(rs), exp=float(rs.mean()),
                t=float(rs.mean() / (sd / np.sqrt(len(rs)))) if sd > 0 else 0.0)


def rates_df(sym, bars=20000):
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, bars)
    if r is None or len(r) < 2000:
        return None
    return pd.DataFrame({"time": r['time'], "open": r['open'], "high": r['high'],
                         "low": r['low'], "close": r['close'], "volume": r['tick_volume']})


def shuffled(df, seed):
    """EXACT copy of ftmo_edge_test.shuffled(): preserve return distribution,
    destroy serial structure (momentum)."""
    rng = np.random.default_rng(seed)
    c = df["close"].to_numpy(float)
    ret = np.diff(np.log(c))
    rng.shuffle(ret)
    newc = c[0] * np.exp(np.concatenate([[0], np.cumsum(ret)]))
    scale = newc / c
    out = df.copy()
    for col in ("open", "high", "low", "close"):
        out[col] = df[col].to_numpy(float) * scale
    return out


def passes_filter(df, p):
    """Same candidate filter used in ftmo_edge_test.py main()."""
    n = len(df)
    allr = simulate_symbol(df, p, 0, n)
    split = int(0.7 * n)
    isr = simulate_symbol(df, p, 0, split)
    oosr = simulate_symbol(df, p, split, n)
    A, I, O = stats(allr), stats(isr), stats(oosr)
    return (I["exp"] > 0) and (O["exp"] > 0) and (A["t"] > 1.5) and (A["n"] >= 60)


def binom_ge(k, n, p):
    """P(X >= k) for X ~ Binomial(n, p)."""
    if p <= 0:
        return 0.0 if k > 0 else 1.0
    tail = 0.0
    for i in range(k, n + 1):
        tail += math.comb(n, i) * p**i * (1 - p)**(n - i)
    return tail


def main():
    if not mt5.initialize(path=FTMO_PATH):
        print("init failed:", mt5.last_error()); return
    surv = [r for r in csv.DictReader(open(UNIVERSE)) if r["pass"] == "True"]
    names = {r["symbol"]: float(r["cost_atr_side"]) for r in surv}
    for k in KNOWN_GOOD:
        names.setdefault(k, 0.03)
    print(f"testing {len(names)} symbols x {len(SEEDS)} shuffle seeds "
          f"= {len(names)*len(SEEDS)} null runs\n")
    print(f"{'symbol':16s} {'cost':>6s} {'n_null':>6s} {'passes':>7s} {'rate':>7s}")
    print("-" * 48)

    total_runs = 0
    total_pass = 0
    per_symbol = {}
    for sym, cost in sorted(names.items(), key=lambda kv: kv[0]):
        mt5.symbol_select(sym, True)
        df = rates_df(sym)
        if df is None:
            print(f"{sym:16s}  (insufficient history)"); continue
        p = validated_params(cost)
        runs = 0
        hits = 0
        for seed in SEEDS:
            sdf = shuffled(df, seed)
            runs += 1
            if passes_filter(sdf, p):
                hits += 1
        per_symbol[sym] = (runs, hits)
        total_runs += runs
        total_pass += hits
        print(f"{sym:16s} {cost:6.3f} {runs:6d} {hits:7d} {hits/runs:7.3f}")

    print("-" * 48)
    p0 = total_pass / total_runs if total_runs else 0.0
    print(f"\nTOTAL null runs: {total_runs}")
    print(f"TOTAL passes   : {total_pass}")
    print(f"PER-TEST FALSE-POSITIVE RATE p0 = {p0:.4f}  ({total_pass}/{total_runs})")

    K = len(names) - len(KNOWN_GOOD & set(names))   # non-control symbols tested
    exp_false = K * p0
    p_ge4 = binom_ge(4, K, p0)
    print(f"\nK (non-control symbols actually tested) = {K}")
    print(f"expected # false candidates = K*p0 = {K}*{p0:.4f} = {exp_false:.3f}")
    print(f"P(>=4 false hits by chance) = Binom(k>=4; n={K}, p={p0:.4f}) = {p_ge4:.5f}")

    # also report P(>=4) using per-symbol heterogeneity would be more precise,
    # but the pooled p0 is the requested statistic.
    mt5.shutdown()

    print("\n=== MACHINE-READABLE ===")
    print(f"p0={p0:.6f}")
    print(f"total_runs={total_runs}")
    print(f"total_pass={total_pass}")
    print(f"K={K}")
    print(f"expected_false={exp_false:.4f}")
    print(f"p_ge4={p_ge4:.6f}")


if __name__ == "__main__":
    main()
