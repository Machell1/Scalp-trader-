# Five candle/wick strategy candidates — screening pre-registration (2026-07-10, late)

**User ask:** "check if we can add any of these: Wick Rejection Pullback, Momentum Pin Bar,
Liquidity Sweep + Momentum Continuation, Candlestick Pullback, Wick Pressure."

**Priors disclosed before results.** (1) The wick FAMILY has one validated win (v1.29 W2
filter: contested signal bars carry information). (2) Liquidity-sweep standalone died on
XAUUSD 2026-07-09 (H1 fill artifact; M5 real-path negative) — this universe is new data.
(3) All five are entry engines; entry engines on trending markets fake edges easily, so
every cell must beat a RANDOM-ENTRY control matched on trade count and side mix.
(4) Trial ledger: 100 prior cells; +10 here → DSR deflation at 110 for any survivor.

**Common machinery.** 12-symbol spread-gated real Deriv M15, per-instrument real cost
(0.5·median spread/median ATR per side), Wilder ATR(14). All info at signal-bar close i;
entry = open of i+1 (market); exits = the validated bracket exactly (SL 1.0 ATR, TP 3.0,
time exit at close of bar i_entry+7, pessimistic SL-first intrabar, one trade per symbol
at a time, engine-identical cost of 2×cost/side per round turn).

**Canonical definitions (locked; one variant cell each → 10 cells):**
- **S1 Wick Rejection Pullback**: 6-bar impulse ending 3 bars ago ≥1.5 ATR (direction D);
  last-3-bar net pullback against D ≥ 0.3 ATR; bar i has an anti-D wick ≥ 0.5 ATR
  [variant ≥ 0.75] and closes in the D-ward 40% of its range → enter D.
- **S2 Momentum Pin Bar**: bar i tail ≥ 2× body and ≥ 0.6 ATR [variant ≥ 1.0]; nose
  direction N; 6-bar move ending at i in direction N ≥ 1.0 ATR → enter N.
- **S3 Liquidity Sweep + Momentum Continuation**: prevailing 12-bar move ≥ 1.5 ATR
  (direction D); bar i pokes ≥ 0.10 ATR [variant ≥ 0.25] beyond the 20-bar extreme
  AGAINST D and closes back inside → enter D.
- **S4 Candlestick Pullback**: live-engine impulse (6-bar ≥ 2.0 ATR, aligned candle) at
  bar j; first bar i ∈ (j, j+4] that closes D-ward after ≥1 counter-D bar → enter D
  [variant: additionally require bar i's body to engulf bar i−1's body].
- **S5 Wick Pressure**: Σ over last 8 bars of (lower−upper wick)/ATR ≥ +1.5 → long,
  ≤ −1.5 → short [variant ±2.5].

**Screen gate per cell (ALL required):** stitched-quarter OOS (last 30% of quarters)
expectancy > 0; > 95th pct of a 100-draw random-entry control (same per-symbol trade
counts and side mix, same bracket); ≥ 7/12 symbols with positive OOS expectancy.
Cells failing the screen are dead. Survivors advance in the SAME run to the full
7-gate battery used for v1.29 (placebo95, quarters ≥60%, symbols ≥8/12, DSR ≥0.95 at
110 trials, 2× cost, n ≥ 250) plus an **overlap report** vs the live engine's trade
windows (a survivor that duplicates the live strategy's trades adds nothing; low
overlap = genuine frequency/diversification gain).

**Ship rule.** Full-gate survivor(s) → propose as a SEPARATE flag-gated module
(own magic-number offset, own risk budget, user sign-off, panel-shadow option).
No survivor → documented null; nothing ships; live EA untouched either way.
