"""Pull Deriv M5 bars for the MTF anchor screen's M5 cell (factor 12 -> H1 anchors).

Writes data/derivM5_spreadgated/<sym>.csv — columns
time,open,high,low,close,volume,spread,spread_price (same schema as the M15
fetchers).  Mirrors fetch_spreadgated.py; requires MetaTrader5 + a logged-in
Deriv terminal.  M5 pulls 3x the bar count for the same calendar span.

New M5 files are NOT gate-grade until they are pinned into
data/MANIFEST.sha256 alongside the existing M15 sets (Article II habit).
"""
from __future__ import annotations

import os
import time as _t

import MetaTrader5 as mt5
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "derivM5_spreadgated")
COUNT = 210000   # ~= 70k M15 bars of calendar coverage

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
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, COUNT)
        if r is None or len(r) < 6000:
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
        print(f"  OK   {sym:22s} {len(out):7d} bars  {str(out.time.iloc[0])[:10]} -> {str(out.time.iloc[-1])[:10]}")
        ok += 1
    mt5.shutdown()
    print(f"\nFetched {ok}/{len(SPREAD_GATED)} to {OUT}")


if __name__ == "__main__":
    main()
