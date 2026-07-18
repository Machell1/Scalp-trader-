# v1.36-A1 signal-detection challenge specification

Date: 2026-07-18

Status: **PRE-REGISTERED BEFORE IMPLEMENTATION OR EXECUTION.** This document
freezes three discovery cells. Its SHA256 sidecar must be committed before any
candidate tape, placebo, or Monte Carlo path is generated. Results may be
appended only after the registered run. This study authorizes no MT5 write,
EA attachment, compilation, or deployment.

## Provenance and decision question

Parent evidence commit: `7ff8ab5281e753498ad435dd0b2fd104eb8a4e9b`.

Kimi 3 supplied the design mechanisms after auditing its v1.33-v1.44 support
history. Kimi is an ideation source, not the validator. The local
corrected-fidelity harness is the sole judge. One defect in the supplied design
is corrected prospectively here: Kimi wrote the six-bar impulse with an
off-by-one close index. Every cell below uses the existing audited A1 impulse
array byte-for-byte and does not independently reimplement that statistic.

The frozen question is:

> Can one of three causal signal-detection changes beat confirmed v1.36-A1 in
> corrected-fidelity, common-random-number FTMO account simulation, without
> exceeding the hard-halt gate or obtaining the result through further
> opportunity starvation?

The confirmed control is v1.36-A1: H1 hour-aligned signals on
`US30.cash, US100.cash, JP225.cash, USDJPY`; absolute audited six-bar impulse
at least 3.0 frozen signal-bar Wilder ATR(14); signal-candle direction
alignment; W2 adverse wick at least 0.30 ATR; 0.6-ATR pullback limit; existing
bar-counted pending occupancy; SL 1 ATR; bank 75% at +1R; remaining target
1.5 ATR; 8-bar time exit; E2 stress cost; existing symbol, cluster, and global
seats; 0.300% trio risk and 0.050% USDJPY risk.

Confirmed A1 evidence is 662 admitted signals, 395 fills, 2,819 events, event
SHA256 `3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573`.
Its corrected 100,000-path result was 90.9940% both-phase pass, 0.0350% hard
halt, 8.9710% timeout, and 978 successful median days. These are historical
benchmarks only; every decision below uses the paired A1 row rebuilt on the
same eligible-block intersection as the candidate rows.

## Frozen common signal notation

For completed H1 signal bar `i`, let `s_i` be the existing audited base side
(`+1` long, `-1` short), `A_i` its frozen Wilder ATR, and `z_i` the magnitude
of the existing audited impulse array. The base predicate already enforces
`z_i >= 2.0`, candle-direction agreement, and later the unchanged W2 predicate.
No cell may recalculate `z_i` from a separately indexed close series.

An **A1-qualified raw signal** has `z_i >= 3.0` plus the unchanged direction
and W2 predicates. A **marginal raw signal** has `2.0 <= z_i < 3.0` plus those
same predicates. Re-admission preserves the A1 predicate, but an added
marginal pending may legitimately occupy a seat and displace a later A1
pending. That downstream coupling is part of the treatment and must be
reported; “preserves A1” never means post-hoc preservation of completed trades.

## Frozen cells

Exactly four primary tapes are permitted: the A1 control and the following
three candidates. No combination, threshold neighbor, symbol-specific repair,
or post-result replacement is permitted.

### A — `R_STRUCT`: 20-close structural-breakout re-admission

Keep every A1-qualified raw signal. Re-admit a marginal raw signal only when
its signal close strictly escapes the prior 20 completed H1 closes:

```text
long:  struct_i = C_i > max(C_{i-20}, ..., C_{i-1})
short: struct_i = C_i < min(C_{i-20}, ..., C_{i-1})
admit_i = (z_i >= 3.0) OR (2.0 <= z_i < 3.0 AND struct_i)
```

Equality is not a breakout. With fewer than 20 prior completed H1 bars,
`struct_i = false`. The signal bar never enters its own channel. Twenty is the
pre-committed canonical Donchian lookback; 16, 24, or any other neighbor is
forbidden. All inputs exist at the signal close.

Mechanism: distinguish range escape from a range-internal 2-3 ATR spike while
recovering some positive-drift opportunity mass removed by A1. Strongest
falsification: strict breakout closes mean-revert into the limit fill and
dilute the account result.

