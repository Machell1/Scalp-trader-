# v1.36-A1 M15-grain universe-admission specification

Date: 2026-07-18

Status: **PRE-REGISTERED BEFORE IMPLEMENTATION OR OUTCOME EXECUTION.** This
document freezes two symbol-discovery cells, their conditional account screens,
and one conditional confirmation. Its SHA256 sidecar must be committed before
any A1 candidate tape, placebo, or Monte Carlo path is generated. This study
authorizes no EA change, MT5 write, attachment, compilation, whitelist change,
or deployment.

## Provenance, conflict resolution, and question

Parent commit: `7c21153900b83e3253ee4c1713bf1913740b9b85`.

`CODEX_CONSTITUTION.md` is absent at the parent commit and `CODEX_HANDOFF.md`
states that it was repealed. The newer dated `README.md` nevertheless links it
as binding. This study follows the stricter surviving README research rules:
hashed preregistration, frozen data, real instrument costs, matched controls,
chronological validation, DSR, doubled-cost stress, paired challenge Monte
Carlo, default-off implementation, and owner review.

The confirmed live research control is v1.36-A1 on `US30.cash`, `US100.cash`,
`JP225.cash`, and `USDJPY`. Its published `90.9940%` both-phase pass estimate is
from the existing H1-OHLC-grain account tape. It is context only. This study
remeasures its control on the same M15-grain machinery and common path frame as
each candidate; it must not import `90.9940%` as a comparison row.

The frozen question is:

> Can exactly one predeclared non-dead FTMO symbol add useful opportunity to
> the frozen v1.36-A1 portfolio under M15-grain quote-side execution without
> reducing paired FTMO challenge pass probability, increasing hard-halt risk,
> slowing successful completion, or displacing the existing edge?

## Selection exposure and permitted cells

Exactly two candidates are permitted, in this fixed order:

1. `FRA40.cash`, canonical source `France_40`;
2. `AUS200.cash`, canonical source `Australia_200`.

Both symbols were exposed in the earlier v1.31-geometry universe study. Their
old 2.0-ATR results and account failures selected them for this retest. Exact
3.0-ATR A1 outcomes are new, but neither the symbols nor calendar bytes are
unseen. Therefore the final chronological segment below is called **reused
chronological validation**, never an untouched holdout. A historical pass may
nominate one symbol for a separately approved demo-forward test; it cannot by
itself prove future FTMO performance.

`XAUUSD` is excluded because the current README records gold as a six-method
dead end and its frozen metadata uses an obsolete commission kind. `LTCUSD`
and all other crypto are excluded because the README records FTMO crypto as
cost-dead and the LTC spread snapshot is unmeasured. No runner-up, near-miss,
metal, crypto, FX, energy, or additional index may be substituted after a
failure.

## Frozen data, metadata, and costs

- Canonical data: `backtest/data/MANIFEST.sha256`, checkout SHA256
  `ec1fcc26132366ab157b8d298c1cf60d79d63ac16708d1a887a1740ad46de49f`.
- Mandatory pre-run output: `python backtest/verify_data.py` must print exactly
  `verified 46 OK, 0 missing, 0 mismatched`.
- Broker metadata: `backtest/h1_universe_broker_meta.json`, exact LF-checkout
  SHA256
  `bb0b3489c48e7cad83e5a85c3eea6005db7c5ec0e7ed9098c76814bb049cd3a6`.
  The older recorded CRLF-normalized hash is not used.
- Live EA source is read-only context, SHA256
  `531d2a8b305e145241d00b9db11f716b49f1d90f190914046ce7b7cdae02b833`.
- `FRA40.cash` uses the larger of its manifest source spread and frozen FTMO
  snapshot spread. Commission is zero.
- `AUS200.cash` has no source spread field. It uses the already registered,
  explicitly modeled `0.03 ATR per side` fallback, or the FTMO snapshot if
  larger. Commission is zero. This assumption must be prominent in results.
- `E1_MEASURED` charges the complete per-side spread plus commission once on
  each full-size round trip. `E2_STRESS`, the admission column, doubles the
  entire E1 per-side cost. No positive swap is credited; unavailable swap is
  reported as a venue-transfer limitation.

For quote-side trigger realism, input bars are bid bars. At each M15 bar, the
full modeled spread is the maximum of available source spread, the frozen FTMO
snapshot spread, and any registered fallback. For a fallback expressed in ATR,
the full spread is twice the per-side fallback times the frozen signal ATR.
Long entries require `bid_low + full_spread <= limit`; short entries require
`bid_high >= limit`. Long stops/partials/targets use bid. Short stops use ask
high and short partials/targets use ask low. Protective stops trigger on touch.

