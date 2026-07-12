# v1.30 FTMO pass-policy study — pre-registration

**Date:** 2026-07-12 UTC

**Branch:** `codex/v130-ftmo-pass-policy`

**Base:** `57ac06aa87167e3aea7292cb51c5dced70c85db3`

**Status:** protocol only. No risk-weighted edge cell, account-policy path,
Monte Carlo pass probability, confirmation cell, or holdout cell defined here
has been run.

## 1. Question, distinction, and null

Can an unchanged MomentumPullbackEA v1.30 trade process exceed an 88% FTMO
2-Step Challenge pass probability by changing only risk allocation: keep every
US30, US100, and JP225 signal plus its pending/cluster/global occupancy, but
risk one-fifth as much on the development-negative US30 stream and use lower,
phase-normalized risk in Phase 2?

This study distinguishes two quantities:

- **trade win rate** is the fraction of the unchanged pre-account trade tape
  with positive final net R;
- **Challenge pass probability** is the probability that the account passes
  Phase 1 and Phase 2 sequentially before any FTMO breach, EA hard halt, or
  numerical timeout.

Risk sizing cannot relabel the fixed trade outcomes or raise pre-account trade
win rate. It can change barrier-hitting probability, cash weighting by symbol,
lot rounding, daily-halt admissions, and completion time. No 90% trade-win
claim is permitted from this study.

**Null:** the sole promotion policy fails to put its one-sided 95% lower bound
strictly above 88% under both the measured executable ledger and mandatory
double stress, or fails another registered robustness gate.

## 2. Revealed evidence and post-selection accounting

The immediately preceding executable-ledger audit measured positive pooled E1
and E2 expectancy, but failed because US30 was negative and E2 depended on both
positive symbols. Its binding verdict was `KILLED_AT_EDGE_GATE`; no account MC
ran and neither blind frame was opened. [MEASURED:
`docs/V130_COST_LEDGER_RESULTS_2026-07-12.md` @
`57ac06aa87167e3aea7292cb51c5dced70c85db3`]

This sign split is fully revealed development evidence. The 5:1 allocation is
therefore data-informed and is not a free confirmatory observation. It is a
round, fixed ratio chosen before any new weighted calculation; no ratio grid,
continuous optimizer, alternate cutoff, or rescue policy is allowed on this
frame. It is charged in the trial ledger and must pass locked confirmation and
sealed holdout unchanged before any historical promotion label.

The uniform 0.20%/0.10% phase schedule was pre-registered in the earlier risk
study but never reached an account path because that study died at its edge
gate. C1 therefore has no prior pass-probability result; this protocol charges
its first actual account-policy test. [MEASURED: `docs/V130_RISK_POLICY_SPEC_2026-07-11.md`
and `backtest/v130_mined_edge_results.json`]

Read-only frozen broker metadata recorded volume minimum and step `0.01` for
all three symbols. This does not prove that every low-risk order is executable;
the account simulator must apply actual stop distance, tick value, balance,
flooring, and minimum-lot over-risk rejection on every entry. [MEASURED:
`backtest/data/ftmoM15_blind_20260711/METADATA.json`]

## 3. Frozen strategy and frequency invariants

All policies use the same:

- symbols and scan order: US30.cash, US100.cash, JP225.cash;
- US30/US100 shared cluster, JP225 independent cluster, one seat per cluster,
  and two seats globally;
- one pending or position per symbol;
- M15 Wilder ATR(14), six-bar momentum at 2.0 ATR, and continuation direction;
- W2 adverse-wick predicate `>= 0.30 ATR`;
- pullback limit offset `0.60 ATR` and live four-working-bar pending window;
- stop at one frozen signal ATR, 50% partial at +1R, remainder TP at +2R,
  and the frozen eight-bar holding convention;
- stop-first same-bar ordering, followed by partial, then TP;
- pending, fill, partial, cooldown, day-cap, and occupancy semantics already
  verified in `parity_engine.run_live`;
- eight fills per EA server day and four final losses per EA server day;
- no signal queue, no replacement, no side filter, and no symbol deletion.

