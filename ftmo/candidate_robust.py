"""Robustness check for the genuinely NEW FTMO crypto candidates that have NO
independent Deriv-universe validation: BNBUSD and DASHUSD.

A cost-gate pass + a single positive both-window number is NOT enough for a
symbol that was never in the validated universe. A short-window or one-regime
artifact will show a positive pooled expectancy while being entirely driven by a
single stretch of history or by a knife-edge parameter peak. This script runs
three orthogonal robustness tests using the AUDITED engine (simulate_symbol) on
FTMO's own M15 bars:

  (a) WALK-FORWARD  : 5 equal sequential blocks; expectancy per block. Robust ->
      positive in most blocks. Fragile -> one block carries it.
  (b) PARAM NEIGHBOURHOOD : vary entry_offset_atr {0.4,0.6,0.8}, momentum_atr
      {1.5,2.0,2.5}, tp_atr {2.0,3.0,4.0} one at a time around the validated
      config. Robust -> stays positive across the neighbourhood. Overfit ->
      only the exact peak is positive.
  (c) COST SENSITIVITY : recompute expectancy at 1x / 1.5x / 2x measured cost.

BTCUSD (already validated, cheapest crypto) is pulled as a POSITIVE-CONTROL /
history-length reference: each candidate's bars_used is compared to BTCUSD's.
"""
import sys
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

sys.path.insert(0, r"C:/Users/Sanique Richards/Documents/Homework Heroes/Pokemon/Scalp-trader/backtest")
from scalper_backtest import Params, simulate_symbol          # audited engine

FTMO_PATH = r"C:/Program Files/FTMO Global Markets MT5 Terminal/terminal64.exe"

# measured per-side cost (fraction of ATR), from the FTMO cost gate
COST = {"BNBUSD": 0.003, "DASHUSD": 0.037, "BTCUSD": 0.0023}
CANDIDATES = ["BNBUSD", "DASHUSD"]
REF = "BTCUSD"


def validated_params(cost, entry_offset_atr=0.6, momentum_atr=2.0, tp_atr=3.0):
    return Params(momentum_bars=6, momentum_atr=momentum_atr, atr_period=14,
                  direction="cont", entry_style="limit",
                  entry_offset_atr=entry_offset_atr, pending_expiry_bars=3,
                  stop_atr=1.0, tp_atr=tp_atr, lock_trigger_atr=999.0,
                  trail_atr=0.0, max_hold_bars=8, cost_atr_frac=cost)


def st(rs):
    rs = np.asarray(rs, float)
    if len(rs) < 3:
        return dict(n=len(rs), exp=0.0, t=0.0, win=0.0, tot=float(rs.sum()))
    sd = rs.std(ddof=1)
    return dict(n=len(rs), exp=float(rs.mean()), win=float((rs > 0).mean()),
                t=float(rs.mean() / (sd / np.sqrt(len(rs)))) if sd > 0 else 0.0,
                tot=float(rs.sum()))


def rates_df(sym, bars=20000):
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, bars)
    if r is None or len(r) < 2000:
        return None
    return pd.DataFrame({"time": r['time'], "open": r['open'], "high": r['high'],
                         "low": r['low'], "close": r['close'], "volume": r['tick_volume']})


def walk_forward(df, cost, k=5):
    """Split bar-history into k equal sequential blocks; expectancy per block."""
    n = len(df)
    p = validated_params(cost)
    out = []
    for b in range(k):
        lo = int(n * b / k)
        hi = int(n * (b + 1) / k)
        rs = simulate_symbol(df, p, lo, hi)
        out.append(st(rs))
    return out


def neighbourhood(df, cost):
    """Vary each param one at a time; return list of (label, stat)."""
    n = len(df)
    rows = []
    for v in (0.4, 0.6, 0.8):
        rs = simulate_symbol(df, validated_params(cost, entry_offset_atr=v), 0, n)
        rows.append((f"entry_off={v}", st(rs)))
    for v in (1.5, 2.0, 2.5):
        rs = simulate_symbol(df, validated_params(cost, momentum_atr=v), 0, n)
        rows.append((f"mom_atr={v}", st(rs)))
    for v in (2.0, 3.0, 4.0):
        rs = simulate_symbol(df, validated_params(cost, tp_atr=v), 0, n)
        rows.append((f"tp_atr={v}", st(rs)))
    return rows


def cost_sensitivity(df, cost):
    n = len(df)
    rows = []
    for mult in (1.0, 1.5, 2.0):
        rs = simulate_symbol(df, validated_params(cost * mult), 0, n)
        rows.append((mult, st(rs)))
    return rows


