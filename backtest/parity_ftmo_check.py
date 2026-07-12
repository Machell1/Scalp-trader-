"""Second-venue direction check: corrected enumeration on FTMO's own M15 history.

Pre-registered in docs/W2_PARITY_SPEC_2026-07-12.md (direction evidence only --
FTMO ~9 months can never clear a gate). READ-ONLY terminal access.

Compares, on identical FTMO bars at FTMO cost (indices: spread only):
  control-method tape (M0 + post-hoc W2)  vs  M1 live-parity (w=4)
If the Deriv finding is real (not a data artifact), the same collapse direction
must appear here.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr
from parity_engine import prep_symbol, run_m0, run_live

SYMS = ["US30.cash", "US100.cash", "JP225.cash"]
TERM = r"C:/Program Files/FTMO Global Markets MT5 Terminal/terminal64.exe"


def fetch(sym):
    import MetaTrader5 as mt5
    if not mt5.initialize(path=TERM):
        raise RuntimeError(f"mt5 init failed: {mt5.last_error()}")
    mt5.symbol_select(sym, True)
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 30000)
    info = mt5.symbol_info(sym)
    mt5.shutdown()
    if r is None or len(r) < 3000:
        return None, None
    df = pd.DataFrame({"time": pd.to_datetime(r["time"], unit="s"),
                       "open": r["open"], "high": r["high"],
                       "low": r["low"], "close": r["close"]})
    sp = r["spread"].astype(float) * info.point
    atr = wilder_atr(df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(), 14)
    med_atr = float(np.nanmedian(atr))
    m = sp > 0
    cost = 0.5 * float(np.median(sp[m])) / med_atr if m.sum() >= 100 and med_atr > 0 else np.nan
    return df, cost


def main():
    print("FTMO second-venue direction check (read-only)")
    ctl_all, m1_all = [], []
    for sym in SYMS:
        df, cost = fetch(sym)
        if df is None or not np.isfinite(cost):
            print(f"  {sym}: no data/cost -- skipped")
            continue
        s = prep_symbol(df, cost, sym)
        ctl = [t.r for t in run_m0(s)
               if np.isfinite(s.watr[t.sig]) and s.watr[t.sig] >= 0.30]
        m1 = [t.r for t in run_live([s], thr={sym: 0.30}, caps=None, window=4)[0]]
        print(f"  {sym}: bars={len(df)} cost={cost:.4f} | control n={len(ctl)} "
              f"exp={np.mean(ctl) if ctl else float('nan'):+.4f} | M1(w4) n={len(m1)} "
              f"exp={np.mean(m1) if m1 else float('nan'):+.4f}")
        ctl_all += ctl
        m1_all += m1
    if ctl_all and m1_all:
        print(f"\n  POOLED: control n={len(ctl_all)} exp={np.mean(ctl_all):+.4f} "
              f"| M1 live-parity n={len(m1_all)} exp={np.mean(m1_all):+.4f}")
        print("  (direction evidence only; ~9 months, one venue)")


if __name__ == "__main__":
    main()
