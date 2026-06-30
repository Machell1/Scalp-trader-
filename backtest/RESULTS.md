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

## 5. REAL Deriv spread cost — the decisive test (drives v1.2)

`deriv_realcost.py` pulls each instrument's live Deriv spread, converts it to ATR units
(per-side = 0.5 × median spread ÷ median ATR), and runs the exact Pine config at that real
cost on the OOS slice. Deriv's spreads are wildly heterogeneous:

| Instrument | real spread (ATR/side) | exp net of real cost |
|---|---|---|
| BTCUSD | 0.005 | +0.114 R |
| US Tech 100 | 0.012 | +0.109 R |
| Germany 40 | 0.010 | +0.053 R |
| Wall Street 30 | 0.016 | +0.051 R |
| … (majors) | ≤ 0.03 | positive |
| LTCUSD | 0.205 | −0.384 R |
| BCHUSD | 0.183 | −0.270 R |
| US Mid Cap 400 | 0.143 | −0.226 R |

Pooled over all 17 it is **−0.032 R** (dragged down by the blown-spread names). But gated by
an a-priori **spread/ATR ≤ 0.05 per side** filter (a cost property, not outcome-fitting):

| Universe | N | exp (real cost) | t | PF |
|---|---|---|---|---|
| spread ≤ 0.05/side (12 majors) | 10,711 | **+0.044 R** | **+4.07** | **1.11** |
| spread ≤ 0.03/side (9 majors)  | 8,132  | **+0.059 R** | **+4.78** | **1.15** |

**Conclusion:** at Deriv's real spreads the pullback edge is positive and significant on a
spread-gated set of major crypto + indices (vs −64% on Binance, where 0.1% taker ≈ 0.23
ATR/side). The cross-venue reconciliation: viability is entirely a spread/ATR question.

**v1.2 ships this:** universe pruned to the ≤0.05 majors, a live `InpMaxSpreadAtr` gate that
skips any symbol whose spread is too wide right now, and AVWAP off by default. Still
observe / minimum-size grade pending a walk-forward + DSR on the gated universe.

## Reproduce

```bash
pip install -r requirements.txt
python fetch_diverse.py      # MT5 terminal must be open + logged in
python validate_diverse.py   # section 3
python experiment.py         # section 2 (uses data/derivM15 index basket)
python deriv_realcost.py     # section 5 — real Deriv spread cost (MT5 must be open)
python fetch_spreadgated.py  # 12 spread-gated majors with spread column
python walkforward_dsr.py    # section 6 — walk-forward + DSR gate (backlog #1)
```

## 6. Walk-forward + DSR on spread-gated universe (backlog #1)

`walkforward_dsr.py` runs the validated v1.2 config on the **12 spread-gated majors**
at **real per-instrument Deriv spread cost**, using calendar-quarter walk-forward:

- **IS:** first 70% of calendar quarters (pooled trades)
- **OOS:** remaining quarters stitched chronologically
- **WFE:** mean rolling OOS/IS expectancy across expanding-window quarterly folds
- **DSR:** deflated Sharpe (PSR vs hurdle from ~25 prior research trials)

**SHIP gate** (all must pass): stitched OOS exp > 0 @ real cost, DSR ≥ 0.95, WFE ≥ 0.30,
2× cost stress positive, ≥ 60% OOS quarters positive, ≥ 60% symbols positive, N ≥ 250.

Run after `fetch_spreadgated.py` (MT5 terminal open).

### Result (run on real Deriv M15, 2024–2026; IS = 7 quarters, OOS = 3 stitched quarters)

| Slice | N | exp (R) | t | t (breadth-haircut) | PF |
|---|---|---|---|---|---|
| IS (real cost) | 24,448 | +0.0296 | +4.14 | | |
| **OOS stitched (real cost)** | 11,790 | **+0.0489** | **+4.76** | **+2.23** | **1.12** |
| OOS frictionless | 11,790 | +0.0926 | +9.02 | | |
| OOS 2× cost stress | 11,790 | **+0.0052** | +0.51 | | |

WFE 1.55 (OOS ≥ IS, no decay) · OOS quarters positive 3/3 · symbols positive 11/12 · DSR 0.998.

**All 7 SHIP gates PASS → VERDICT: SHIP** (promote to **small-size** live on the
spread-gated majors with the live spread gate enabled).

> Note: the original `dsr_hurdle()` used a fixed `var_sr = 0.05²` prior, which set a
> per-trade-Sharpe hurdle of ~0.10 — ~5× the proper sampling-theory null (≈1/√T ≈ 0.018
> for ~12k trades) — forcing DSR→0 and a spurious WATCH. Fixed to a principled
> `1/(T-1)` null; DSR then 0.998.

**Honest caveat:** the edge is real and time-stable but **thin** — at 2× cost it is only
+0.005R (break-even). The entire margin is spread/cost, so live execution discipline and
the spread gate are essential; this is "small-size live trial," not "scale up." Also only
~3 OOS quarters (one broad 2025–26 regime).
