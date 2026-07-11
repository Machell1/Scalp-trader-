"""Download the free Binance futures microstructure archive for the crypto probe.

Pre-registered: docs/CRYPTO_MICRO_SPEC_2026-07-11.md
  (SHA256 8af19185498fa14cc7ced6adedcb902d82a5a37c7d1980d6528de03f3aeea734)
Datasets: 15m klines (monthly), metrics (daily), bookDepth (daily) for BTCUSDT
USDT-M perp, 2024-01-01 .. 2026-07-02 (the Deriv tape window). ~425MB total.
Resumable: skips files already present. Failures are listed, never papered over.
"""
import datetime
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data_crypto")
BASE = "https://data.binance.vision/data/futures/um"
START = datetime.date(2024, 1, 1)
END = datetime.date(2026, 7, 2)


def get(url, dest):
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        return "skip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "research-probe"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest + ".part", "wb") as f:
            f.write(r.read())
        os.replace(dest + ".part", dest)
        return "ok"
    except Exception as e:
        if os.path.isfile(dest + ".part"):
            os.remove(dest + ".part")
        return f"FAIL {e}"


def main():
    os.makedirs(os.path.join(OUT, "klines"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "metrics"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "bookDepth"), exist_ok=True)
    fails = []

    # monthly 15m klines
    m = datetime.date(START.year, START.month, 1)
    while m <= END:
        tag = f"{m.year}-{m.month:02d}"
        r = get(f"{BASE}/monthly/klines/BTCUSDT/15m/BTCUSDT-15m-{tag}.zip",
                os.path.join(OUT, "klines", f"{tag}.zip"))
        if r.startswith("FAIL"):
            fails.append(("klines", tag, r))
        m = datetime.date(m.year + (m.month == 12), (m.month % 12) + 1, 1)
    print(f"klines monthly done ({len(os.listdir(os.path.join(OUT,'klines')))} files)", flush=True)

    # daily metrics + bookDepth
    d = START
    n = 0
    while d <= END:
        tag = d.isoformat()
        for ds in ("metrics", "bookDepth"):
            r = get(f"{BASE}/daily/{ds}/BTCUSDT/BTCUSDT-{ds}-{tag}.zip",
                    os.path.join(OUT, ds, f"{tag}.zip"))
            if r.startswith("FAIL"):
                fails.append((ds, tag, r))
        n += 1
        if n % 50 == 0:
            print(f"  {n} days processed (through {tag})", flush=True)
            time.sleep(1)
        d += datetime.timedelta(days=1)

    print(f"\nDONE. metrics: {len(os.listdir(os.path.join(OUT,'metrics')))} files | "
          f"bookDepth: {len(os.listdir(os.path.join(OUT,'bookDepth')))} files", flush=True)
    if fails:
        print(f"FAILURES ({len(fails)}) — reported verbatim, first 20:")
        for x in fails[:20]:
            print("  ", x)
    else:
        print("no failures")


if __name__ == "__main__":
    main()
