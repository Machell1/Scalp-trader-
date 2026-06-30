"""Fetch proxy OHLCV data via Yahoo Finance for Linux / CI backtesting.

Writes data/yahooM15/<sym>.csv with columns time,open,high,low,close,volume.
Yahoo limits 15m history (~60 days); for longer OOS we also write 1h bars to
data/yahooH1/ and edge_loop.py can use either.

Not a substitute for Deriv MT5 data — use fetch_diverse.py when MT5 is available.
"""
from __future__ import annotations

import os
import time as _t

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))

# Yahoo ticker → canonical name (matches validate_diverse CLASS keys where possible)
BASKET = {
  # crypto
  "BTCUSD": "BTC-USD",
  "ETHUSD": "ETH-USD",
  "LTCUSD": "LTC-USD",
  "XRPUSD": "XRP-USD",
  "SOLUSD": "SOL-USD",
  "BCHUSD": "BCH-USD",
  # US indices
  "NDX": "^NDX",
  "SPX": "^GSPC",
  "DJI": "^DJI",
  # global indices
  "Germany_40": "^GDAXI",
  "UK_100": "^FTSE",
  "Japan_225": "^N225",
  "France_40": "^FCHI",
  "Australia_200": "^AXJO",
  "Hong_Kong_50": "^HSI",
  # FX (for class comparison — expected to lose)
  "EURUSD": "EURUSD=X",
  "GBPUSD": "GBPUSD=X",
  "USDJPY": "USDJPY=X",
  "XAUUSD": "GC=F",
}


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index()
    # yfinance may use DatetimeIndex name 'Datetime' or 'Date'
    tcol = "Datetime" if "Datetime" in df.columns else "Date"
    out = pd.DataFrame({
        "time": pd.to_datetime(df[tcol], utc=True).dt.tz_convert(None),
        "open": df["Open"].astype(float),
        "high": df["High"].astype(float),
        "low": df["Low"].astype(float),
        "close": df["Close"].astype(float),
        "volume": df["Volume"].fillna(0).astype(float),
    })
    return out.dropna(subset=["open", "high", "low", "close"])


def fetch_one(ticker: str, interval: str, period: str) -> pd.DataFrame | None:
    try:
        raw = yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=False)
    except Exception as e:
        print(f"    ERR  {ticker}: {e}")
        return None
    if raw is None or len(raw) < 500:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    return _normalize(raw)


def main():
    for tf, interval, period, min_bars in [
        ("yahooM15", "15m", "60d", 1500),
        ("yahooH1", "1h", "730d", 3000),
    ]:
        out_dir = os.path.join(HERE, "data", tf)
        os.makedirs(out_dir, exist_ok=True)
        print(f"\n=== {tf} ({interval}, {period}) ===")
        ok = 0
        for sym, ticker in BASKET.items():
            _t.sleep(0.15)
            df = fetch_one(ticker, interval, period)
            if df is None or len(df) < min_bars:
                n = 0 if df is None else len(df)
                print(f"  SKIP {sym:14s} ({ticker:12s}) {n} bars")
                continue
            path = os.path.join(out_dir, f"{sym}.csv")
            df.to_csv(path, index=False)
            print(f"  OK   {sym:14s} {len(df):6d} bars  {str(df.time.iloc[0])[:10]} -> {str(df.time.iloc[-1])[:10]}")
            ok += 1
        print(f"  -> {ok}/{len(BASKET)} written to {out_dir}")


if __name__ == "__main__":
    main()