The scheduler creates one policy-independent pre-account tape per cost column.
Within each column, C0, C1, and P1 must consume the same tape hash.
Account-level entries can then
differ only because of registered lot limits, balance, FTMO/EA halts, phase
transition, or timeout. Every such difference is reported. Cancelling or
skipping an account entry never causes favorable post-hoc re-enumeration of a
signal rejected in the frozen tape; this is conservative.

No entry, exit, filter, partial, target, stop, pending, symbol, time, or
frequency parameter may change after the protocol hash.

## 4. Data, access, and sequencing

Before every outcome command:

1. `python backtest/freeze_ftmo_v130_blind.py --verify` must print exactly
   `verified FTMO blind freeze 9 OK, 0 missing, 0 mismatched, 0 extra`.
2. `python backtest/verify_data.py` must print exactly
   `verified 46 OK, 0 missing, 0 mismatched`.
3. Development may load only `load_ftmo_split("mined")`.
4. Confirmation may load only `load_ftmo_split("confirmation")`, and only
   after a committed development artifact records every gate passed.
5. Holdout may load only `load_ftmo_split("holdout")`, and only after a
   committed confirmation artifact records the unchanged P1 passed every gate.
6. Each runner refuses to overwrite its result and has no force, alternate
   policy, threshold, seed, path-count, or frame-bypass CLI.

The frozen frames are:

- development: newest 30,000 M15 bars per symbol, already mined;
- locked confirmation: preceding 30,000 bars per symbol;
- sealed holdout: oldest 39,999 bars per symbol.

Repository lineage can prove what the tracked runner opens but cannot prove
that no manual or untracked process previously inspected nominally blind data.
Historical status remains conditional on the owner's external attestation.

No terminal data refresh, order action, EA input write, chart change, compile,
deployment, or terminal restart is part of this study.

## 5. Executable-price columns

The corrected cost ledger from the preceding audit is binding:

- `E0_EXECUTABLE`: side-correct executable prices, zero extra slippage and
  zero swap; decomposition diagnostic only;
- `E1_MEASURED`: E0 minus `0.02R` fixed full-position slippage plus current
  negative swap; positive swap credits suppressed;
- `E2_STRESS`: E0 minus `0.04R` fixed slippage plus twice current negative
  swap; mandatory promotion stress.

Both E1 and E2 independently enumerate causal trades because cost-induced
final-sign changes can change the deployed EA's four-loss server-day gate. E1
and E2 are both eligibility columns. E0 cannot rescue a failure.

The committed cost-audit JSON is evidence, not an MC lifecycle source: it does
not contain the raw event tape. The new runner must causally regenerate E1 and
E2 from the frozen frame and reproduce the preceding audit's event and
diagnostic hashes before adapting those in-memory events to account cashflows.
Any hash mismatch stops before the weighted edge or MC.

The full fixed slippage debit is applied to balance at entry, the conservative
timing for drawdown. For EA deal classification only, it is allocated pro rata
to the partial and final exit fractions. Negative swap accrues against the
open position's equity at each registered Europe/Helsinki rollover, including
Friday triple, but does not change closed balance or current-balance sizing
until it is realized when the position closes. Positive swap remains zero.
The accumulated swap is attached to the final deal for the EA's loss-streak
classifier, matching deployed history semantics. There is no second
Saturday/Sunday charge after Friday triple. Swap cash must use the actual
rounded volume still open at rollover, not the theoretical 50% fraction.

## 6. New account-event fidelity requirements

Before an edge or policy cell, the existing pure account engine may be extended
only additively and default-off to support:

1. a symbol-specific risk multiplier in `RiskPolicy`;
2. timed swap cashflows that do not change position volume or occupancy;
3. separate balance-cash and EA deal-classification components;
4. exact final-server-day loss classification: negative increments, positive
   resets, exact zero leaves the streak unchanged;
5. policy-dependent current-balance lot sizing without altering the source tape.

For every admitted position:

- requested risk cash is current closed balance times phase risk for that
  symbol;
