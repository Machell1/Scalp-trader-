# Scale-invariant M5/M15 entry — research specification

## Problem

The shipped H1 strategy compares closed bars at shifts 1 and 6, uses H1
Wilder ATR for its 2 ATR impulse and all order geometry, leaves a pending for
three H1 bars, and holds for at most eight H1 bars. Simply selecting M15 or M5
shrinks those horizons by 4x or 12x. That is a different, noisier strategy with
a much larger cost-to-risk burden; repository results do not support calling it
an H1-equivalent entry.

## v1.32 candidate

`InpUseScaleInvariantLowerTfV132` is a default-off research flag. On a working
timeframe below `InpReferenceTimeframeV132` (intended reference: H1), it:

1. preserves the original shift-1-to-shift-6 close span. The effective signal
   shift is `1 + (6 - 1) * reference_seconds / work_seconds`: 21 on M15 and 61
   on M5;
2. divides the rolling move by closed-bar H1 Wilder ATR(14), and also uses that
   ATR for spread admission, pullback offset, SL, TP, sizing, and partial-close
   R;
3. retains the working-timeframe directional candle and W2 adverse wick as the
   finer entry trigger. The wick is divided by local ATR, because dividing an
   M5/M15 wick by H1 ATR would mechanically erase the trigger;
4. scales pending lifetime and maximum hold to equal wall-clock horizons:
   M15 = 12/32 bars and M5 = 36/96 bars.

With the flag off, every effective value is the original input. H1 is rejected
as an adaptive configuration and remains on the exact v1.31 path.

## Why this is the narrow candidate

This is not another EMA, ADX, session, VWAP, or breakout filter. Those families
already failed the repository's out-of-sample screens. It changes the sampling
clock while preserving the validated H1 economic horizon and risk ruler. The
lower timeframe supplies entry timing, not a shorter strategy.

## Promotion gate

The implementation is **not evidence of profitability** and must remain off by
default. Promotion requires canonical native M5 and M15 bid/ask or spread data,
causal reference-ATR alignment, live-parity coupled enumeration, trade-through
limit fills, real per-symbol costs, chronological OOS and 2x-cost stress.
Results must be reported separately for M5, M15, each symbol, and the coupled
portfolio. New assets must pass the existing universe admission and risk-sleeve
process; this mode does not turn an unprofitable asset into an admitted one.

Synthetic invariants are in `backtest/test_adaptive_entry.py`. The research
mirror is `backtest/adaptive_entry.py`.
