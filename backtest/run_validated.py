"""Backtest the DEPLOYED DerivScalperEA config (v1.24/v1.25) — pullback-limit
entry, pure-bracket exits — on the real spread-gated universe, IS/OOS + per-symbol.

Matches the live inputs: momentum 6 bars / 2.0 ATR, pullback limit 0.6 ATR,
stop 1.0 ATR, TP 3.0 ATR, max hold 8 bars, pending expiry 3, ladder DISABLED
(lock_trigger set out of reach => pure bracket = SL/TP/time, exactly like live).
"""
import sys
from scalper_backtest import Params, load_dataset, run, fmt

tf = sys.argv[1] if len(sys.argv) > 1 else "derivM15_spreadgated"
cost = float(sys.argv[2]) if len(sys.argv) > 2 else 0.03

p = Params(
    momentum_bars=6, momentum_atr=2.0, atr_period=14,
    direction="cont", entry_style="limit", entry_offset_atr=0.6,
    pending_expiry_bars=3, stop_atr=1.0, tp_atr=3.0,
    lock_trigger_atr=999.0, trail_atr=0.0,   # ladder off => PURE BRACKET (live)
    max_hold_bars=8, cost_atr_frac=cost,
)
data = load_dataset(tf)
print(f"tf={tf}  cost={cost}/side  symbols={len(data)}")
for split in ("all", "is", "oos"):
    pooled, per = run(data, p, split)
    print(f"  {split.upper():4s}: {fmt(pooled)}")
    if split == "oos":
        pos = sum(1 for s in per.values() if s.n >= 10 and s.expectancy > 0)
        tot = sum(1 for s in per.values() if s.n >= 10)
        print(f"  OOS per-symbol positive: {pos}/{tot} (>=10 trades)")
        for sym, s in sorted(per.items(), key=lambda kv: -kv[1].expectancy):
            if s.n >= 10:
                print(f"      {sym:20s} {fmt(s)}")
