# M30-native families, round 2 — pre-registration (2026-07-21)

**Owner directive:** "run round two." Cells pre-declared in round 1's results
(M30_FAMILIES_SPEC, 6ac24154). **Contamination stated up front:** R2a and R2b
are hypotheses formed by inspecting round-1 results on this same data; a
Stage-A pass is therefore discovery-grade only — confirmatory life requires
the Stage-B paired account MC AND forward-demo validation, with this
contamination noted in any promotion claim. R2c is a re-parameterization of a
never-really-tested cell (8 trades) — less contaminated but still same-data.

**Cells (ledger 312 → 315), all SWAP-NET from the start** (measured FTMO
rates: US30 −11.2694, US100 −6.2145, JP225 −8.2192 price/night long; Friday
triple; nights counted per spanned server-day):

- **R2a — overnight momentum-gated, ex-US30:** round-1 C2 mechanization
  verbatim (long at cash close bar open_bin+12 when session net change ≥ 0;
  exit next session's first-bar open) on JP225 + US100 only.
  Gates: swap-net full > 0 AND OOS > 0 AND 2/2 symbols positive.
- **R2b — overnight momentum-gated, Friday-avoided:** C2 on all 3 indices,
  skipping any entry whose spanned nights include the triple-rollover night.
  Gates: swap-net full > 0 AND OOS > 0 AND ≥2/3 symbols.
- **R2c — squeeze at testable density:** compression = 16-bar TR-sum below
  the trailing-720-bar 40th percentile (was 20th) with the 2.0×ATR range cap
  REMOVED (the starving condition); session-gated; entry/exit identical to
  round 1 (stops at 16-bar extremes armed 8 bars, first touch, SL opposite
  boundary capped 1.5×ATR, bank 50% @ +1R, TP +2R, hold 16). Both sides.
  Gates: E2 full > 0 AND OOS > 0 AND ≥3/4 symbols AND n ≥ 200 (density must
  actually be testable this time).

**Informational (no cell charged):** the R2a∩R2b intersection (ex-US30 AND
Friday-avoided) reported as a labeled column for context only.

**Frame:** canonical manifest (verify first), M30 aggregation via the audited
mirror, E2 study currency, OOS = last 30% quarters. All cells reported.

*Results appended below the hash after runs.*

---
## RESULTS (appended post-run 2026-07-21; protocol hashed pre-run: 709a6bdd...)

### Stage A
| cell | n | exp (swap-net where applicable) | OOS | syms+ | verdict |
|---|---|---|---|---|---|
| R2a overnight ex-US30 | 620 | +0.0474 | +0.1640 | 2/2 | **SURVIVE** |
| R2b Friday-avoided | 755 | -0.0306 | +0.0730 | 1/3 | FAIL |
| (info) ex-US30 + Fri-avoided | 507 | -0.0084 | +0.0505 | 1/2 | FAIL (not charged) |
| R2c squeeze @40th | 938 | -0.3217 | -0.2845 | 0/4 | FAIL (family now properly sampled and dead) |

Finding of note: Friday-avoidance HURTS (JP225 flips negative without weekend
holds) - the weekend risk premium out-earns the triple swap. The intuitive
fix was wrong; measurement caught it.

### Stage B (two-book paired MC, R2a sleeve @0.10% + C1-H1 vs C1-H1)
- Kernel engineering (registered here): the account-capacity ceiling was
  raised 2 -> 4 in v130_pass_policy_kernel.cs for two-book replay; PROTECTED
  REGRESSION REPRODUCED EXACTLY post-change (A1 control 20k: 90.9650% /
  0.0400% / 8.9950% / 979d) - the relaxation is inert for single-book tapes.
- Sleeve integration: kept 609 trades, 11 dropped at capacity, swap-net
  +0.0370.
- **SCREEN-20k: FAIL** - common blocks collapsed 389 -> 126 (overnight
  positions destroy flat day-boundaries), and TWO-BOOK both-phases 77.07% vs
  control 90.91% on that frame (paired lower -0.148).
- **Autopsy - the failure is substantially a MODELING artifact:** the kernel's
  day-gates (fillsToday >= 8, consecutiveLosses >= 4, daily halt) are
  ACCOUNT-GLOBAL; the sleeve's fills and losses therefore throttle the H1
  book's entries inside the simulator, which a real two-EA deployment (separate
  magics, separate counters) would not do. Proper two-book evaluation requires
  per-book day-gates in the kernel + new regressions = a separately
  registerable engineering project (IMPROVE-100 precedent wording).
- **Ceiling analysis (decision-relevant):** even if perfectly integrated, the
  sleeve's standalone contribution is ~+0.037R x 0.10% x ~250 trades/yr ~
  +0.9%/yr of account - a <= ~1pp odds ceiling. Engineering cost (kernel
  surgery + v1.34 two-book EA + forward validation) is disproportionate.

### VERDICT
Round 2: R2a is the program's first M30-native TAPE-LEVEL survivor (swap-net,
contamination-labeled). Account-level admission: NOT ESTABLISHED - blocked by
harness architecture, and the honest ceiling is tiny. **DISPOSITION: R2a
PARKED** (documented, revivable if the per-book-gates kernel project is ever
registered). Rounds 1+2 totals: 9 cells + 1 informational, 1 tape survivor,
0 account admissions. Ledger 312 -> 315. The live H1 book remains the only
account-validated book.