## Frozen A1 signal and lifecycle

Every control and candidate uses exactly:

- complete hour-aligned H1 bars formed from four contiguous manifest M15 bars;
- the audited `parity_engine.prep_symbol` Wilder ATR(14), candle-direction
  predicate, and six-bar impulse array;
- absolute six-bar impulse at least `3.0` frozen signal-bar ATR;
- W2 adverse-side wick at least `0.30` signal-bar ATR;
- limit entry `0.60 ATR` back from the signal close;
- pending placement at the next M15 open and eligibility across exactly the
  next 12 M15 bars, representing three H1 bar-counted windows;
- stop distance `1.0 ATR`;
- bank `75%` once at `+1.0R`;
- residual target `1.5 ATR` from entry;
- time exit at the close of the eighth broker H1 bar counted from the entry
  H1 bar, using the final observed M15 close in that H1 bar;
- pessimistic ambiguous-bar order: stop, partial, target;
- transaction cost charged once on the original full size.

Signals are built on H1 and resolved only through their causally available raw
M15 constituents. No next-bar feature, H1 exit shortcut, completed-trade
post-filter, parameter neighbor, side suppression, symbol-specific threshold,
market entry, or exit change is permitted.

## Frozen portfolio scheduling and risk

The control priority is permanently:

`US30.cash`, `US100.cash`, `JP225.cash`, `USDJPY`.

The tested candidate is appended fifth. Alphabetical resorting is forbidden
because it would demote `USDJPY` at same-epoch contention. Clusters are:

- `US30.cash|US100.cash`: `US_INDEX`;
- `JP225.cash|AUS200.cash`: `ASIA_INDEX`;
- `USDJPY`: `FX`;
- `FRA40.cash`: `EU_INDEX`.

The source tape uses one seat per symbol, one seat per cluster, and two global
seats. Daily fill, consecutive-loss, FTMO, and EA risk rails are reapplied by
the account engine after bootstrap; the source scheduler may not pre-remove
trades on those path-dependent gates.

Both phases use dynamic cash risk of `0.300%` for the three existing indices,
`0.050%` for `USDJPY`, and one universal, preselected `0.050%` sleeve for either
new candidate. There is no `0.30%` candidate cell, fixed-lot cell, or risk
sweep. A passing candidate cannot be deployed by editing the whitelist because
the current EA would otherwise assign it `0.30%`; any later implementation
requires a separate default-off versioned risk map and owner approval.

## Timestamp split and lifecycle ownership

Before outcomes, compute the common complete-H1 timestamp interval across the
six involved sources (current four plus both candidates). Let `start` be the
latest first complete H1 open and `end` the earliest last complete H1 close.
Define `cutoff` as the first whole UTC hour at or after
`start + 0.70 * (end - start)`.

A lifecycle belongs to discovery only when its placement and final/cancel
epochs are both before `cutoff`. It belongs to validation only when its
placement epoch is at or after `cutoff`. Straddling lifecycles are excluded and
counted. All cells use the same start, end, and cutoff. Timestamp computation is
outcome-blind and must be reported before expectancy.

## Mandatory implementation and regression gates

Before any outcome is accepted:

1. Data verification must match the exact mandatory line above.
2. The historical default builder must remain 1,645 trades / 7,317 events with
   SHA256 `3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f`.
3. The explicit v1.33-C1 builder must remain 1,684 trades / 7,145 events with
   SHA256 `b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187`.
4. The existing H1-grain A1 builder must remain 662 trades / 2,819 events with
   SHA256 `3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573`.
5. New M15 control construction must reproduce identical event bytes in two
   independent builds. E1 and E2 may differ only in registered cost fields and
   quote buffers.
6. Synthetic fixtures must cover long/short quote-side entry, stop, partial,
   target, same-M15 ambiguity, pending expiry, eighth-H1 time exit, session gap,
   candidate-last contention, cluster contention, and no-candidate order.
7. Current pass-policy, risk-policy, and adapter synthetic self-tests must pass.
8. Every account tape must match Python and C# exactly on path ID 0.
9. Common eligible 20-day bootstrap starts must number at least 20.

Any failure stops the study. It is reported verbatim and is not repaired and
rerun inside the registered cell.

## Stage A: two symbol-discovery cells

For each candidate, build standalone E1 and E2 tapes with the frozen A1 rules.
Report every signal, pending, fill, cancellation, side, quarter, partial, exit,
cost, and exclusion count on discovery and validation.

Each candidate passes only if all gates hold:

1. Discovery has at least 50 fills. Validation has at least 30 fills, including
   at least 10 long and 10 short fills.
