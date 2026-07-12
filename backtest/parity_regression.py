"""Golden regression: parity_engine.run_m0 must reproduce simulate_symbol
trade-for-trade on EVERY manifest CSV before any corrected number is reported.

Pre-registered gate in docs/W2_PARITY_SPEC_2026-07-12.md: identity of
(signal_bar, entry_bar, side, r) with |dr| < 1e-9. Any diff = stop.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import Params, simulate_symbol
from walkforward_dsr import real_cost_per_side
from parity_engine import prep_symbol, run_m0

P = dict(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
         entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
         stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
         max_hold_bars=8)


def main():
    files = sorted(glob.glob(os.path.join(HERE, "data", "*", "*.csv")))
    n_ok = n_fail = 0
    total_trades = 0
    for path in files:
        name = os.path.relpath(path, os.path.join(HERE, "data"))
        raw = pd.read_csv(path)
        nmap = {c.lower(): c for c in raw.columns}
        if not all(k in nmap for k in ("time", "open", "high", "low", "close")):
            print(f"  {name}: SKIP (not OHLC)")
            continue
        df = raw.rename(columns={nmap[k]: k for k in ("time", "open", "high", "low", "close")})
        cost = real_cost_per_side(raw)
        if not np.isfinite(cost):
            cost = 0.03
        sigs = []
        simulate_symbol(df, Params(**P, cost_atr_frac=cost), 0, len(df), signals_out=sigs)
        mine = run_m0(prep_symbol(raw, cost, name))
        ok = len(sigs) == len(mine)
        if ok:
            for (i, eb, sd, r), t in zip(sigs, mine):
                if not (i == t.sig and eb == t.entry_bar and sd == t.side
                        and abs(r - t.r) < 1e-9):
                    ok = False
                    print(f"  {name}: FIRST DIFF at sim=({i},{eb},{sd},{r:.6f}) "
                          f"vs mine=({t.sig},{t.entry_bar},{t.side},{t.r:.6f})")
                    break
        else:
            print(f"  {name}: COUNT DIFF sim={len(sigs)} mine={len(mine)}")
        total_trades += len(sigs)
        if ok:
            n_ok += 1
        else:
            n_fail += 1
            print(f"  {name}: FAIL")
    print(f"\nGolden regression: {n_ok} identical, {n_fail} failed, "
          f"{total_trades} trades compared across {n_ok + n_fail} files.")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
