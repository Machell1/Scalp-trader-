"""ATR definition parity check: harness Wilder ATR vs MT5 iATR (brief P4, last item).

Every ATR-scaled quantity in the system (impulse gate, pullback offset, stop, TP,
lock trigger, trail) assumes the EA's iATR and the harness's wilder_atr produce the
same number. Both are Wilder-smoothed with an SMA seed, but the seeds differ
slightly:

  * harness (scalper_backtest.wilder_atr): seeds at index `period` with
    mean(TR[1..period]) — TR[0] is EXCLUDED because prev_close[0] is synthetic.
  * MT5 standard ATR (Indicators/ATR.mq5): seeds at index `period-1` with
    mean(TR[0..period-1]) where TR[0] = high[0]-low[0].

Wilder smoothing forgets its seed geometrically (factor (1-1/p) per bar), so the
difference decays by ~e^-1 every `period` bars; at 14*10 bars it is ~5e-5 of the
seed delta. This tool MEASURES the residual on real Deriv M15 data instead of
assuming it: it replicates the exact MT5 algorithm from the same rates and reports
the relative delta distribution over the recent window the EA actually trades on.

MEASURE ONLY — do not change either definition unless the delta is material
(>0.1% would still be 40x smaller than the 2x cost-stress margin).

Run with the MT5 terminal open:
  python atr_parity.py [--bars 5000]
  python atr_parity.py --report atr_parity_report.json
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

from scalper_backtest import wilder_atr

PERIOD = 14
SYMBOLS = [
    "BTCUSD", "ETHUSD", "XRPUSD", "SOLUSD",
    "US Tech 100", "US SP 500", "Wall Street 30", "US Small Cap 2000",
    "Germany 40", "UK 100", "Japan 225", "France 40",
]


def mt5_atr(high, low, close, period):
    """Exact replica of MT5's standard ATR.mq5: TR[0]=high-low, SMA seed at
    period-1 over TR[0..period-1], then Wilder smoothing."""
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    tr[1:] = np.maximum(high[1:] - low[1:],
                        np.maximum(np.abs(high[1:] - close[:-1]),
                                   np.abs(low[1:] - close[:-1])))
    atr = np.full(n, np.nan)
    if n < period:
        return atr
    atr[period - 1] = tr[:period].mean()
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def main():
    ap = argparse.ArgumentParser(description="Wilder-vs-iATR parity measurement")
    ap.add_argument("--bars", type=int, default=5000, help="M15 bars per symbol")
    ap.add_argument("--report", default=None, help="write JSON report to this path")
    args = ap.parse_args()

    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")

    print(f"{'symbol':22s}{'bars':>7s}{'median|d|%':>12s}{'p99|d|%':>10s}{'max|d|%':>10s}  verdict")
    print("-" * 75)
    worst = 0.0
    rows = []
    for sym in SYMBOLS:
        r = mt5.copy_rates_from(sym, mt5.TIMEFRAME_M15, datetime.now(), args.bars)
        if r is None or len(r) < PERIOD * 20:
            print(f"{sym:22s}   insufficient data")
            rows.append(dict(symbol=sym, status="insufficient_data"))
            continue
        df = pd.DataFrame(r)
        h = df.high.to_numpy(float)
        l = df.low.to_numpy(float)
        c = df.close.to_numpy(float)
        a_harness = wilder_atr(h, l, c, PERIOD)
        a_mt5 = mt5_atr(h, l, c, PERIOD)
        skip = PERIOD * 10
        mask = np.isfinite(a_harness[skip:]) & np.isfinite(a_mt5[skip:]) & (a_mt5[skip:] > 0)
        d = np.abs(a_harness[skip:][mask] - a_mt5[skip:][mask]) / a_mt5[skip:][mask] * 100
        if d.size == 0:
            print(f"{sym:22s}   no overlapping values")
            rows.append(dict(symbol=sym, status="no_overlap"))
            continue
        med, p99, mx = float(np.median(d)), float(np.percentile(d, 99)), float(d.max())
        worst = max(worst, mx)
        verdict = "OK" if mx < 0.1 else "INVESTIGATE"
        print(f"{sym:22s}{d.size:7d}{med:12.5f}{p99:10.5f}{mx:10.5f}  {verdict}")
        rows.append(dict(symbol=sym, bars=int(d.size), median_pct=med, p99_pct=p99,
                         max_pct=mx, verdict=verdict))
    mt5.shutdown()

    if worst < 0.1:
        recommendation = (
            "PARITY OK: seed difference has decayed on the trading horizon; no ATR-scaled "
            "quantity is materially affected. No harness or EA change required."
        )
    else:
        recommendation = (
            "PARITY BROKEN: max delta exceeds 0.1% — diff series bar-by-bar before trusting "
            "ATR-scaled results. Do NOT silently change either definition."
        )

    print(f"\nworst relative delta across universe: {worst:.5f}%")
    print(recommendation)

    if args.report:
        payload = dict(
            generated=datetime.now().isoformat(timespec="seconds"),
            bars_per_symbol=args.bars,
            worst_max_pct=worst,
            threshold_pct=0.1,
            recommendation=recommendation,
            symbols=rows,
        )
        with open(args.report, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"\nWrote {args.report}")


if __name__ == "__main__":
    main()
