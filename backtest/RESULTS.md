# Backtest results & evidence — DerivScalperEA

All numbers are **out-of-sample** (last 30% of each series), per-trade R-multiples,
on **real Deriv M15 data**. Cost is modelled as a per-side fraction of ATR and swept.
"Realistic cost" = 0.02 ATR/side; "2× stress" = 0.04.

## 1. The original entry had no out-of-sample edge

On the 5 real Deriv US-index M15 series (2024–2026), the as-shipped momentum-continuation
entry (STOP beyond price, tp 1.5 ATR) was a ~43% win / ~1:1 coin flip that loses after
cost. Widening TP to 3.0 ATR moved it from "clearly losing" to "break-even gross, still
negative after cost". The Anchored-VWAP gate produced in-sample sparkle but **zero**
out-of-sample edge (a textbook overfit), confirmed by a negative-control / permutation
test that the research harness applies to every filter.

## 2. Confluence study — 0 of 19 filters shipped, but entry geometry is the lever

19 candidates were tested as marginal changes over the tp 3.0 baseline, each with: a
permutation-vs-random-subset test, a correlation breadth haircut, walk-forward efficiency,
2× cost-stress, a power floor, and a Deflated Sharpe over all cells.

- **Every bolt-on filter** (ADX/±DI regime, HTF trend alignment, efficiency-ratio,
  candle body, volatility-regime band, session window, tick-volume) **failed.** They
  remove some losers but never flip the population positive.
- The tick-volume **negative control** scored permutation-p ≈ 0.99–1.00 (correctly
  rejected), validating that the protocol does not rubber-stamp noise.
- The **only** candidate to flip out-of-sample expectancy positive was the
  **pullback-limit entry** — an entry-geometry change, not a filter. This confirmed the
  thesis: the noise is in *where you enter and where the stop sits*, not a missing filter.

## 3. Diverse-instrument confirmation (the breadth test)

29 real Deriv M15 instruments across FX majors/crosses, metals, energy, crypto, and 6
non-US indices. Genuine breadth: **mean pairwise correlation 0.15, N_eff = 5.7** (vs 0.84 /
1.3 on the 5 US indices).

| Config | OOS exp @0 | @0.02 | @0.04 | Instruments + | Verdict |
|---|---|---|---|---|---|
| Baseline (chase-at-extension STOP) | −0.007 R | −0.047 R | −0.087 R | 5 / 29 | loser everywhere (t −7.45) |
| **#1 Pullback LIMIT 0.6 ATR** | **+0.047 R** | **+0.007 R** | −0.033 R | **18 / 29** | **real structural gain — WATCH** |

The pullback entry is a **genuine, broad improvement** over the chase entry — not an
index artifact. But it is **not shippable** on its own: at realistic cost it is only
break-even (+0.007 R), negative at 2× cost, the breadth-haircut t is 0.48 (not
significant), the Deflated Sharpe ≈ 0.01, and only 2/4 calendar quarters are positive.

### By asset class (pullback entry, OOS exp @ 0.02)
| Class | exp | tot R |
|---|---|---|
| CRYPTO | +0.042 | +248 |
| INDEX | +0.034 | +170 |
| ENERGY | +0.015 | +42 |
| METAL | +0.007 | +22 |
| FX | −0.028 | −287 |

Restricting to **crypto + indices** lifts the pooled edge to **+0.078 R (cost 0) →
+0.038 R (0.02) → ~0 (0.04)** — the cleanest pocket, still cost-fragile. Hence the EA's
default universe (`InpSymbolWhitelist`).

## 4. What shipped, and why it is "observe-grade"

- **Adopted:** pullback-limit entry (default), 3.0 ATR take-profit, crypto+index universe.
- **Not adopted:** any of the bolt-on confluence filters (none survived).
- **Why not full size:** the edge is small and dies under realistic-to-2× cost and fails
  the deflated-Sharpe / walk-forward gate. Treat live trading as a **minimum-size
  monitored experiment** that needs low-spread execution; scale only if it survives live.

## Reproduce

```bash
pip install -r requirements.txt
python fetch_diverse.py      # MT5 terminal must be open + logged in
python validate_diverse.py   # section 3
python experiment.py         # section 2 (uses data/derivM15 index basket)
```
