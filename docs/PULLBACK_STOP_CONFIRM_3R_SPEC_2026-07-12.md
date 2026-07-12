# First-touch pullback stop-confirmation with 3R target — pre-registration

**Date:** 2026-07-12 UTC  
**Branch:** `codex/pullback-stop-confirm-3r`  
**Base:** main `57ac06aa87167e3aea7292cb51c5dced70c85db3`

## Hypothesis

A pullback trade-through can continue adversely. Instead of filling passively or
requiring the same bar to reclaim at its close, wait for a later price reversal
through the first pullback bar's extreme. This is the first-touch/confirmation
mechanism in the repository's ranked research queue, applied to the existing
signal rather than creating a new EMA system.

## Frozen cells

- `C0_PASSIVE_3R`: existing W2 signal, 0.6 ATR limit, 0.02 signal-ATR
  trade-through, 1 ATR stop, 3 ATR target, 8-bar hold.
- `S1_PULLBACK_STOP_CONFIRM_3R`: find the first 0.6 ATR trade-through inside the
  same four-bar pending window. Do not enter on that bar. For a long, set a buy
  stop at that bar's high + 0.02 signal ATR; for a short, set a sell stop at that
  bar's low − 0.02 signal ATR. Search only subsequent bars remaining in the
  original pending window. Enter at the stop level on first trade-through. If no
  later bar confirms, cancel at original expiry. SL/TP are 1R/3R from the actual
  confirmation entry using frozen signal ATR; hold is 8 bars from entry. Stop is
  pessimistic touch-fill and TP requires 0.02 ATR trade-through.

No threshold sweep, same-bar confirmation, FIP, panic veto, ADX, session, volume,
liquidation, partial, lock, trail, or exit change.

## Data and controls

Require canonical verification `verified 46 OK, 0 missing, 0 mismatched`. Use
only frozen spreadgated Wall Street 30, US Tech 100, and Japan 225. Stitched OOS
is the final 30% of quarters; partial endpoints are reported but not complete-
quarter gated. Costs remain `real_cost_per_side`. No blind/confirmation/terminal
or prior failed candidate is accessed.

Default realistic-control tuple hashes for three symbols × buffers
0.00/0.02/0.05 must remain identical. Synthetic tests cover long/short confirm,
no same-bar fill, expiry cancellation, actual confirmation entry anchoring,
stop-first, and 3R TP trade-through.

Registered command: `python backtest/run_pullback_stop_confirm_3r.py`

## Gates

Report all cells, symbols, quarters, touch/confirm/cancel counts and retention.
S1 advances only if all pass: OOS win-rate lift >=5.00 pp; OOS expectancy positive
and >=C0; every symbol positive; every complete OOS quarter positive; OOS trade
retention >=35%; regression/synthetic integrity. >80% is diagnostic only.
Failure disposes; pass unlocks separate confirmation, never deployment.

One new cell; proposed working ledger `215 -> 216`. Terminal/EA/order writes: 0.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `PENDING`

