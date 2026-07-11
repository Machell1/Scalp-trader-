"""BASELINE-REPRODUCTION TEST — the byte-exact hard rule (HANDOFF / helper brief).

Any touch to the harness must keep `simulate_symbol_c` (all new params at their OFF
defaults) reproducing `scalper_backtest.simulate_symbol` EXACTLY: same trade count,
same per-trade R, maxdiff 0.00e+00 (float equality, not np.allclose).

Checked configs (each at cost 0.0 and 0.02):
  * harness defaults (chase STOP, tp 1.5, ladder)
  * SHIPPED v1.2 ladder (pullback LIMIT 0.6, tp 3, lock .25 / trail .5, hold 8)
  * v1.23 live PURE BRACKET (lock/trail OFF via 99, tp 3, hold 8)

Data: real spread-gated CSVs (data/derivM15_spreadgated) when present — that is the
run that counts for the gate. Falls back to a seeded synthetic OHLC feed so the test
is runnable on machines without broker data (source is printed either way).

Exit code 0 = byte-exact, 1 = any mismatch.
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd

from scalper_backtest import Params, simulate_symbol
from scalper_confluence import CParams, simulate_symbol_c, rs_of
from walkforward_dsr import SHIPPED, load_spreadgated

BRACKET = dict(SHIPPED, lock_trigger_atr=99.0, trail_atr=99.0)

CONFIGS = [
    ("defaults (chase STOP tp1.5 ladder)", {}),
    ("SHIPPED v1.2 ladder", dict(SHIPPED)),
    ("v1.23 pure bracket", dict(BRACKET)),
]
COSTS = [0.0, 0.02]


def synthetic_symbol(seed: int, n: int = 20000) -> pd.DataFrame:
    """Deterministic heavy-tailed OHLC walk (produces real momentum signals)."""
    rng = np.random.default_rng(seed)
    ret = rng.standard_t(3, n) * 0.0018
    close = 100.0 * np.exp(np.cumsum(ret))
    opn = np.concatenate([[100.0], close[:-1]])
    span = np.abs(rng.standard_t(3, n)) * 0.0012 * close
    high = np.maximum(opn, close) + span
    low = np.minimum(opn, close) - span
    t = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame(dict(time=t, open=opn, high=high, low=low, close=close,
                             volume=rng.integers(50, 5000, n)))


def load_data():
    data = load_spreadgated()
    if data:
        return data, "REAL data/derivM15_spreadgated"
    data = {f"SYN{k}": synthetic_symbol(20260703 + k) for k in range(4)}
    return data, "SYNTHETIC fallback (seeded) — re-run on real data before gating"


def main() -> int:
    data, src = load_data()
    print(f"BASELINE-REPRODUCTION TEST — {len(data)} symbols, source: {src}\n")
    worst = 0.0
    fail = False
    for label, cfg in CONFIGS:
        for cost in COSTS:
            n_base = n_c = 0
            maxdiff = 0.0
            for sym, df in data.items():
                p_base = Params(**cfg, cost_atr_frac=cost)
                rs_base = simulate_symbol(df, p_base, 0, len(df))
                p_c = CParams(**cfg, cost_atr_frac=cost)   # every new param at OFF default
                tr_c, _ = simulate_symbol_c(df, p_c, 0, len(df))
                rs_c = rs_of(tr_c)
                n_base += len(rs_base); n_c += len(rs_c)
                if len(rs_base) != len(rs_c):
                    print(f"  MISMATCH count {sym} [{label} cost={cost}]: "
                          f"{len(rs_base)} vs {len(rs_c)}")
                    fail = True
                    continue
                if rs_base:
                    d = float(np.max(np.abs(np.asarray(rs_base) - np.asarray(rs_c))))
                    maxdiff = max(maxdiff, d)
            worst = max(worst, maxdiff)
            ok = (not fail) and maxdiff == 0.0
            print(f"  [{'PASS' if ok else 'FAIL'}] {label:36s} cost={cost:0.2f}  "
                  f"N={n_base:6d} vs {n_c:6d}  maxdiff {maxdiff:.2e}")
            if maxdiff != 0.0:
                fail = True
    print(f"\n>>> {'BYTE-EXACT' if not fail else 'FAILED'}: maxdiff {worst:.2e}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
