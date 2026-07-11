# 100-point weighted confluence engine — pre-registration (2026-07-11)

**User ask:** test the pasted "institutional confluence" stack (weighted score, trade at
≥85/100) "not just for Gold." Mechanized FAITHFULLY from the paste's final table:
trend 20 · momentum impulse 20 · healthy pullback 15 · liquidity sweep 15 ·
wick rejection 10 · strong close 10 · ATR expanding 5 · active session 5.

**Priors disclosed before results.** (1) Checklist/weighted-score aggregation is 0-for-3
in this project (AD_XAU 85-cell checklist null; Golden-Asia zone score refuted; LLM-judge
selection null). (2) Components individually: EMA/HTF trend filters, session filters,
tick-volume gates all failed OOS previously; sweep null twice; wick-rejection-as-entry
died today (S1). (3) DIRECT CONTRADICTION: the stack's most-weighted momentum definition
(big body, small opposite wick, close at extreme) is the clean-climax profile measured
WORST across 58k trades (W2 finding). A composite may still work; that is what's tested.

**Mechanization (all info at closed bar i; direction D from the EMA stack):**
- D: close>EMA20>EMA50 with EMA20 slope>0 (mirror for short). No D → no score.
- Trend 20: D exists AND H4-resampled EMA20>EMA50 agrees (H1 frame; for M15 frame the
  HTF is H1). Else 0.
- Momentum 20: an impulse bar in the last 6 bars: range ≥1.5×ATR14, body ≥60% of range,
  opposite wick ≤20%, close in D-ward 25%, close breaks the prior 10-bar extreme.
- Pullback 15: 2–5 counter-D bars since the impulse, median TR < impulse TR, no counter
  body >0.8× impulse body, net retrace <0.8× impulse range.
- Sweep 15: bar i wicks beyond the prior 5-bar D-adverse extreme and closes back inside.
- Wick rejection 10: bar i D-favorable wick ≥60% of range, body ≤40%.
- Strong close 10: bar i closes in the D-ward 20% of its range.
- ATR expanding 5: ATR14[i] > mean(ATR14[i−10..i−1]).
- Session 5: bar hour 07–17 UTC (London+NY).
Entry: score ≥ threshold → market at open of i+1, direction D; validated bracket
(SL 1.0 ATR / TP 3.0 / hold 8, engine-identical replay); one position per symbol.

**Arms (7 cells; ledger → ~125 for survivors' DSR):**
- A. Standalone H1 (per the paste): thresholds 85 (primary), 80, 70. Data = 12-symbol
  spread-gated + XAUUSD, M15 resampled to H1; real per-instrument costs (gold 0.03 flat).
- B. Standalone M15: threshold 85.
- C. As a FILTER on the live engine's M15 signals (momentum 20 granted; other 7
  components scored on the signal bar): engine trades with score ≥ 85 and ≥ 70,
  compared PAIRED against the live W2 baseline on the same tape.
**Gates:** screen = stitched-quarter OOS > 0, beats matched random-entry control
(100 draws) [arm C: beats the W2 baseline instead], ≥7/12 symbols (gold reported
separately, never pooled-hidden). Survivors → full battery (placebo, DSR@125, 2× cost,
quarters, n≥250). Ship only via the standard rule (flag-gated, sign-off).
