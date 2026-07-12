# Panic-rebound entry veto with 3R target — pre-registration

**Date:** 2026-07-12 UTC  
**Branch:** `codex/panic-veto-3r`  
**Base:** main `57ac06aa87167e3aea7292cb51c5dced70c85db3`

## Hypothesis

Momentum continuation is vulnerable when a fresh impulse is actually a violent
rebound against a preceding move in an elevated-volatility state. Daniel and
Moskowitz document momentum crashes following market declines, high volatility,
and abrupt rebounds (NBER 20439 / JFE 2016,
https://www.nber.org/papers/w20439). Applying that long-horizon result to M15
index entries is a hypothesis.

## Frozen cells

- `C0_PASSIVE_3R`: W2 continuation, 0.6 ATR realistic pullback limit, 0.02
  signal-ATR entry/TP trade-through, 1 ATR stop, 3 ATR target, 8-bar hold.
- `P1_PANIC_REBOUND_VETO_3R`: identical, except veto a signal only when both:
  1. the 32-bar return ending immediately before the six-bar impulse is opposite
     the signal by at least 2 signal ATR:
     `side[i] * (close[i-5] - close[i-37]) <= -2 * ATR[i]`; and
  2. `ATR[i]` is at or above the 80th percentile of the prior 96 closed ATR
     observations `ATR[i-96:i]`, excluding the signal bar.

If history is incomplete or the causal percentile is not finite, do not veto.
There is no threshold sweep, separate volatility-only arm, FIP, reclaim, session,
volume, liquidation, ADX, or exit change.

## Data and frame

Require `python backtest/verify_data.py` to print exactly `verified 46 OK, 0
missing, 0 mismatched`. Use only frozen `derivM15_spreadgated` data for Wall
Street 30, US Tech 100, and Japan 225. Stitched OOS is the last 30% of
chronological quarters per symbol; partial endpoint quarters are reported but
excluded from complete-quarter gates. Costs remain
`walkforward_dsr.real_cost_per_side`.

No confirmation, holdout, terminal, fresh data, or prior failed candidate is
accessed or combined.

## Implementation and regression

Add a default-`None` pre-entry predicate to `retest_fillrealism.run`, evaluated
after W2 and before pending placement. Default output must match nine frozen
tuple hashes for three symbols × buffers 0.00/0.02/0.05. Synthetic tests cover
long/short veto, long/short admission, exact threshold equality, causal exclusion
of the signal ATR, incomplete history, and default-off identity.

Registered command: `python backtest/run_panic_veto_3r.py`

## Outputs and gates

Report all-data and stitched-OOS n, win rate (`R>0`), expectancy and total R for
both cells, every symbol and quarter, veto/admission counts, and retention.
P1 advances only if all pass:

1. OOS win-rate lift at least +5.00 percentage points;
2. OOS expectancy positive and not below C0;
3. every symbol OOS expectancy positive;
4. every complete OOS quarter positive;
5. OOS trade retention at least 35%;
6. regression and synthetic tests pass;
7. no source, timing, manifest, or reporting discrepancy.

Win rate >80% is diagnostic only and cannot be tuned toward. Failure disposes P1.
A pass only unlocks separately registered confirmation; no EA/deployment authority.

## Ledger and writes

One new hypothesis cell. Proposed working ledger `214 -> 215`, subject to owner
reconciliation. Terminal writes, orders, EA changes, and settings changes: zero.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `239f3889bb36fd0dfcc46ee3376f55b86b48c1d1375c2b3be695b3f892a25467`

## Result appended after registration

Executed once at `58f2cc57723b39d56ea3049a921051ce4cb1514d`.
Verdict: **DISPOSE**. Full report: `docs/PANIC_REBOUND_VETO_3R_RESULTS_2026-07-12.md`;
lossless artifact: `backtest/panic_veto_3r_results.json`.
