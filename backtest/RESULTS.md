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

## 5. Reproducible crypto M15 arm (no MT5/TradingView terminal needed)

The MT5/TradingView feeds above need a logged-in desktop terminal, which a headless
CI/cloud box does not have. So this arm pulls **real Binance M15** from the public,
bit-for-bit re-downloadable dumps at `data.binance.vision` (`fetch_crypto.py`): 16
liquid pairs (majors + alts + a few `*-BTC` crosses), 2021-01 → 2026-05, ~190k bars
each, real volume. Crypto is also the asset class where section 4 located the only
positive expectancy, so it is the honest place to keep hunting.

### Honest cost calibration (the thing that kills most "edges")
Median M15 ATR is only ~0.5% of price, so a flat fee maps to a *large* ATR fraction:

| Execution | per-side fee | ≈ cost_atr_frac |
|---|---|---|
| Deep maker / rebate / futures | ~1 bp | ~0.02 |
| VIP / futures maker | ~3 bp | ~0.06 |
| Standard maker | ~5–6 bp | ~0.12 |
| **Retail spot taker** | **10 bp** | **~0.20 (off the chart)** |

The repo's "realistic 0.02" is really an HFT-grade-execution assumption. The crypto
ship gate therefore demands a config still be positive at **0.06 (≈3 bp)** *and* at
**0.12 (≈6 bp, 2× stress)**.

### Edge hunt — 6 structurally-distinct families, one shared exit engine
`crypto_research.py` runs momentum continuation/fade, RSI(2) reversion, Bollinger
reversion & breakout, Donchian breakout, VWAP reversion and opening-range breakout
through the *same* exit/cost/fill model and the *same* gate (breadth haircut, DSR over
all cells, cost-stress, WFE, quarter signs). **Every common-frequency strategy is a net
loser at realistic cost.** The only family net-positive at 3–6 bp is **extreme-momentum
continuation**: the rarer and larger the impulse, the bigger the gross edge per trade,
because a fixed fee is a smaller fraction of a big move.

| Config (OOS, crypto M15) | exp@0 | exp@.06 | exp@.12 (2×) | OOS t | +quarters |
|---|---|---|---|---|---|
| ≥2 ATR pullback (common) | +0.074 | −0.046 | −0.166 | −9.0 | 0/7 |
| ≥3 ATR pullback1.0 | +0.121 | +0.000 | −0.120 | +0.1 | 2/7 |
| **≥4 ATR pullback1.0** | **+0.169** | **+0.049** | −0.071 | +2.5 | **6/7** |
| **≥5 ATR pullback1.0 tp4** | **+0.165** | **+0.085** | **+0.005** | +2.8 | **6/7** |

### Is it real, or an OOS fluke? (`crypto_validate_lead.py`)
The **gross** extreme-momentum edge is positive **in-sample and out-of-sample** (t≈8–9
in both halves) and **positive gross in every calendar year 2021→2026** — a genuine,
regime-spanning signal, not a recent artifact.

| Year (≥4 ATR) | gross R | net @ .06 |
|---|---|---|
| 2021 | +0.246 | +0.126 |
| 2022 | +0.109 | −0.011 |
| 2023 | +0.012 | −0.108 |
| 2024 | +0.128 | +0.008 |
| 2025 | +0.188 | +0.068 |
| 2026 (part) | +0.133 | +0.013 |

### Verdict — a real edge, still observe-grade
It is a meaningful improvement on the ≥2 ATR pullback (which dies at realistic cost),
but it does **not** clear a formal ship gate, for two honest reasons:
1. **Cost-fragile** — net-positive in most years, but a net loser in the low-volatility
   chop of 2023, so the pooled in-sample *net* is only ~break-even.
2. **Breadth** — one correlated asset class gives only **N_eff ≈ 3** effective bets, so
   the breadth-haircut t (≈1.2) and the deflated Sharpe over the search fall short.

So: trade it **minimum size with maker/low-fee execution**, and confirm the same effect
on independent asset classes (indices/FX/metals) before scaling. EA preset:
`InpMomentumAtrMult=4.0, InpPullbackAtr=1.0` (tp 3.0, stop 1.0). Cost curve:
[`docs/crypto_xmom_costcurve.png`](../docs/crypto_xmom_costcurve.png).

## Reproduce

```bash
pip install -r requirements.txt

# Deriv arm (needs an open, logged-in MT5 terminal):
python fetch_diverse.py      # MT5 terminal must be open + logged in
python validate_diverse.py   # section 3
python experiment.py         # section 2 (uses data/derivM15 index basket)

# Crypto arm (no terminal — pulls public Binance dumps):
python fetch_crypto.py        # ~190k M15 bars x 16 pairs -> data/cryptoM15/
python crypto_research.py     # section 5 ship-gate edge hunt
python crypto_validate_lead.py# extreme-momentum deep-dive + cost-curve chart
```
