"""Pull a diverse basket of real M15 crypto OHLCV to disk from Binance's PUBLIC
data dumps (https://data.binance.vision) — no API key, no terminal, fully
reproducible.

Why this feed: the MT5 / TradingView feeds the rest of this repo uses need a
running, logged-in desktop terminal, which is unavailable in a headless CI/cloud
box. Binance publishes monthly kline ZIPs that anyone can re-download bit-for-bit,
which makes the research below independently checkable. Crypto is also exactly the
asset pocket where this repo's own diverse-instrument study located the only
positive out-of-sample expectancy (see backtest/RESULTS.md), so it is the honest
place to keep hunting for a real edge.

Writes data/cryptoM15/<SYM>.csv with columns: time,open,high,low,close,volume.
No market data passes through the agent's context.
"""
from __future__ import annotations

import io
import os
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "cryptoM15")
BASE = "https://data.binance.vision/data/spot/monthly/klines"
INTERVAL = "15m"
START = (2021, 1)          # first month to attempt
RETRIES = 3

# A spread of liquid USDT pairs (majors + higher-beta alts) plus a few *-BTC
# crosses, which carry meaningfully different dynamics from the USD legs and so
# add a little genuine breadth to an otherwise highly-correlated asset class.
BASKET = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "LTCUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT", "BCHUSDT",
    "ETHBTC", "BNBBTC", "SOLBTC", "LTCBTC",
]

COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "qv", "trades", "tbb", "tbq", "ignore"]


def _months(start, end):
    y, m = start
    ey, em = end
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def _fetch_month(sym, y, m):
    url = f"{BASE}/{sym}/{INTERVAL}/{sym}-{INTERVAL}-{y:04d}-{m:02d}.zip"
    for attempt in range(RETRIES):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=30) as r:
                raw = r.read()
            break
        except HTTPError as e:
            if e.code == 404:
                return None          # month not published — normal at the edges
            if attempt == RETRIES - 1:
                return None
        except (URLError, TimeoutError):
            if attempt == RETRIES - 1:
                return None
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = z.namelist()[0]
        data = z.read(name)
    # Newer dumps ship a header row; older ones don't. Detect by first byte.
    first = data[:1]
    header = 0 if (first.isdigit()) else 1
    df = pd.read_csv(io.BytesIO(data), header=None if header == 0 else 0,
                     names=COLS, usecols=range(len(COLS)))
    return df


def fetch_symbol(sym, end):
    parts = []
    for (y, m) in _months(START, end):
        df = _fetch_month(sym, y, m)
        if df is not None and len(df):
            parts.append(df)
    if not parts:
        return sym, 0, None
    full = pd.concat(parts, ignore_index=True)
    # Binance switched kline-dump timestamps from milliseconds to MICROSECONDS
    # around 2025-01, so a single series can mix both. Normalise per-row to ms
    # (anything past ~1e14 is microseconds).
    ot = full["open_time"].astype("int64")
    ot = ot.where(ot < 10**14, ot // 1000)
    full["time"] = pd.to_datetime(ot, unit="ms", utc=True).dt.tz_localize(None)
    full = full.drop_duplicates(subset="open_time").sort_values("time")
    out = full[["time", "open", "high", "low", "close", "volume"]].copy()
    out = out[out["volume"] > 0]
    os.makedirs(OUT, exist_ok=True)
    fn = os.path.join(OUT, f"{sym}.csv")
    out.to_csv(fn, index=False)
    return sym, len(out), (str(out["time"].iloc[0])[:10], str(out["time"].iloc[-1])[:10])


def main():
    now = datetime.now(tz=None)
    # monthly dumps publish with a lag; attempt through last full month
    end = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    print(f"Fetching {len(BASKET)} crypto M15 series {START} -> {end} from data.binance.vision\n")
    rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_symbol, s, end): s for s in BASKET}
        for f in as_completed(futs):
            sym, n, rng = f.result()
            if n:
                rows.append((sym, n))
                print(f"  OK   {sym:10s} {n:7d} bars  {rng[0]} -> {rng[1]}")
            else:
                print(f"  SKIP {sym:10s} (no data)")
    print(f"\nWrote {len(rows)} series to {OUT}")
    if not rows:
        sys.exit("No data fetched — check network access to data.binance.vision")


if __name__ == "__main__":
    main()
