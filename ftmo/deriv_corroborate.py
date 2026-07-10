"""Independent corroboration of the FTMO edge on Deriv's 2.5-year M15 data.

The FTMO live history is only ~9 months and underpowered. This runs the EXACT
deployed config (limit-pullback 0.6 ATR, stop 1.0, TP 3.0, hold 8, expiry 3,
ladder OFF = pure bracket -- identical to backtest/run_validated.py) on Deriv's
independent spread-gated feed for the SAME instruments.

Question: do Germany_40 and Japan_225 show a POSITIVE out-of-sample edge on
Deriv's 2.5-year data? If yes, the FTMO result is corroborated and not a
short-window artifact.

Reports ALL / IS / OOS expectancy R, t-stat and n at cost_atr_frac 0.0 AND 0.03
for the two targets (Germany_40, Japan_225) plus controls
(Wall_Street_30, US_Tech_100, US_SP_500, BTCUSD).
"""
import os
import sys

# import the validated harness from the backtest folder
HERE = os.path.dirname(os.path.abspath(__file__))
BT = os.path.abspath(os.path.join(HERE, "..", "backtest"))
sys.path.insert(0, BT)

import pandas as pd  # noqa: E402
from scalper_backtest import Params, simulate_symbol, compute_stats  # noqa: E402

DATA_DIR = os.path.join(BT, "data", "derivM15_spreadgated")

TARGETS = ["Germany_40", "Japan_225"]
CONTROLS = ["Wall_Street_30", "US_Tech_100", "US_SP_500", "BTCUSD"]
SYMBOLS = TARGETS + CONTROLS
COSTS = [0.0, 0.03]


def deployed_params(cost):
    """The exact live/validated config (matches run_validated.py)."""
    return Params(
        momentum_bars=6, momentum_atr=2.0, atr_period=14,
        direction="cont", entry_style="limit", entry_offset_atr=0.6,
        pending_expiry_bars=3, stop_atr=1.0, tp_atr=3.0,
        lock_trigger_atr=999.0, trail_atr=0.0,   # ladder off => PURE BRACKET
        max_hold_bars=8, cost_atr_frac=cost,
    )


def split_bounds(n, split):
    if split == "is":
        return 0, int(n * 0.7)
    if split == "oos":
        return int(n * 0.7), n
    return 0, n


def load(sym):
    f = os.path.join(DATA_DIR, sym + ".csv")
    return pd.read_csv(f)


def eval_symbol(df, cost):
    """Return dict split -> Stats for one symbol at one cost."""
    p = deployed_params(cost)
    out = {}
    n = len(df)
    for split in ("all", "is", "oos"):
        lo, hi = split_bounds(n, split)
        rs = simulate_symbol(df, p, lo, hi)
        out[split] = compute_stats(rs)
    return out


def span(df):
    t = pd.to_datetime(df["time"])
    return t.iloc[0].date(), t.iloc[-1].date()


def main():
    # cache loads
    dfs = {s: load(s) for s in SYMBOLS}

    print("=" * 100)
    print("DERIV INDEPENDENT CORROBORATION  (M15 spread-gated feed)")
    d0, d1 = span(dfs["Germany_40"])
    print(f"Window: {d0} -> {d1}   (~2.5 years)   IS=first 70%  OOS=last 30%")
    print("Config: limit-pullback 0.6 ATR | stop 1.0 | TP 3.0 | hold 8 | expiry 3 | ladder OFF (pure bracket)")
    print("=" * 100)

    for cost in COSTS:
        tag = "NO COST (0.0/side)" if cost == 0.0 else f"WITH COST ({cost}/side)"
        print(f"\n### {tag}")
        print(f"{'symbol':16s} | {'ALL exp/t/n':26s} | {'IS exp/t/n':26s} | {'OOS exp/t/n':26s}")
        print("-" * 100)
        for sym in SYMBOLS:
            res = eval_symbol(dfs[sym], cost)
            def cell(st):
                return f"{st.expectancy:+.4f}R t={st.tstat:+5.2f} n={st.n}"
            marker = " *" if sym in TARGETS else "  "
            print(f"{sym:16s}{marker}| {cell(res['all']):26s} | {cell(res['is']):26s} | {cell(res['oos']):26s}")

    # ------- verdicts (based on WITH-COST 0.03, the realistic case) -------
    print("\n" + "=" * 100)
    print("VERDICTS  (realistic cost 0.03/side; OOS = independent last-30% held-out slice)")
    print("=" * 100)
    for sym in SYMBOLS:
        res = eval_symbol(dfs[sym], 0.03)
        oos = res["oos"]
        alln = res["all"]
        role = "TARGET " if sym in TARGETS else "control"
        if oos.expectancy > 0 and oos.tstat >= 1.5:
            v = "CORROBORATED  (positive OOS edge, t>=1.5)"
        elif oos.expectancy > 0:
            v = "WEAK-POSITIVE (OOS>0 but t<1.5, underpowered)"
        else:
            v = "NOT CORROBORATED (OOS expectancy <= 0)"
        print(f"[{role}] {sym:16s} OOS exp={oos.expectancy:+.4f}R t={oos.tstat:+.2f} n={oos.n} "
              f"| ALL exp={alln.expectancy:+.4f}R t={alln.tstat:+.2f} -> {v}")


if __name__ == "__main__":
    main()