def main():
    if not mt5.initialize(path=FTMO_PATH):
        print("init failed:", mt5.last_error()); return
    ai = mt5.account_info()
    print(f"connected: {ai.company} | {ai.server}\n")

    dfs = {}
    for sym in [REF] + CANDIDATES:
        mt5.symbol_select(sym, True)
        df = rates_df(sym)
        if df is None:
            print(f"{sym}: insufficient history"); continue
        dfs[sym] = df

    ref_bars = len(dfs[REF]) if REF in dfs else None
    ref_span = None
    if ref_bars:
        t = pd.to_datetime(dfs[REF]["time"], unit="s")
        ref_span = (t.iloc[0], t.iloc[-1])

    print("=" * 78)
    print("HISTORY LENGTH (M15 bars pulled; 20000 requested)")
    print("=" * 78)
    print(f"{'symbol':10s} {'bars':>7s} {'first':>17s} {'last':>17s}  {'vs BTC':>8s}")
    for sym in [REF] + CANDIDATES:
        if sym not in dfs:
            continue
        df = dfs[sym]
        t = pd.to_datetime(df["time"], unit="s")
        rel = f"{len(df)/ref_bars*100:5.1f}%" if ref_bars else "n/a"
        print(f"{sym:10s} {len(df):7d} {str(t.iloc[0])[:16]:>17s} {str(t.iloc[-1])[:16]:>17s}  {rel:>8s}")

    for sym in CANDIDATES:
        if sym not in dfs:
            continue
        df = dfs[sym]
        cost = COST[sym]
        n = len(df)
        full = st(simulate_symbol(df, validated_params(cost), 0, n))
        print("\n" + "=" * 78)
        print(f"{sym}   (cost={cost}, bars={n})   FULL-SAMPLE: "
              f"exp={full['exp']:+.4f}R  t={full['t']:+.2f}  win={full['win']*100:.1f}%  "
              f"n={full['n']}  totR={full['tot']:+.1f}")
        print("=" * 78)

        print("\n(a) WALK-FORWARD  (5 equal sequential blocks)")
        print(f"    {'block':6s} {'n':>5s} {'exp(R)':>9s} {'t':>6s} {'win%':>6s} {'totR':>8s}")
        wf = walk_forward(df, cost)
        pos = 0
        for i, s in enumerate(wf):
            flag = "+" if s["exp"] > 0 else ""
            if s["exp"] > 0:
                pos += 1
            print(f"    {i+1:6d} {s['n']:5d} {s['exp']:+9.4f} {s['t']:+6.2f} "
                  f"{s['win']*100:6.1f} {s['tot']:+8.1f} {flag}")
        exps = [s["exp"] for s in wf]
        best = max(range(len(exps)), key=lambda i: wf[i]["tot"])
        tot_all = sum(s["tot"] for s in wf)
        tot_ex_best = tot_all - wf[best]["tot"]
        print(f"    -> {pos}/5 blocks positive expectancy;  totR all={tot_all:+.1f}, "
              f"excl. best block(#{best+1})={tot_ex_best:+.1f}")

        print("\n(b) PARAMETER NEIGHBOURHOOD  (one param varied at a time; * = validated)")
        print(f"    {'param':16s} {'n':>5s} {'exp(R)':>9s} {'t':>6s} {'win%':>6s}")
        nb = neighbourhood(df, cost)
        npos = 0
        for label, s in nb:
            star = " *" if label in ("entry_off=0.6", "mom_atr=2.0", "tp_atr=3.0") else ""
            if s["exp"] > 0:
                npos += 1
            print(f"    {label:16s} {s['n']:5d} {s['exp']:+9.4f} {s['t']:+6.2f} "
                  f"{s['win']*100:6.1f}{star}")
        print(f"    -> {npos}/{len(nb)} neighbourhood configs positive")

        print("\n(c) COST SENSITIVITY")
        print(f"    {'mult':>5s} {'cost':>7s} {'exp(R)':>9s} {'t':>6s} {'win%':>6s}")
        cs = cost_sensitivity(df, cost)
        for mult, s in cs:
            print(f"    {mult:5.1f} {cost*mult:7.4f} {s['exp']:+9.4f} {s['t']:+6.2f} "
                  f"{s['win']*100:6.1f}")
        survives_2x = cs[-1][1]["exp"] > 0
        print(f"    -> expectancy at 2x cost {'STAYS positive' if survives_2x else 'goes NEGATIVE'}")

    mt5.shutdown()


if __name__ == "__main__":
    main()