### B — `S_ZSEAT`: normalized-impulse seat arbitration

Use the unchanged A1 raw signal set. At each exact pending-placement epoch,
remove expired/finished active lifecycles with the existing equality semantics,
then collect every new claimant at that epoch. Greedily evaluate claimants in
descending `z_i`; accept a claimant only if the existing per-symbol,
per-cluster, and two-seat global rules permit it. If the top `z_i` values differ
by at most `1e-9`, fall back to the existing source/symbol priority. Non-
contention epochs remain behaviorally identical.

The `1e-9` dead band is a determinism rule, not a tuned quality threshold.
All compared impulses are frozen at the common decision epoch. Full downstream
occupancy is rebuilt because the selected lifecycle duration may change later
admissions. Strongest falsification: contention is too rare for power, or the
largest impulse is a climax rather than the best use of the seat.

### C — `R_DRIVE`: front-half M15 drive re-admission

Keep every A1-qualified raw signal. For a marginal signal, use exactly the four
manifest-pinned completed M15 constituents of its H1 signal bar at offsets
`T, T+15m, T+30m, T+45m`. Define directional bodies
`b_k = s_i * (close_k - open_k)`, `k = 0..3`, and let `k_star` be the earliest
index attaining `max(b_k)`. Re-admit iff `k_star <= 1`.

Ties go to the earliest index. If the four timestamps are not present exactly,
do not re-admit and increment a mandatory missing-constituent counter. No next-
hour bar may be accessed. The half-bar cut is fixed by the four-part symmetry;
no quarter variant may be tested. Strongest falsification: within-hour order is
noise or duplicates the already-killed close/path-quality family.

## Explicit dead-end exclusions

The implementation must not add or proxy EMA/ADX/HTF alignment, session,
volume, AVWAP/VWAP, ORB, generic confluence, standalone wick/pin/sweep,
close-location/body strength, Kaufman efficiency ratio, aligned-interval
counts, max retrace, compression, volatility regime, positive lead-lag,
sliding/off-hour entries, market entry, deeper pullback, 5R targets, threshold
neighbors, adaptive ML, or symbol-specific thresholds. The entry, exit, risk,
cost, universe, timing, and safety book are frozen.

## Additive implementation and mandatory regressions

Implementation lives only in research code and is default-off. The historical
builder call must remain byte-identical. Candidate predicates are evaluated at
the signal bar before pending placement; filtering finished events is invalid.

Before any candidate number is accepted:

1. `python backtest/verify_data.py` must print exactly
   `verified 46 OK, 0 missing, 0 mismatched`.
2. The legacy-default regression must remain 1,645 trades, 7,317 events,
   SHA256 `3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f`.
3. The explicit v1.33-C1 regression must remain 1,684 trades, 7,145 events,
   SHA256 `b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187`.
4. Explicit A1/default-candidate-off must reproduce 662 trades, 2,819 events,
   SHA256 `3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573`.
5. Causality fixtures must compare full-frame feature values with values built
   from data truncated exactly at sampled signal closes. All must match.
6. Every H1/M15 fixture must assert the exact four allowed timestamps. Access
   to the next M15 bar is a hard failure.
7. Pass-policy and risk-policy synthetic self-tests must pass.
8. Python/C# path 0 must match exactly for A1 and every account-screen tape.

Any failure stops the registered study and is reported verbatim. It may not be
silently repaired and rerun inside these cells.

## Discovery stage: causal OOS and matched placebos

Data and costs are frozen to the same manifest and E2 stress convention used
for A1. For each symbol, the last 30% of its completed H1 bars by chronological
index is OOS. Signal placement time assigns OOS quarter and side. Calendar-edge
partial quarters are reported but excluded from the complete-quarter stability
fraction when at least three OOS quarters exist.

For `R_STRUCT` and `R_DRIVE`, generate exactly 200 random re-admission masks
with seed `20260711`. Each placebo matches the candidate's marginal raw-signal
count within symbol x side x OOS quarter. Every placebo rebuilds pending
occupancy and portfolio coupling from the signal bar. The observed re-admitted
filled subset must have OOS expectancy greater than zero and exceed the 95th
percentile of the matched placebo distribution. The predeclared negative
controls are the inside-channel remainder for `R_STRUCT` and `k_star >= 2` for
`R_DRIVE`; each must underperform its positive arm.

