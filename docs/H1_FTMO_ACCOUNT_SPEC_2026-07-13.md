# H1 FTMO account-level test — pre-registration

The H1 screen passed its expectancy gates. This cell tests whether that result
survives the v1.30 account rules. It uses the same seed `13020260711`, 20-day
moving blocks, C0/C1/P1 risk policies, sequential two-phase simulation, Wilson
gates, and E1/E2 cost modes as the registered M15 account test.

H1 bars are the frozen complete 4xM15 aggregation from
`H1_TIMEFRAME_SPEC_2026-07-13.md`. For each W2 H1 pending-limit lifecycle, the
event tape records placement, fill/cancel, one close mark per bar, a 50%
partial at the first causal +1R bar when reached before the stop, and the
resolver's final stop/TP/time event. Entry cost is the measured H1 per-side
spread; E2 doubles it. No API data, terminal access, or EA write is allowed.

Because the source is an OHLC-derived H1 tape rather than a native H1 broker
feed, the account result is a historical H1 model and is not promoted without
native-H1/forward validation. The exact C# output must match the Python policy
engine at path 0 for C0/C1/P1 before the 100,000-path run.

Ledger charge proposed: one confirmatory H1 account cell (E1/E2 paired modes),
pending owner review. No entry parameter sweep is permitted.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `de199c9c8f9cebb2810da2a3490c681788d37f7ce67b01c962c07df2b87fecc6`

## Execution record

The first path-0 attempt failed before producing an outcome with
`BootstrapOverlapError: source cluster overlap: 0`. The independent per-symbol
H1 enumeration had not yet applied the registered one-seat US30/US100 cluster
and two-seat global scheduler. The tape builder was corrected to apply that
scheduler; no account result was used from the failed attempt.

The corrected scheduler still allowed a same-epoch terminal/placement tie;
path 0 failed again with `BootstrapOverlapError: source cluster overlap: 0`
(`H1:US30.cash:1999` versus `H1:US100.cash:1998`). Equality is now retained as
occupied through the terminal epoch; no account result was used.
