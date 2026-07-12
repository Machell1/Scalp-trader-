# Four entry-family screen (owner's research paste) — pre-registration (2026-07-13)

**Source:** owner-provided research report (external AI deep-research; literature
anchors Jegadeesh-Titman, Moskowitz-Ooi-Pedersen, Menkhoff FX momentum, Bailey
PBO — real citations, but ALL at daily+ horizons; M15 transfer is the open
question under test). Four rule families, mechanized as below. SCREEN under
RETEST_SPEC governance (e7df76df): live-parity enumeration, real per-symbol
cost, trio primary + 10-symbol holdout generalization column, all cells
reported, promotions need full gate + forward validation. Ledger: 4 screen
cells noted.

**Shared mechanics:** M15 bars; symmetric long/short (mirrored); signal at bar-t
close; stop-entries rest 4 bars (live window) then re-arm at t+4; market entries
fill at o[t+1]; one position per symbol; cooldown = exit bar; safety max-hold 96
bars; costs 2 sides in ATR fraction; R = price risk (entry−stop). Indicators:
Wilder RSI(2)/RSI(14)/ADX(14)/ATR(14), EMA20/50, SMA50/200, Stoch(14,3,3),
MACD(12,26,9). Swing machinery (families 2–3): lookback 96 bars; swing_high =
max high (long side), swing_low = min low before it; leg must exceed 2×ATR;
pullback_low = min low since swing_high; retrace = (SH − low_t)/(SH − SL).

**Stated simplifications (pre-registered, honesty over fidelity):** price-action
trigger = close > prior bar high (engulfing/hammer variants not screened);
structure trails replaced by 3×ATR highest-close trails; F2 "higher-low" trail
likewise; F4's contradictory pseudocode (RSI in 40–50 AND >50 at t) mechanized
as min(RSI14[t−5..t−1]) ∈ [40,50] AND RSI14[t] > 50.

- **F1 trend-oversold pullback:** c>SMA200, SMA50 rising (vs t−5), low touches
  EMA20 or EMA50, (RSI2<15 or RSI14∈[40,50]), c>h[t−1] → buy stop at h[t];
  stop = min(l[t]−0.5A, entry−2.0A); partial 50% @ +1.5R then BE; 3A trail;
  exit-all if close crosses below EMA20 while profitable.
- **F2 fib-stoch structure pullback:** c>EMA50>SMA200, retrace ∈ [0.382,0.618],
  StochK crosses up through 20 with K>D, c>h[t−1] → buy stop h[t]; stop =
  min(SL_swing−1.5A, l[t]−0.5A); partials 33% @1R and @2R; 3A trail.
- **F3 ADX-MACD shallow momentum pullback:** c>EMA50>SMA200, ADX>25,
  MACD>signal, MACD>0, retrace ≤ 0.382, c≥EMA50, c>h[t−1] → market at next
  open; stop = pullback_low−2.0A; partial 33% @2R; 3A trail; exit-all if
  MACD<signal AND c<EMA20.
- **F4 RSI bull-range re-entry:** c>EMA20>EMA50>SMA200, recent RSI14 dip into
  [40,50], RSI14>50 now, ADX>20, c>h[t−1] → market next open; stop =
  min(l[t]−0.5A, entry−1.75A); exit on 2 consecutive closes < EMA20; 3A trail.

**Prior stated:** the report's own horizon caveat cuts against transfer; the
program's corrected-engine history says M15 index edges are rare and fill/cost
fragile. Expectation: most or all families ≈ 0 or negative at real cost; any
positive OOS + holdout-consistent family is a genuine find. Results below.

---
## RESULTS (appended post-run 2026-07-13; protocol hashed pre-run: de3b503a...)

| family | trio n / exp / OOS | holdout-10 n / exp / OOS | MC trio | verdict |
|---|---|---|---|---|
| F1 trend-oversold pullback | 1377 / −0.0424 / +0.0617 | 5385 / −0.0288 / −0.0296 | 0.6%/69% | NULL (frames disagree) |
| F2 fib-stoch structure | 704 / +0.0080 / +0.0343 | 2519 / −0.0198 / +0.0012 | 0.2%/0% | NULL (≈0, ~1 trade/day — challenge-irrelevant) |
| F3 ADX-MACD shallow momentum | 2015 / +0.0218 / −0.0066 | 6750 / −0.0259 / −0.0123 | 42.6%/9% | NULL (IS-only) |
| F4 RSI bull-range re-entry | 1801 / +0.0520 / +0.0140 | 6361 / −0.0403 / +0.0033 | 59.2%/23.5% | NULL (no generalization) |

**All four fail the two-frame consistency standard** (the bar the scale-out
geometry cleared: positive AND consistent on trio-OOS + holdout + second
venue). The daily-horizon literature did not transfer to M15 index CFDs —
exactly the report's own horizon caveat, now measured. Consistent with every
prior standalone-entry screen: at this venue/timeframe, entry alpha is scarce;
the realizable improvement found so far lives in EXIT geometry on the existing
momentum signal. Ledger: +4 screen cells noted (→ ~213).
