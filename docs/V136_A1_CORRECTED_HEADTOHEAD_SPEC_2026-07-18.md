# v1.36-A1 corrected-fidelity head-to-head specification

Date: 2026-07-18

Status: PRE-REGISTERED BEFORE CORRECTED-FIDELITY EXECUTION. This document
freezes one confirmatory candidate cell. Results may be appended only after
this specification and its SHA256 sidecar are committed. Nothing in this
study authorizes an MT5 write, EA attachment, or deployment.

## Source, provenance, and question

The owner supplied the folder `v1.36-A1`. Its `SHA256SUMS_v136.txt` entries
were independently recomputed before registration and all seven matched.
The decision-relevant supplied artifacts are:

- `MomentumPullbackEA_v136_A1.mq5`, SHA256
  `397ece9d1c8b841bbe3ed763ef2a6d8ddb3cd207f9ea69244d8857f162feef82`;
- `V136_APLUS_EARLY_REPORT.md`, SHA256
  `a9e3ffb846cff049abd628e2394258ff932e37152f1db146f616f985c8055fa1`;
- `v136_aplus_early_results.json`, SHA256
  `ba097f920720a0c9312ea09ca483af4a41850d39c1787b8ecf784c7c34092fbd`.

The supplied screen reports 93.22% pass, 0.015% hard halt, 6.77% timeout,
and a +2.82 percentage-point paired lower bound for A1 versus its C1 control.
Those values came from the supplier's optimistic bar-resolution harness and
are prior context only. They are not decision-grade results and are not used
as the corrected-fidelity control.

The supplied EA differs from the supplied v1.33-C1 EA in executable strategy
logic only by a renamed momentum threshold whose default rises from 2.0 ATR
to 3.0 ATR. Other differences are version, description, panel, and log text.
The supplied v1.33-C1 file differs from the repository's preserved candidate
only in its confirmation-status comment.

The frozen question is:

> Does v1.36-A1 beat the installed v1.33-C1 champion under common-random-number
> corrected-fidelity account simulation while keeping absolute EA hard-halt
> probability at or below 0.3700%?

## Frozen cells

Only these two tapes are permitted:

| Cell | Momentum threshold | Pullback | Partial bank | Trigger | Final target | Trio risk | USDJPY risk |
|---|---:|---:|---:|---:|---:|---:|---:|
| `V133_C1_CONTROL` | 2.0 ATR | 0.6 ATR | 75% | +1.0R | 1.5 ATR | 0.300% | 0.050% |
| `V136_A1` | 3.0 ATR | 0.6 ATR | 75% | +1.0R | 1.5 ATR | 0.300% | 0.050% |

Universe, H1 bar alignment, candle predicate, entry, pending behavior, exit
ordering, costs, symbol/cluster/global seats, account rules, and every other
parameter remain frozen. No 2.5 or 3.5 neighbor, risk change, deeper pullback,
5R target, compression, lead-lag, universe change, or post-result repair may
be tested on this branch.

## Frozen machinery

- Parent evidence commit: `3fe4f258c7a588a2d05c5d15ff947c2b9deded02`.
- Data: repository `backtest/data/MANIFEST.sha256`. Immediately before
  execution, `python backtest/verify_data.py` must print exactly
  `verified 46 OK, 0 missing, 0 mismatched`.
- Tape construction: the audited H1 universe builder and corrected reference
  resolver ordering already used to confirm v1.33-C1: stop first, partial
  second, final target third on ambiguous same bars.
- Threshold implementation: one additive `momentum_atr_mult` builder argument,
  default `2.0`. The default path must preserve the historical tape bytes.
  At `3.0`, it may only suppress signals whose absolute six-bar impulse is
  below 3.0 frozen signal-bar ATR; it may not alter surviving signal geometry.
- Cost model: `E2_STRESS`.
- Account engine: existing Python/C# parity-checked FTMO two-phase simulator.
- Random seed: `13020260711`.
- Moving-block length: 20 days.
- Pairing: common eligible flat-block starts and identical path IDs for both
  cells.
- Chunk size: 500 paths.
- Screen: exactly 20,000 paired paths.
- Confirmation: exactly 100,000 paired paths, executed only after a passing
  screen.

The common eligible-block count will be measured once from the two committed
tapes before path simulation and recorded. It must be positive, identical for
Python and C#, and deterministic on rerun. It is not borrowed from the
supplier's eight-tape screen because that intersection was a different
experiment.

## Mandatory pre-run gates

1. The existing legacy-default tape regression must remain exactly 1,645
   trades, 7,317 events, SHA256
   `3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f`.
2. The new explicit `momentum_atr_mult=2.0` C1 control must reproduce the prior
   C1 tape exactly: 1,684 admitted trades, 7,145 events, event SHA256
   `b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187`.
3. Python/C# path-0 rows must match exactly for both `V133_C1_CONTROL` and
   `V136_A1`.
4. Repository pass-policy and risk-policy synthetic self-tests must pass.
5. The candidate EA must compile in MetaEditor with zero errors and zero
   warnings. Compilation is validation only; the EX5 must not be copied to a
   terminal data folder.

Any failure stops the study and is reported verbatim. It must not be repaired
and rerun inside the registered cell.

## Stage 1: frozen screen

Run exactly 20,000 paired paths. A1 advances only if both gates pass:

1. candidate hard-halt probability is no greater than `0.003700`; and
2. the conservative one-sided paired lower bound for candidate-minus-control
   both-phase pass probability is strictly greater than zero.

The paired lower bound is the existing Bonferroni difference of
Clopper-Pearson marginal bounds used by the corrected head-to-head runner.
Point delta is `(candidate_only_passes - control_only_passes) / N`.

If either gate fails, verdict is `A1_SCREEN_REJECTED`, the 100,000-path stage
is not run, and v1.33-C1 remains the champion.

## Stage 2: frozen confirmation

Only after a passing screen, run exactly 100,000 paired paths using the same
seed, block starts, pairing, costs, and two gates. Both gates must pass.

- Both pass: `A1_CONFIRMED_BEATS_V133_C1`.
- Any failure: `A1_CONFIRMATION_REJECTED`.

No threshold may be relaxed after seeing the screen or confirmation. Even a
passing result does not authorize deployment; owner review and a separate
promotion instruction are required.

## Required reporting

For each executed stage and both cells report paths, phase-1 pass, conditional
phase-2 pass, both-phase pass and Wilson interval, hard halt and Wilson upper,
timeout, firm breach, median and p90 successful completion days, paired
discordant counts, point delta, conservative paired lower bound, exact
one-sided McNemar p-value, tape census, event hashes, row hashes, and every
simulator counter. Report the supplied optimistic values separately from the
corrected-fidelity values and explicitly quantify the time/throughput cost.

Trial ledger charge: one confirmatory candidate cell, zero discovery cells.
The supplier's seven-cell discovery screen and fragility neighbors are prior
research and are not rerun here.
