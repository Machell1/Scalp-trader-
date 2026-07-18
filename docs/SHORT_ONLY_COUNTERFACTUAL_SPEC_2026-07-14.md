# v1.31 short-only counterfactual

## Question

The completed Deriv H1/C1 directional report found higher pooled short
expectancy than long expectancy. Does declining every long signal improve the
unchanged v1.31 strategy on a previously unopened FTMO broker-data holdout?

## Locked inputs

- Data: `backtest/data/ftmoM15_blind_20260711`, `holdout` slice only. Verify
  its manifest immediately before loading. This unlock consumes the holdout;
  no result-driven rerun, parameter alteration, or replacement candidate is
  allowed.
- Symbols/clusters: US30.cash + US100.cash share cluster 0; JP225.cash is
  cluster 1. Preserve global cap 2, cluster cap 1, fill cap 8/day,
  four-consecutive-loss stop, live four-bar pending window, no queue, and no
  pending replacement.
- Signal and exits: exactly `v130_coupled.py` phase-0 v1.31/v1.30 geometry:
  W2 0.30, frozen ATR, 0.6-ATR pullback, 1-ATR stop, 50% at +1R, TP2, eight
  H1-bar maximum hold, and stop-first lifecycle.
- Costs: E1 `F1_PER_BAR`; E2 `F2_STRICT_ASK_2X`. All broker spreads are taken
  from the frozen holdout.

## Cells

| Cell | Direction admission |
|---|---|
| C0 | Existing both-sides v1.31 control |
| S1 | Short signals only; every long is declined before pending placement |

No parameters, asset selection, risk sizing, or exits are varied. The
candidate is evaluated with the same deterministic event scheduler, so freeing
a seat by declining a long may admit a later short exactly as it would live.

## Outcomes and gates

Report every E1/E2 cell: completed trades, expectancy, win rate, total R,
long/short counts, complete-quarter values, and event-tape SHA256. For S1,
long count must be zero and all occupancy invariants must pass.

S1 is a **trade-tape pass** only if under E2: (1) its expectancy is positive,
(2) it exceeds C0 expectancy, and (3) its final complete holdout quarter is
non-negative. Otherwise S1 is disposed and no short-only account Monte Carlo
or deployment is allowed. A trade-tape pass is still not a live change: a
separate common-path account MC and owner approval are required.

All numbers are reported as `[MEASURED]`, `[DERIVED]`, or `[HYPOTHESIS]`.
There are no terminal writes.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `8b4e81360ed37631933785eb09ce9510aa7f94687987ea14a79ac81d0df51b0a`
