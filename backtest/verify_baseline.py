"""Byte-exact baseline reproduction gate for scalper_confluence changes.

simulate_symbol_c with every extension OFF must match scalper_backtest.simulate_symbol
trade-for-trade on the same bars. Run after any edit to scalper_confluence.py or
scalper_backtest.py:

  python verify_baseline.py

Exit 0 only when max |r_c - r_base| == 0.00e+00 across all trades.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from scalper_backtest import Params, simulate_symbol
from scalper_confluence import CParams, simulate_symbol_c


def synthetic_ohlc(n: int = 3000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp("2024-01-01", tz="UTC")
    times = pd.date_range(t0, periods=n, freq="15min")
    logp = np.cumsum(rng.normal(0, 0.0008, n))
    close = 100.0 * np.exp(logp)
    spread = rng.integers(5, 30, n)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    wobble = rng.uniform(0.0002, 0.0015, n)
    high = np.maximum(open_, close) * (1 + wobble)
    low = np.minimum(open_, close) * (1 - wobble)
    return pd.DataFrame({
        "time": times,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "spread": spread,
    })


def compare(df: pd.DataFrame, label: str) -> float:
    n = len(df)
    p_base = Params(cost_atr_frac=0.02, entry_style="limit", entry_offset_atr=0.6,
                    pending_expiry_bars=3, tp_atr=3.0, lock_trigger_atr=0.25,
                    trail_atr=0.5, max_hold_bars=8)
    p_c = CParams(cost_atr_frac=0.02, entry_style="limit", entry_offset_atr=0.6,
                  pending_expiry_bars=3, tp_atr=3.0, lock_trigger_atr=0.25,
                  trail_atr=0.5, max_hold_bars=8, block_overlap=True)
    rb = simulate_symbol(df, p_base, 0, n)
    tc, _ = simulate_symbol_c(df, p_c, 0, n)
    rc = [t["r"] for t in tc]
    if len(rb) != len(rc):
        print(f"{label}: trade count mismatch base={len(rb)} confluence={len(rc)}")
        return float("inf")
    if not rb:
        return 0.0
    d = np.max(np.abs(np.asarray(rb, float) - np.asarray(rc, float)))
    print(f"{label}: N={len(rb)} maxdiff={d:.2e}")
    return float(d)


def main() -> int:
    configs = [
        ("synthetic", synthetic_ohlc()),
        ("synthetic+spread_price", synthetic_ohlc(seed=7).assign(
            spread_price=lambda d: d["spread"] * 0.01)),
    ]
    worst = 0.0
    for label, df in configs:
        worst = max(worst, compare(df, label))
    if worst == 0.0:
        print("PASS: baseline reproduction byte-exact (maxdiff 0.00e+00)")
        return 0
    print(f"FAIL: maxdiff {worst:.2e} — fix scalper_confluence before shipping")
    return 1


if __name__ == "__main__":
    sys.exit(main())
