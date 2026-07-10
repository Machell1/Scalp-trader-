"""Stage 2 — does the VALIDATED strategy actually have an edge on each
cost-gate survivor, tested on FTMO's OWN M15 history?

Passing the cost gate is necessary, not sufficient. This runs the exact deployed
engine (momentum 6/2.0 ATR -> pullback-LIMIT 0.6 ATR -> stop 1.0 / TP 3.0 / hold 8,
PURE BRACKET) via the already-audited simulate_symbol(), on FTMO's own bars, at each
symbol's own measured cost.

Anti-data-mining controls, both mandatory:
  * POSITIVE CONTROL: US30/US100/BTCUSD (already validated) must show a positive
    edge here. If they don't, the window is too short/noisy and NO result on a new
    symbol can be trusted.
  * NEGATIVE CONTROL: per symbol, shuffle bar-to-bar returns (destroys momentum,
    preserves return distribution) and rebuild the price path. The strategy must
    show ~0 there. If it doesn't, the harness is broken.
Multiple-comparisons: testing K symbols, ~5% will look "significant" by luck.
We report K and the binomial expectation, and require IS>0 AND OOS>0.
"""
import csv, sys
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

sys.path.insert(0, r"C:/Users/Sanique Richards/Documents/Homework Heroes/Pokemon/Scalp-trader/backtest")
from scalper_backtest import Params, simulate_symbol          # audited engine

FTMO_PATH = r"C:/Program Files/FTMO Global Markets MT5 Terminal/terminal64.exe"
KNOWN_GOOD = {"US30.cash", "US100.cash", "BTCUSD"}

def validated_params(cost):
    return Params(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
                  entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
                  stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
                  max_hold_bars=8, cost_atr_frac=cost)

def stats(rs):
    rs = np.asarray(rs, float)
    if len(rs) < 3:
        return dict(n=len(rs), exp=0.0, t=0.0, win=0.0)
    sd = rs.std(ddof=1)
    return dict(n=len(rs), exp=float(rs.mean()), win=float((rs > 0).mean()),
                t=float(rs.mean() / (sd / np.sqrt(len(rs)))) if sd > 0 else 0.0)

def rates_df(sym, bars=20000):
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, bars)
    if r is None or len(r) < 2000:
        return None
    return pd.DataFrame({"time": r['time'], "open": r['open'], "high": r['high'],
                         "low": r['low'], "close": r['close'], "volume": r['tick_volume']})

def shuffled(df, seed):
    """Preserve return distribution, destroy serial structure (momentum)."""
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

def main():
    if not mt5.initialize(path=FTMO_PATH):
        print("init failed:", mt5.last_error()); return
    surv = [r for r in csv.DictReader(open("ftmo_universe.csv")) if r["pass"] == "True"]
    # always include the known-good trio as positive controls even if borderline
    names = {r["symbol"]: float(r["cost_atr_side"]) for r in surv}
    for k in KNOWN_GOOD:
        names.setdefault(k, 0.03)
    print(f"testing {len(names)} symbols (cost-gate survivors + positive controls)\n")
    print(f"{'symbol':16s} {'cost':>6s} {'n':>5s} {'ALL exp':>8s} {'t':>6s} | {'IS exp':>7s} {'OOS exp':>8s} "
          f"| {'shuf exp':>8s} | verdict")
    print("-" * 100)
    results = []
    for sym, cost in sorted(names.items(), key=lambda kv: kv[0]):
        mt5.symbol_select(sym, True)
        df = rates_df(sym)
        if df is None:
            print(f"{sym:16s}  (insufficient history)"); continue
        p = validated_params(cost)
        n = len(df)
        allr = simulate_symbol(df, p, 0, n)
        split = int(0.7 * n)
        isr = simulate_symbol(df, p, 0, split)
        oosr = simulate_symbol(df, p, split, n)
        shr = []
        for s in range(3):                       # 3 shuffles, pooled
            shr += simulate_symbol(shuffled(df, 1000 + s), p, 0, n)
        A, I, O, S = stats(allr), stats(isr), stats(oosr), stats(shr)
        good = (I["exp"] > 0) and (O["exp"] > 0) and (A["t"] > 1.5) and (A["n"] >= 60)
        tag = ("CONTROL " if sym in KNOWN_GOOD else "") + ("CANDIDATE" if good else "no")
        print(f"{sym:16s} {cost:6.3f} {A['n']:5d} {A['exp']:+8.4f} {A['t']:+6.2f} | "
              f"{I['exp']:+7.4f} {O['exp']:+8.4f} | {S['exp']:+8.4f} | {tag}")
        results.append((sym, A, I, O, S, good))
    K = len(results)
    hits = [r for r in results if r[5]]
    newhits = [r for r in hits if r[0] not in KNOWN_GOOD]
    ctrl_ok = [r for r in results if r[0] in KNOWN_GOOD and r[5]]
    print("-" * 100)
    print(f"symbols tested K={K}; passed both-window filter: {len(hits)} "
          f"(expected ~{0.25*K:.1f} by chance at 25% base rate under a null)")
    print(f"POSITIVE CONTROL: {len(ctrl_ok)}/3 known-good symbols reproduced an edge on FTMO data")
    print(f"NEW candidates: {[r[0] for r in newhits]}")
    print("Shuffled-control column must be ~0.00 for every row; any large positive = harness bug.")
    mt5.shutdown()

if __name__ == "__main__":
    main()