- loss per lot is stop distance divided by trade tick size times loss-side
  tick value;
- volume is floored to `volume_step` and capped at `volume_max`;
- `volume_min` substitution is allowed only when its stop risk is no more than
  1.5 times the requested budget; otherwise the entry is rejected;
- the 50% partial volume is floored to step and skipped if either the close or
  remainder would be below minimum; it is never rounded up;
- profit-side and loss-side tick values are used according to each realized
  price move;
- entry slippage, timed swap, partial price cash, and final price cash must sum
  exactly to the saved account ledger within `1e-9` cash.

All cost/timing additions must be absent by default so prior tests and hashes
remain unchanged.

The symbol-risk map is complete and immutable: it contains exactly the three
registered symbols for both phases, has no fallback, and rejects a missing or
extra symbol before replay.

## 7. FTMO and deployed-EA account rules

The modeled product is the standard FTMO 2-Step Evaluation:

- Phase 1 target +10%; Phase 2 target +5%;
- maximum daily loss 5% of phase initial balance measured from balance at
  00:00 CE(S)T; equality is failure;
- static maximum loss 10% of phase initial balance; equality is failure;
- minimum four distinct trading days per phase;
- no commercial time limit.

Sources: `https://ftmo.com/en/trading-objectives/`,
`https://ftmo.com/en/faq/can-i-trade-news/`, and
`https://ftmo.com/en/faq/do-i-have-to-close-my-positions-overnight-or-before-the-weekend/`.
Evaluation news trading and overnight/weekend holding are allowed, so neither
is invented as an FTMO prohibition. The EA's existing news guard remains
unchanged because it is part of the deployed configuration.

The simulator also retains the stricter deployed v1.30 rails:

- 4% EA daily halt from Europe/Helsinki server-day start balance;
- permanent 8% peak-equity hard halt and 9% static hard halt;
- eight fills and four final losses per EA server day;
- one symbol, one cluster, and two global seats.

A daily halt blocks later entries but continues managing open positions. A
firm breach or permanent EA hard halt before target is failure, never survival.
A phase passes only with no open position or working pending, at or above
closed-balance target, with four trading days. Once target and minimum days are
first satisfied, new entries are frozen, working pendings are cancelled at the
next modeled management event, and existing positions continue to their frozen
exits. Same-timestamp management/fill priority remains the scheduler's existing
priority; the protocol does not retrospectively cancel an already-prioritized
fill. Passage occurs only if the eventual flat closed balance still meets
target. Phase 2 resets account and EA ledgers to 100,000 and begins on
the next Prague calendar day while continuing the same sampled stream; it is
not redrawn.

All calendar days, weekends, and zero-trade days remain in the stream. The
numerical ceiling is 3,650 calendar days per phase; unresolved paths fail. The
reported successful-path P90 must not exceed 1,825 total calendar days.

## 8. Pre-registered policies and ledger

Risk is a fraction of current closed balance at each entry.

| policy | Phase 1 JP225 | Phase 1 US100 | Phase 1 US30 | Phase 2 JP225 | Phase 2 US100 | Phase 2 US30 | role | charge |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| C0 | 0.30% | 0.30% | 0.30% | 0.30% | 0.30% | 0.30% | deployed equal-risk account control | 0 |
| C1 | 0.20% | 0.20% | 0.20% | 0.10% | 0.10% | 0.10% | phase-normalized equal-risk attribution control | +1 |
| **P1** | **0.20%** | **0.20%** | **0.04%** | **0.10%** | **0.10%** | **0.02%** | **sole promotion candidate** | **+1** |

P1 makes the positive-symbol target distance 50 nominal R in each phase while
preserving the same 5:1 US30 allocation ratio. [DERIVED from fixed targets and
registered risks]

No other risk level, ratio, drawdown throttle, hot-hand rule, volatility size,
target-chasing band, symbol deletion, or policy combination may be tested.

