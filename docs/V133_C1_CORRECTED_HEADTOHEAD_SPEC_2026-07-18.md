# v1.33-C1 corrected-fidelity head-to-head specification

Date: 2026-07-18

Status: PRE-REGISTERED BEFORE CORRECTED-FIDELITY EXECUTION. This document freezes
one decision-grade cell. Results must be appended only after the specification and
its SHA256 have been committed. Nothing in this study authorizes an MT5 write or a
deployment.

## Source and question

The owner supplied the text titled `1.33-C1 Candidate Spec — Reset of the Failed E3
Challenger (2026-07-18)`, attachment SHA256
`11c43f24c6597f5824391914e8b29dd5d59645dab01f3aac60d5ea5e2b8ce1ea`.

That document reports an optimistic-generation grid and explicitly requires C1 to
be tested on the corrected-fidelity head-to-head harness before it may be called
validated. The frozen question is:

> Does C1 beat v1.31 under common-random-number corrected-fidelity account
> simulation while keeping absolute EA hard-halt probability at or below 0.3700%?

The optimistic result (C1 88.850% both-phase pass and 0/20,000 hard halts) is prior
context only. It is not a decision-grade result and is not used as a control.

## Frozen cells

Only these two tapes are permitted:

| Cell | Partial bank | Trigger | Final target | Trio risk | USDJPY risk |
|---|---:|---:|---:|---:|---:|
| `V131_CONTROL` | 50% | +1.0R | 2.0 ATR | 0.300% | 0.050% |
| `V133_C1` | 75% | +1.0R | 1.5 ATR | 0.300% | 0.050% |

Universe, H1 signals, entries, pending behavior, costs, symbol/cluster/global seats,
account rules, and every other strategy parameter remain frozen. No C2, C3, C4,
risk adjustment, trigger adjustment, or post-result repair may be tested on this
branch.

## Frozen machinery

- Parent evidence commit: `9a938225ffef569729d36dd6a0b32e32e0f34170`.
- Data: repository `backtest/data/MANIFEST.sha256`; immediately before execution,
  `python backtest/verify_data.py` must print exactly
  `verified 46 OK, 0 missing, 0 mismatched`.
- Tape construction: audited H1 universe builder with the corrected reference
  resolver ordering used by `backtest/retest_engine.py::resolve`: stop first,
  partial second, final target third on ambiguous same bars.
- Cost model: `E2_STRESS`.
- Account engine: existing Python/C# parity-checked FTMO two-phase simulator.
- Random seed: `13020260711`.
- Moving-block length: 20 days.
- Pairing: common eligible flat-block starts and identical path IDs for both cells.
- Expected common-block count: 373; a different count is a discrepancy and stops
  the run.
- Chunk size: 500 paths.

## Mandatory pre-run gates

1. The legacy-default tape regression must remain exactly 1,645 trades, 7,317
   events, SHA256
   `3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f`.
2. Python/C# path-0 rows must match exactly for both `V131_CONTROL` and `V133_C1`.
3. The repository pass-policy and risk-policy synthetic self-tests must pass.

Any failure stops the study and is reported verbatim. It must not be repaired and
rerun inside this registered cell.

## Stage 1: frozen screen

Run exactly 20,000 paired paths. C1 advances only if both gates pass:

1. candidate hard-halt probability is no greater than `0.003700`; and
2. the conservative one-sided paired lower bound for candidate-minus-control
   both-phase pass probability is strictly greater than zero.

The paired lower bound is the existing Bonferroni difference of Clopper-Pearson
marginal bounds used by the corrected head-to-head runner. Point delta is
`(candidate_only_passes - control_only_passes) / N`.

If either gate fails, verdict is `C1_SCREEN_REJECTED`, the 100,000-path stage is not
run, and v1.31 remains unchanged.

## Stage 2: frozen confirmation

Only after a passing screen, run exactly 100,000 paired paths using the same seed,
block starts, pairing, costs, and two gates. Both confirmation gates must pass.

- Both pass: `C1_CONFIRMED_BEATS_V131`.
- Any failure: `C1_CONFIRMATION_REJECTED`.

No threshold may be relaxed after seeing the screen or confirmation.

## Required reporting

For each executed stage and both cells report paths, phase-1 pass, conditional
phase-2 pass, both-phase pass and Wilson interval, hard halt and Wilson upper,
timeout, firm breach, median and p90 successful completion days, paired discordant
counts, point delta, conservative paired lower bound, exact one-sided McNemar
p-value, tape census, event hashes, row hashes, and every simulator counter.

The claimed `MomentumPullbackEA_v133_C1.mq5`, optimistic grid runner, and optimistic
JSON were not present in the supplied workspace or GitHub remote at registration.
This study therefore validates or rejects the frozen C1 geometry in the audited
harness; it does not validate an absent EA implementation.

Trial ledger charge for this corrected study: one confirmatory candidate cell, zero
discovery cells. The four optimistic grid cells are part of the supplied prior
research record and are not rerun here.
