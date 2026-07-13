# v1.30 FTMO pass-policy bootstrap repair — pre-registration

**Date:** 2026-07-12 UTC

**Branch:** `codex/v130-ftmo-pass-policy`

**Original protocol:**
`docs/V130_FTMO_PASS_POLICY_SPEC_2026-07-12.md`

**Original protocol SHA256:**
`0bccf0057f65b30e70a3b70663476ecadf6348efaee5aa366f3e235a3dfad671`

## Purpose and scope

The original registered development command passed both weighted E1/E2 edge
gates, then failed before completing its first MC path with
`BootstrapOverlapError: non-flat lifecycle at sampled block boundary`. The
failure and traceback are recorded below the original protocol hash and in
commit `2e52cad`.

This repair changes only the flat-boundary invariant. A lifecycle whose final
event occurs exactly at the next Europe/Prague midnight is ineligible as a
moving-block boundary because the replay cursor schedules that final event on
the following calendar day. The repaired predicate is:

`placement_epoch < boundary_epoch <= final_epoch` means occupied.

The original strict `< final_epoch` test was inconsistent with the replay
calendar convention. The adapter, policy tape, and cached block compiler must
use this same predicate. A synthetic equality-boundary test is mandatory.

No signal, symbol, risk percentage, cost column, seed, block length, account
rule, gate, frame, path count, or inference method changes. The original edge
results are not rerun under the old hash; the repair run must reproduce their
source event and diagnostic hashes before any MC path. Confirmation and
holdout remain unopened.

## Exact unchanged outcome protocol

The repair command is:

`python backtest/run_v130_pass_policy.py --development`

It must use:

- development/mined data only;
- E1 and E2 only, with source hashes from the committed cost-audit result;
- C0, C1, and P1 exactly as in the original protocol;
- 100,000 paths, seed `13020260711`, 20-day flat moving blocks;
- sequential Phase 1 then Phase 2 on the same path stream;
- the same FTMO and v1.30 rails, timed swaps, current-balance lot sizing,
  pending-aware passage, and Wilson/paired gates;
- no CLI bypass for confirmation or holdout.

The repair consumes the already charged C1/P1 development cells. It adds no
new hypothesis and does not increase the trial ledger beyond `209 -> 211`.
The prior failed command remains a required result, not a discarded run.

## Repair tests before data access

In addition to every original pre-outcome test, the repair must prove:

1. a lifecycle ending exactly at a Prague midnight is rejected as a block
   boundary;
2. a lifecycle ending strictly before the boundary remains eligible;
3. adapter and policy-tape eligible block starts are byte-identical;
4. a seeded bootstrap never raises a boundary overlap for the repaired tape;
5. all source event/diagnostic hashes and default-off regression outputs remain
   unchanged.

Any failed test or source hash stops the repair before MC. The exact output is
reported verbatim and no further repair is silently attempted under this hash.

## Results

Not run at registration. Results may be appended here only; this protocol and
its repair convention are immutable above the recorded hash.

---
**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `486bc9ae857332f29dbe1bb434399d3baeaaa0e3938f6e338ddb22bab05bc4`

---
