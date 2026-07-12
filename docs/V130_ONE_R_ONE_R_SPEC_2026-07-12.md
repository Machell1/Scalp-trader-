# v1.30 1R:1R exit screen — pre-registration

**Date:** 2026-07-12 UTC  
**Branch:** `codex/v130-1r1r-screen`

## Hypothesis

Without changing signals, W2 filtering, limit entry, pending occupancy, stop
distance, holding period, cooldown, symbol set, or portfolio constraints, a
full-position take-profit at +1.0R may raise the net positive-trade rate above
80% while preserving the validated v1.30 edge.

FTMO does not require a particular trade win rate. For the 2-Step evaluation,
the relevant objectives are a 10% Challenge target, a 5% Verification target,
5% maximum daily loss, 10% maximum loss, and four minimum trading days. Source:
https://ftmo.com/en/trading-objectives/ (accessed 2026-07-12). Therefore this
screen treats win rate as a diagnostic and net expectancy as the edge gate.

## Frozen cells

- `CONTROL_V130`: W2, continuation, 0.6 ATR limit, SL 1.0 ATR, 50% scale-out
  at +1R, final TP +2.0 ATR, hold 8 bars.
- `CANDIDATE_FULL_TP1`: identical enumeration and costs, but no scale-out and
  the entire position exits at +1.0 ATR (= +1R).

There is one new hypothesis cell. Trial ledger charge: `209 -> 210`.

## Data and engine

Use only the frozen canonical `backtest/data/derivM15_spreadgated` trio:
`Wall_Street_30`, `US_Tech_100`, and `Japan_225`. Verify the 46-file manifest
before execution. Use `parity_engine.prep_symbol`,
`walkforward_dsr.real_cost_per_side`, and `retest_engine.run_cell` unmodified.
The final 30% of chronological quarters per symbol is the stitched OOS frame,
matching `retest_stage2.py`.

## Outputs

For every cell and symbol, and pooled, report trade count, positive-trade rate,
mean net R, total net R, and each stitched-OOS quarter's count/mean. Also report
pooled stitched-OOS values and the candidate-minus-control deltas. A trade is a
win only when its final cost-adjusted R is strictly greater than zero.

## Gates and disposition

The candidate advances only if every condition holds:

1. pooled stitched-OOS net win rate is strictly greater than 80%;
2. pooled stitched-OOS expectancy is strictly positive;
3. pooled stitched-OOS expectancy is not below `CONTROL_V130`;
4. every symbol has positive stitched-OOS expectancy;
5. every complete stitched-OOS quarter has positive expectancy;
6. candidate trade-count and frequency deltas are reported. Earlier exits may
   causally re-arm the symbol sooner under live-parity enumeration; those added
   opportunities remain part of the frozen candidate and are not post-filtered;
7. no source, engine, or manifest discrepancy occurs.

Any failed gate means the 1R:1R idea is disposed of without EA changes. If all
gates pass, this screen still does not authorize deployment: it unlocks a
separately registered executable-price E1/E2 confirmation and FTMO two-phase
account MC. No confirmation or blind holdout is accessed here.

Command: `python backtest/run_v130_one_r_one_r.py`

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `16fc8f12a78db09424b6b6b7f30984a40e99894018f012289c8f1a669bd1f4d5`