Trial ledger starts at 209. Maximum charge is `209 -> 213`: C1 development
`+1`, P1 development `+1`, unchanged P1 locked confirmation `+1`, and
unchanged P1 sealed holdout `+1`. C0, E0, sensitivities, and fidelity controls
are uncharged. Only cells actually run are charged, and every run is reported.

## 9. Allocation edge gate before account Monte Carlo

For allocation weights JP225 `1.0`, US100 `1.0`, and US30 `0.2`, define:

`weighted_expectancy = sum(weight[symbol] * trade_R) / sum(weight[symbol])`

over the unchanged pre-account tape. The same relative weights apply to P1 in
both phases. Before any account MC, E1 and E2 must each satisfy:

1. weighted pooled expectancy strictly positive;
2. weighted last-four-complete-quarter expectancy strictly positive;
3. at least four complete quarters;
4. at least 250 completed trades per symbol;
5. weighted numerator remains strictly positive after deleting each one of
   JP225, US100, or US30;
6. weighted numerator remains strictly positive after deleting each complete
   calendar quarter in turn;
7. JP225 and US100 raw expectancy are each strictly positive, and US30's
   weighted loss magnitude is smaller than either core symbol's positive
   weighted contribution;
8. deterministic rerun event and diagnostic hashes match;
9. all fidelity and access gates pass.

A complete quarter has both its first and final Europe/Prague calendar day
inside the frozen frame. Boundary fragments are reported as partial but are
excluded from the four-quarter, last-four, and leave-one-quarter gates. Fewer
than four complete quarters is failure.

Raw unweighted pooled, symbol, quarter, and delete-one results remain reported;
their prior failures are not hidden. A failed weighted gate kills the account
study with zero MC paths.

## 10. Monte Carlo and inference

Primary inference uses:

- 100,000 deterministic paths;
- seed `13020260711`, unchanged from the earlier unexecuted risk protocol;
- 20 complete Europe/Prague calendar-day moving blocks;
- block starts only where both ends are flat across positions and working
  pendings;
- one pre-generated source-index stream per path, reused across C0/C1/P1;
- sequential Phase 1 and Phase 2 on that same stream;
- the conservative open-equity envelope in which each open position may be at
  its stop simultaneously, with global cap two;
- one-sided 95% Wilson bounds using `z = 1.6448536269514722`.

At 100,000 paths, the strict `lower > 0.88` rule requires at least 88,170
both-phase passes; 88,169 is insufficient. [DERIVED from the frozen Wilson
formula]

The 2x-stop gap envelope, observed-mark equity, and IID calendar-day bootstrap
are diagnostics run only after the primary P1 gate passes. They cannot rescue
the primary. Moving-block stitches with an orphan, overlap, ambiguous event
order, non-flat boundary, or policy-dependent source stream are fatal.

Report for every cost column and policy:

- paths, Phase 1 pass, conditional Phase 2 pass, both-phase pass count, point
  probability, and one-sided Wilson lower/upper bounds;
- FTMO daily/static breach, EA hard halt, and timeout counts, probabilities,
  and one-sided upper bounds;
- median and P90 total calendar days among successful both-phase paths;
- ending/minimum/peak equity distributions and failure reasons;
- entries, completions, low-lot substitutions/rejections, partial rounding
  skips, daily-halt skips, fill-cap skips, and loss-streak skips;
- pre-account tape count, expectancy, win rate, hashes, and all policy admission
  divergences;
- per-symbol and leave-one-complete-quarter-out attribution after primary pass.

The paired P1-minus-C0 and P1-minus-C1 gates use matched path IDs. For each
delta, `p10 - p01` is bounded by the Bonferroni difference between 97.5%
one-sided exact Clopper-Pearson lower and upper bounds for the two discordant
multinomial cells. This is conservative and fixed before outcomes.

## 11. Promotion, blind sequence, and kill rules

P1 advances from development only if, in both E1 and E2 primary moving-block
two-stop runs:

1. the both-phase pass one-sided 95% Wilson lower bound is strictly greater
   than 88%;
2. paired P1-C0 and P1-C1 one-sided 95% lower bounds are both greater than 0;
3. P1 FTMO-breach and EA-hard-halt upper bounds are no worse than both C0 and
   C1;
