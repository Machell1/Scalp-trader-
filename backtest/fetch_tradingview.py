"""Pull a diverse, real, multi-asset basket of OHLCV bars directly from TradingView
(no MT5 terminal required) using the unofficial `tvdatafeed` websocket client.

This is the data source for the swing-strategy edge search (see
EDGE_SEARCH_PLAN.md and swing_backtest.py / swing_experiment.py). It deliberately
mirrors the diversity philosophy of fetch_diverse.py (FX majors/crosses, metals,
energy, crypto, global indices) but sources data live from TradingView instead of
a Deriv MT5 terminal, and targets the DAILY and 4-HOUR timeframes (vs M15) because:

  1. TradingView's no-login historical endpoint caps any single request at 5000
     bars regardless of timeframe, so lower-frequency bars buy far more real
     calendar history (Daily: ~19y back to 2006-2007 for FX/metals/energy/
     indices; H4: ~3y). M15 would only reach back ~2 months.
  2. Swing/trend systems are far less cost-fragile than M15 scalps, which is the
     dimension that killed the existing EA's edge under realistic spread.

Writes data/tv_<tf>/<sym>.csv with columns time,open,high,low,close,volume.
"""
from __future__ import annotations

import os
import time

import pandas as pd
from tvDatafeed import Interval, TvDatafeed

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# label -> (exchange, symbol) -- verified live against TradingView's nologin feed.
BASKET = {
    # FX majors
    "EURUSD": ("OANDA", "EURUSD"),
    "GBPUSD": ("OANDA", "GBPUSD"),
    "USDJPY": ("OANDA", "USDJPY"),
    "AUDUSD": ("OANDA", "AUDUSD"),
    "USDCAD": ("OANDA", "USDCAD"),
    "USDCHF": ("OANDA", "USDCHF"),
    "NZDUSD": ("OANDA", "NZDUSD"),
    # FX crosses
    "EURJPY": ("OANDA", "EURJPY"),
    "GBPJPY": ("OANDA", "GBPJPY"),
    "EURGBP": ("OANDA", "EURGBP"),
    "AUDJPY": ("OANDA", "AUDJPY"),
    # metals
    "XAUUSD": ("OANDA", "XAUUSD"),
    "XAGUSD": ("OANDA", "XAGUSD"),
    "XPTUSD": ("OANDA", "XPTUSD"),
    "COPPER": ("COMEX", "HG1!"),
    # energy
    "WTI": ("TVC", "USOIL"),
    "BRENT": ("TVC", "UKOIL"),
    "NATGAS": ("NYMEX", "NG1!"),
    # crypto (genuine volume)
    "BTCUSD": ("BINANCE", "BTCUSDT"),
    "ETHUSD": ("BINANCE", "ETHUSDT"),
    "LTCUSD": ("BINANCE", "LTCUSDT"),
    "XRPUSD": ("BINANCE", "XRPUSDT"),
    "SOLUSD": ("BINANCE", "SOLUSDT"),
    "BCHUSD": ("BINANCE", "BCHUSDT"),
    # global (non-US) indices
    "GER40": ("OANDA", "DE30EUR"),
    "UK100": ("OANDA", "UK100GBP"),
    "JPN225": ("OANDA", "JP225USD"),
    "EU50": ("OANDA", "EU50EUR"),
    "AUS200": ("OANDA", "AU200AUD"),
    "HK50": ("OANDA", "HK33HKD"),
    # US indices
    "SPX500": ("OANDA", "SPX500USD"),
    "US30": ("OANDA", "US30USD"),
    "NAS100": ("OANDA", "NAS100USD"),
}

TIMEFRAMES = {
    "D1": Interval.in_daily,
    "H4": Interval.in_4_hour,
}

N_BARS = 5000  # TradingView nologin cap per request


def fetch_one(tv, label, exchange, symbol, interval, out_dir, retries=3):
    for attempt in range(retries):
        try:
            df = tv.get_hist(symbol=symbol, exchange=exchange, interval=interval, n_bars=N_BARS)
            if df is None or len(df) < 200:
                return None
            df = df.reset_index().rename(columns={"datetime": "time"})
            out = df[["time", "open", "high", "low", "close", "volume"]].copy()
            out.to_csv(os.path.join(out_dir, f"{label}.csv"), index=False)
            return len(out), str(out.time.iloc[0])[:10], str(out.time.iloc[-1])[:10]
        except Exception as e:  # noqa: BLE001 - flaky websocket, just retry
            if attempt == retries - 1:
                print(f"  SKIP {label:10s} ({exchange}:{symbol}) -> {e}")
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def main():
    tv = TvDatafeed()  # nologin: public/limited data, no TradingView account required
    for tf, interval in TIMEFRAMES.items():
        out_dir = os.path.join(DATA, f"tv_{tf}")
        os.makedirs(out_dir, exist_ok=True)
        print(f"\n=== {tf} ===")
        ok = 0
        for label, (exchange, symbol) in BASKET.items():
            res = fetch_one(tv, label, exchange, symbol, interval, out_dir)
            if res:
                n, t0, t1 = res
                print(f"  OK   {label:10s} {n:5d} bars  {t0} -> {t1}")
                ok += 1
            time.sleep(0.25)  # be polite to the public endpoint
        print(f"{tf}: fetched {ok}/{len(BASKET)} instruments to {out_dir}")


if __name__ == "__main__":
    main()