2. Pooled discovery expectancy is positive at E1 and E2.
3. Validation expectancy is positive at E1 and E2 pooled, E2 long, and E2
   short.
4. At least two complete validation calendar quarters exist; at least 60% are
   E2-positive and the latest complete quarter is E2-positive. Edge quarters
   are reported but excluded from the completeness fraction.
5. DSR on validation E2 returns is at least `0.95`, using
   `dsr_hurdle(n_trials=305, n_obs=N)` and the repository `psr` function.
6. The validation E2 mean beats a matched C1-opportunity placebo at familywise
   alpha `0.05` across two candidates.

The placebo is frozen as follows. For the same symbol, build the 2.0-ATR/W2
opportunity tape with identical A1 entry, exit, cost, and M15 execution. Draw
exactly 999 without-replacement same-N subsets of its filled validation trades,
matched to the observed A1 count within side x calendar quarter. Seed is
`20260718` plus candidate order index. The observed A1 E2 mean must exceed the
97.5th percentile, and empirical one-sided
`p=(1 + count(placebo_mean >= observed_mean))/1000` must be at most `0.025`.
Insufficient matched population is a failure, never a relaxed match.

A candidate failing any Stage-A gate is killed and receives no account cell.

## Stage B: conditional 20,000-path account screens

Every Stage-A survivor is appended separately to A1. All survivor tapes and
the control use one common discovery-segment eligible-block intersection,
seed `13020260711`, 20-day moving blocks, 500-path chunks, E2 stress, identical
path IDs `0..19999`, two-phase FTMO rules, and common random numbers.

Each survivor passes only if all gates hold:

1. The 97.5%-confidence conservative paired lower bound for candidate-minus-
   control both-phase pass probability is strictly above zero.
2. Exact one-sided McNemar `p <= 0.025`.
3. Candidate one-sided Wilson lower bound for both-phase pass is at least
   `0.88`.
4. Candidate hard-halt probability is at most `0.003700`.
5. The 97.5%-confidence paired upper bound for candidate-minus-control
   hard-halt probability is at most `0.000500`.
6. Candidate timeout and successful median completion days are each no worse
   than paired control.
7. Firm-breach probability is zero.
8. At least 97% of all filled A1 lifecycles are retained, no existing symbol
   retains less than 95%, and total filled lifecycles strictly increase.
9. Minimum-lot substitutions are no greater than paired control.

If both pass, select exactly one by: highest paired lower bound, then lower
timeout, then lower successful median days, then alphabetical FTMO symbol.

## Stage C: one conditional 100,000-path confirmation

Only the selected Stage-B winner may run. No runner-up substitution is allowed.
Use validation-segment A1 and winner tapes, their common eligible 20-day block
intersection, the same seed and E2/risk rules, 500-path chunks, and fresh path
IDs `20000..119999`. All nine Stage-B gates remain binding at the same alpha.

Possible verdicts are:

- `NO_SYMBOL_SURVIVED_DISCOVERY`;
- `NO_SYMBOL_SURVIVED_ACCOUNT_SCREEN`;
- `SYMBOL_CONFIRMATION_REJECTED`; or
- `ONE_SYMBOL_NOMINATED_FOR_DEMO_FORWARD`.

Even the last verdict does not authorize source modification, deployment, or
live trading. Forward demo evidence and a separate owner instruction remain
required.

## README stability interpretation, reporting, and ledger

README's `>=8/12` stability gate is designed for changing strategy logic. This
study does not modify A1; the unit under test is one named symbol. Following the
repository's earlier universe-admission precedent, both-side and calendar-
quarter stability substitute for an across-symbol rule. If that interpretation
is rejected, every outcome remains research-only and no symbol ships.

Report the exact data line; spec/code/data/metadata/tape/result hashes; common
timestamp split; every candidate and placebo; every failure; E1/E2 pooled,
side, and quarter cells; DSR inputs; lifecycle retention; priority/cluster
rejections; quote-buffer sources; all 20k/100k account fields, paired counts,
bounds, p-values, row hashes, path-0 parity, and simulator counters. Every
number is tagged `[MEASURED: command @ commit]`, `[DERIVED]`, or `[HYPOTHESIS]`.

The conservative program-wide starting floor is 300. Charge two discovery
cells; one 20,000-path account cell for each survivor; and one 100,000-path
confirmation only if executed. Maximum charge is `300 -> 305`. All DSR values
prospectively use 305 trials. Regressions, synthetic fixtures, and the 999
declared placebo rows are falsification controls, not additional strategy
cells.

---

**End of pre-registration. No result existed above this line when hashed.**