For `S_ZSEAT`, generate exactly 200 same-epoch random claimant orderings with
the same seed and rebuild every lifecycle. The observed full-tape OOS
expectancy must exceed the 95th percentile of those rows. The predeclared
negative control is ascending-`z_i` arbitration and must underperform
descending `z_i`.

The empirical one-sided placebo p-value is
`(1 + count(placebo >= observed)) / 201` and must be at most
`0.0166666667` (Bonferroni familywise 0.05 across three cells). Each cell also
requires positive E2-stress OOS expectancy, nonnegative OOS expectancy delta
versus A1 in at least 3/4 symbols, and nonnegative delta in at least 60% of
complete OOS quarters. `R_STRUCT` and `R_DRIVE` must retain at least 70% of
the A1 control's admitted and filled A1-qualified lifecycles after downstream
coupling. `S_ZSEAT` must retain at least 97% of A1 filled lifecycles. All cells,
placebos, negative controls, counts, quarters, failures, and null-identical
outcomes are reported.

A cell failing any discovery gate is killed and does not enter account MC.

The repository's DSR gate is also binding. For each cell's full stitched-OOS
filled-trade R distribution, compute
`sr0 = dsr_hurdle(n_trials=300, n_obs=N)` and
`DSR = psr(oos_r, sr0)` using the existing audited functions. The frozen
trial count 300 is a conservative program-wide count that exceeds the last
explicit repository ledger of 211 and includes the known v1.31-v1.44 external
screens plus all three cells here. DSR must be at least `0.95`; A1's paired
value is reported for context. No smaller trial count may be substituted.

## Account Stage 1: 20,000-path screen

All discovery survivors and A1 use one common eligible-flat-block intersection,
seed `13020260711`, 20-day moving blocks, E2 stress, 500-path chunks, identical
path IDs, and the existing corrected Python/C# policy machinery. Every survivor
runs exactly 20,000 paired paths.

A cell advances only if every gate passes against the paired A1 row:

1. hard-halt probability `<= 0.003700`;
2. conservative paired lower bound for both-phase pass is strictly `> 0`;
3. exact one-sided McNemar p-value `<= 0.0166666667`;
4. timeout is no more than paired A1 timeout plus `0.005000`; and
5. successful median completion days are no more than `1.10` times paired A1.

If multiple cells pass, select exactly one by highest conservative paired lower
bound; first tie-break is lower timeout, second is lower successful median days,
and final deterministic tie-break is cell order A, B, C. This selection rule is
frozen before execution.

## Account Stage 2: 100,000-path confirmation

Only the predeclared Stage-1 winner may run 100,000 paired paths against A1,
using the same seed, block length, E2 cost, policy, chunking, and five gates,
including the familywise McNemar threshold. Both rows and every simulator
counter are reported. A screen failure cannot be repaired; no runner-up may be
substituted after seeing results.

Possible final verdicts are:

- `SIGNAL_CHALLENGER_CONFIRMED_BEATS_A1`;
- `SIGNAL_CHALLENGER_CONFIRMATION_REJECTED`; or
- `SIGNAL_SURFACE_EXHAUSTED_NO_SURVIVOR`.

Even a confirmed result remains research-only. It does not authorize an EA
source change or deployment.

## Reporting and ledger

Report data verification verbatim; spec, code, tape, row, and result SHA256s;
all raw/admitted/filled/cancel/event counts by symbol and side; A1-predicate
retention; M15-missing counters; every placebo and negative-control summary;
OOS symbols and quarters; common-block count; path-0 parity; all 20k/100k
account fields, discordant counts, bounds, p-values, and simulator counters.
Every number is tagged `[MEASURED: command @ commit]`, `[DERIVED]`, or
`[HYPOTHESIS]`.

Trial-ledger charge: three discovery cells, plus one conditional confirmation
cell only if Stage 2 executes. Placebos and declared negative controls are
falsification machinery, not additional strategy cells. No other cell is
authorized on this branch.

---

**End of pre-registration. No result existed above this line when hashed.**