4. timeout one-sided 95% upper bound is at most 1%;
5. successful-path P90 completion is at most 1,825 total calendar days;
6. P1 has zero broker-minimum substitutions, zero broker-minimum entry
   rejections, and zero partial-close rounding skips, preserving the registered
   5:1 allocation and v1.30 exit geometry in executable lots;
7. the pre-account trade IDs, lifecycle, expectancy, win rate, and hashes are
   policy-independent, and every account admission difference is attributable
   to a registered account rule;
8. all allocation-edge, event-ledger, regression, access, and determinism gates
   pass.

Any failure kills P1 on development. C1 is attribution only and cannot be
promoted. Diagnostics cannot rescue a failure. No confirmation or holdout is
opened after a development failure.

After development passage, locked confirmation runs only C0, C1, and unchanged
P1 with the same E1/E2 columns, paths, seed, blocks, account rules, and gates.
After confirmation passage, sealed holdout does the same once. No parameter,
gate, cost, seed, or implementation change is permitted between frames.

Historical passage is labeled `HISTORICALLY GATE-ELIGIBLE`, not live validated.
No live risk input or EA code changes from historical research alone. A
separate implementation PR and flat-account deployment review are required.
Prospective validation still requires at least 250 post-policy completed
trades across two calendar quarters, at least 50 per symbol, clean telemetry,
and the same pre-registered >88% lower-bound calculation.

## 12. Mandatory pre-outcome tests

All must pass before the weighted edge cell:

1. exact blind-manifest and 46-file data verification;
2. default-off 46-file golden regression;
3. existing 9 parity-hook, 49 cost-ledger, 7 coupled, and account-engine
   synthetic suites;
4. backward-compatible scalar `RiskPolicy` behavior;
5. exact symbol-risk selection for both phases;
6. timed ordinary and Friday-triple swap accrual in open equity, actual-volume
   calculation, and final-close balance realization;
7. positive-swap suppression and no weekend double charge;
8. partial-before-rollover open fraction;
9. entry slippage balance timing versus exit-fraction classifier allocation;
10. cross-server-midnight partial/final classifier, zero-P&L streak, and
    four-loss stop;
11. profit/loss tick values, lot floor, min substitution/rejection, max cap,
    and partial skip;
12. Prague midnight and both DST transitions, plus separate Helsinki EA day;
13. FTMO daily/static equality breach, EA daily/peak/static rails, and halt
    persistence;
14. simultaneous two-stop envelope and 2x-gap diagnostic;
15. four trading days, target recognition only when positions and pendings are
    both absent, next-day phase transition, same-stream continuation, and both
    phase timeouts;
16. flat 20-day block boundaries, orphan/overlap rejection, common random
    numbers, Wilson known values, and paired exact-bound known tables;
17. two identical complete small seeded runs produce identical normalized
    bytes and SHA256;
18. an independent reference account calculation matches registered fixtures
    within `1e-9` cash.

The optimized runner may cache eligible flat block starts, compile immutable
day templates, stream path IDs, and evaluate all policies inside one path loop.
It may use deterministic path-ID chunks in parallel only after single-process
and parallel normalized results are byte-identical. Optimization may not
change event order, source indices, floating-equity checks, or inference.

Any mismatch stops before an outcome. Failed tests and commands are retained
verbatim; no repair-and-silent-rerun is allowed after an outcome has begun.

## 13. Deliverables

- this committed, SHA256-pinned protocol;
- additive account-event and symbol-risk support with default-off regression;
- an optimized deterministic runner that cannot open a frame out of sequence;
- lossless development, and if authorized confirmation/holdout, result JSON;
- exhaustive tagged result reports and trial-ledger updates;
- PRs to main; no terminal write on this research branch.

---
**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `0bccf0057f65b30e70a3b70663476ecadf6348efaee5aa366f3e235a3dfad671`

---
## RESULTS

Not run at registration. Results may be appended here only; the protocol above
the recorded hash is immutable.
