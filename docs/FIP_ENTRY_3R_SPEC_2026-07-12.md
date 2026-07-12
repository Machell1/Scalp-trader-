# Smooth-impulse FIP entry gate with 3R target — pre-registration

**Date:** 2026-07-12 UTC  
**Branch:** `codex/fip-entry-3r`  
**Base:** main `57ac06aa87167e3aea7292cb51c5dced70c85db3`

## Hypothesis

The baseline admits any five-close movement spanning the six-bar momentum window
when its magnitude is at least two signal ATR and the current candle agrees. The
candidate asks whether gradual, directionally consistent impulses have higher
continuation quality than impulses dominated by reversals/noise.

Published motivation: Da, Gurun, and Warachka report stronger continuation after
continuous rather than discrete return paths (`Frog in the Pan`, Review of
Financial Studies 2014, https://doi.org/10.1093/rfs/hhu003). Their horizon and
assets differ from this M15 index system, so transfer is explicitly a hypothesis.

## Frozen cells

- `C0_PASSIVE_3R`: existing W2 continuation, 0.6 ATR pullback limit, realistic
  0.02 signal-ATR entry/TP trade-through, 1 ATR stop, 3 ATR target, 8-bar hold.
- `F1_FIP4OF5_3R`: C0 plus one pre-entry predicate. For signal index `i`, compute
  the five close-to-close changes `c[k]-c[k-1]` for `k=i-4..i`. A change is
  aligned when `side[i] * (c[k]-c[k-1]) > 0`. Admit only when at least four of
  five changes align. Zero changes are not aligned. No threshold sweep, bar-size
  filter, reclaim rule, ADX, volume, session, or volatility condition is allowed.

This is equivalent to an information-discreteness cutoff of at most −0.6 on the
five non-overlapping close returns when none is zero, but implementation and tests
use the explicit aligned-count definition above.

## Data, frames, and costs

Run `python backtest/verify_data.py` first; only `verified 46 OK, 0 missing, 0
mismatched` permits execution. Use frozen `derivM15_spreadgated` data for
`Wall_Street_30`, `US_Tech_100`, and `Japan_225`. The final 30% of chronological
quarters per symbol is stitched OOS. Complete-quarter gates exclude partial
endpoint quarters. Costs use `walkforward_dsr.real_cost_per_side` unchanged.

No confirmation split, blind holdout, FTMO terminal, volume/liquidation data,
fresh data, or prior reclaim candidate is accessed.

## Implementation and regression

Add an optional default-`None` pre-entry predicate to
`backtest/retest_fillrealism.py::run`, evaluated after the frozen W2 signal and
before pending placement. Default output must reproduce the nine previously
frozen control tuple hashes across three symbols and buffers 0.00/0.02/0.05.
Synthetic tests cover long/short 4-of-5 pass, 3-of-5 fail, zero-return fail, causal
window boundaries, and default-off identity. Any discrepancy stops before F1.

Registered command: `python backtest/run_fip_entry_3r.py`

## Outputs

For both cells report all-data and stitched-OOS n, net win rate (`R>0`), mean R,
total R, and every symbol/quarter cell. For F1 report eligible and rejected signal
counts and retention versus C0. Report all cells regardless of verdict.

## Gates

F1 advances only if every gate passes:

1. stitched-OOS win rate is at least C0 + 5.00 percentage points;
2. stitched-OOS expectancy is positive and not below C0;
3. every symbol's stitched-OOS expectancy is positive;
4. every complete stitched-OOS quarter expectancy is positive;
5. stitched-OOS trade count is at least 35% of C0;
6. all regression and synthetic checks pass;
7. no source, manifest, timing, or reporting discrepancy occurs.

Win rate above 80% is reported as an untuned diagnostic. Failure of any gate means
dispose. A pass unlocks a separately hashed FIP-plus-reclaim interaction test; it
does not authorize EA changes, deployment, confirmation, holdout, or FTMO MC.

## Ledger and writes

One new hypothesis cell. Proposed global working ledger charge `213 -> 214`,
subject to owner reconciliation of pending branches. Terminal writes, orders, EA
changes, and terminal-setting changes authorized: zero.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `f5d20adc0f9d3d8535a8c4b585f4ef2c6fa5a82261b66d5b3073299325d79ad4`
