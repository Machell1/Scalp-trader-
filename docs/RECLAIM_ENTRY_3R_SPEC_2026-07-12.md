# Immediate pullback-reclaim entry with 3R target — pre-registration

**Date:** 2026-07-12 UTC  
**Branch:** `codex/reclaim-entry-3r`  
**Base:** main `57ac06aa87167e3aea7292cb51c5dced70c85db3`

## Question and hypothesis

The current passive pullback limit is filled while price is moving adversely.
The candidate keeps the existing six-bar ≥2 ATR momentum signal, W2 adverse-wick
gate, 0.6 ATR pullback level, one-ATR stop, three-ATR target, eight-bar hold,
four-bar pending window, symbol set, costs, and causal re-arm semantics. It changes
only entry confirmation: after a realistic trade-through of the pullback level,
price must close back through that level in the momentum direction; entry occurs
at the next bar's open.

Hypothesis: immediate reclaim confirmation rejects continuing adverse moves,
raising net positive-trade rate by at least 5 percentage points without lowering
stitched-OOS expectancy versus the realistic passive-limit control.

Mechanism source: passive limit fills are state-dependent and can coincide with
adverse price drift: https://arxiv.org/abs/2407.16527. Transfer from order-book
research to this M15 CFD system is a hypothesis, not evidence of profitability.

## Frozen cells

- `C0_PASSIVE_3R`: existing W2 continuation; 0.6 ATR resting limit; entry requires
  trade-through by 0.02 signal ATR; SL 1.0 ATR; TP 3.0 ATR; hold 8 bars.
- `R1_IMMEDIATE_RECLAIM_3R`: identical signal and pullback level. On the first bar
  within the four-bar pending window that trades through the level by 0.02 signal
  ATR, require `close > limit` for a long or `close < limit` for a short. If true,
  enter at the next bar's open; if false, cancel at that bar close and allow the
  symbol to re-signal from the next bar. No later reclaim of that order is allowed.

For both cells, the protective stop remains pessimistic touch-fill. The 3R
take-profit is a resting limit and requires trade-through by 0.02 signal ATR.
Round-trip cost uses `walkforward_dsr.real_cost_per_side` exactly as the existing
screen engine. No scale-out, lock, trail, direction change, or threshold sweep.

## Data and frames

Before execution run `python backtest/verify_data.py`; any result other than
`verified 46 OK, 0 missing, 0 mismatched` stops the study. Use only the frozen
canonical `derivM15_spreadgated` trio: `Wall_Street_30`, `US_Tech_100`, and
`Japan_225`. No FTMO terminal, confirmation split, blind holdout, crypto, volume,
open-interest, liquidation, or fresh data is accessed.

For each symbol, the final 30% of chronological quarters is stitched OOS, matching
`retest_stage2.py`. Complete quarters exclude partial endpoint quarters.

## Implementation and regression

Add `entry_mode="limit"` as a default-off-compatible parameter to
`backtest/retest_fillrealism.py::run`. With the default, every returned tuple must
be byte/equality identical to the pre-change control for all three symbols at
buffers 0.00, 0.02, and 0.05. Add a synthetic test covering long/short pass,
long/short reject, next-open entry, cancellation/re-arm, stop-first, and 3R
trade-through. Any regression difference stops the study before R1 is exposed.

Registered command: `python backtest/run_reclaim_entry_3r.py`

## Required outputs

For C0 and R1, report all-data and stitched-OOS trade count, net positive-trade
rate (`R > 0`), expectancy, total R, and per-symbol/per-quarter cells. For R1 also
report signal count, trade-through count, reclaim passes, reclaim rejects, unfilled
orders, pass rate conditional on trade-through, and frequency delta versus C0.
Report every cell even when a gate fails.

## Gates and disposition

R1 advances to a separately registered executable-price E1/E2 confirmation only
if all gates pass:

1. stitched-OOS net positive-trade rate is at least C0 + 5.00 percentage points;
2. stitched-OOS expectancy is positive and not below C0;
3. each symbol's stitched-OOS expectancy is positive;
4. each complete stitched-OOS quarter expectancy is positive;
5. stitched-OOS R1 trade count is at least 35% of C0;
6. default-mode regression and all synthetic tests pass;
7. no manifest, source, or causal-timing discrepancy occurs.

The owner's >80% win-rate objective is reported as a diagnostic, not used to tune
the cell. If R1 fails any gate, dispose of it. If it passes, it is still not an EA
change and cannot be deployed until cost-ledger confirmation, FTMO two-phase MC,
and forward validation pass.

## Trial ledger and writes

One new hypothesis cell. Main records 209; pending codex branches have already
exposed three charged development cells. Proposed global working charge is
`212 -> 213`, subject to owner adjudication. Terminal writes, orders, EA changes,
and live-setting changes authorized: zero.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `PENDING`

