"""Pull the 12 spread-gated Deriv M15 majors (EA v1.2 whitelist) with spread column.

Writes data/derivM15_spreadgated/<sym>.csv — columns time,open,high,low,close,volume,spread
(volume = tick_volume; spread = points from MT5 rates).

Requires MetaTrader5 + logged-in Deriv terminal.
"""
from __future__ import annotations

import os
import time as _t

import MetaTrader5 as mt5
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "derivM15_spreadgated")
COUNT = 70000

SPREAD_GATED = [
    "BTCUSD", "ETHUSD", "XRPUSD", "SOLUSD",
    "US Tech 100", "US SP 500", "Wall Street 30", "US Small Cap 2000",
    "Germany 40", "UK 100", "Japan 225", "France 40",
]


def sym_to_file(sym: str) -> str:
    return sym.replace(" ", "_") + ".csv"


def main():
    os.makedirs(OUT, exist_ok=True)
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    print(f"connected: {mt5.terminal_info().company}\n")
    ok = 0
    for sym in SPREAD_GATED:
        if not mt5.symbol_select(sym, True):
            print(f"  SKIP {sym:22s} (not selectable)")
            continue
        _t.sleep(0.05)
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, COUNT)
        if r is None or len(r) < 2000:
            n = 0 if r is None else len(r)
            print(f"  SKIP {sym:22s} ({n} bars)")
            continue
        df = pd.DataFrame(r)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        info = mt5.symbol_info(sym)
        point = info.point if info else 0.0
        out = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]].rename(
            columns={"tick_volume": "volume"}
        )
        out["spread_price"] = out["spread"].astype(float) * point
        path = os.path.join(OUT, sym_to_file(sym))
        out.to_csv(path, index=False)
        print(f"  OK   {sym:22s} {len(out):6d} bars  {str(out.time.iloc[0])[:10]} -> {str(out.time.iloc[-1])[:10]}")
        ok += 1
    mt5.shutdown()
    print(f"\nFetched {ok}/{len(SPREAD_GATED)} to {OUT}")


if __name__ == "__main__":
    main()
