# v1.33-C1 Candidate Spec — Reset of the Failed E3 Challenger (2026-07-18)

**Status: PRE-SCREENED CANDIDATE — NOT VALIDATED.** Decision-grade confirmation must
run on the owner's corrected-fidelity head-to-head harness. Owner sign-off required
before any deployment. Do not label validated.

## 1. Why a reset

The E3 challenger (bank 67% @ +1R, TP 1.5 ATR, v1.32 EA framework) won its head-to-head
vs v1.31 on the owner's corrected harness (20,000 paired paths @ `042dfe4`):
pass 86.660% vs 76.750% (**+9.91pp**, paired LB +8.94pp), hard-halt 0.435% vs 4.055%,
timeout 12.905% vs 19.195%, median 595.5d vs 772d — but **failed the absolute
hard-halt gate ≤ 0.370% by 0.065pp**, so the 100k confirmation was correctly refused.

The owner authorized a reset of the failed strategy. This document pre-registers the
reset grid and reports every cell (no cherry-picking). Ledger charge: 4 candidate cells.

## 2. Pre-registered grid (declared before any run)

House-standard machinery: seed `13020260711`, 20-day blocks, E2_STRESS, exact
Python/C# path-0 parity gate per tape (all passed), 20,000 CRN-paired paths per cell,
373 common flat-block starts (intersection across all grid tapes), gate-grade data
`verified 46 OK`. All cells share the v1.31 portfolio (trio + USDJPY 0.05%) and entry
engine; only exit geometry / risk varies.

| Cell | bank @ trigger | TP | trio risk | change vs E3 |
|---|---|---|---|---|
| V131 (control) | 50% @ +1.0R | 2.0 ATR | 0.300% | — (incumbent) |
| E3 (reference) | 67% @ +1.0R | 1.5 ATR | 0.300% | — (failed challenger) |
| **C1** | **75% @ +1.0R** | **1.5 ATR** | **0.300%** | bank more (1 param) |
| C2 | 67% @ +0.8R | 1.5 ATR | 0.300% | bank earlier |
| C3 | 67% @ +1.0R | 1.5 ATR | 0.275% | risk trim only |
| C4 | 75% @ +0.9R | 1.5 ATR | 0.300% | combo |

Pre-declared gates: G1 hard ≤ 0.370% · G2 paired pass-LB vs V131 > 0 · G3 hard < E3 ·
G4 timeout ≤ V131.

## 3. Results — ALL cells (repo harness, optimistic bar-resolution generation)

| Cell | pass (both) | hard-halt | timeout | median days | paired Δ vs V131 (LB) | gates |
|---|---:|---:|---:|---:|---:|---|
| V131 | 80.370% | 0.835% (167/20k) | 18.795% | 562 | — | control |
| E3 | 88.015% | 0.010% (2/20k) | 11.975% | 398 | +8.48pp (**+6.71pp**) | G3 n/a |
| **C1** | **88.850%** | **0.000% (0/20k)** | **11.150%** | 374 | +8.48pp (**+7.55pp**) | **ALL PASS** |
| C2 | 82.085% | 0.000% (0/20k) | 17.915% | 337 | +1.72pp (+0.72pp) | PASS |
| C3 | 87.815% | 0.000% (0/20k) | 12.185% | 434 | +7.45pp (+6.51pp) | PASS |
| C4 | 88.710% | 0.000% (0/20k) | 11.290% | 338 | +8.34pp (+7.41pp) | PASS |

Paired head-to-heads vs E3 (exact, shared path IDs):
- **C1 vs E3: +0.835pp (LB −0.006pp) → statistical TIE on pass**; C1 strictly better on
  halts (0 vs 2 events), timeout (2230 vs 2395), median days (374 vs 398).
- C4 ≈ C1 (tie); C2 weakest pass; C3 ≈ E3 pass with zero halts (geometry-untouched fallback).
- Replication check: E3 printed 88.015% here vs 87.965% on the owner's earlier
  optimistic-generation run (Δ0.05pp) — pipeline reproduces the reference machinery.

## 4. Candidate selection

**Primary: C1** — `bank 75% @ +1R, TP 1.5 ATR, risk unchanged`. One-parameter move from
E3; ties E3's pass rate and dominates it on every safety metric; the biggest paired
lower bound vs v1.31 in the grid (+7.55pp).
**Fallback: C3** — E3 geometry untouched, trio risk 0.30%→0.275%; zero halts, if the
owner prefers no exit-geometry change at all.
Rejected: C2 (gives back most of the pass gain), C4 (two-parameter, no gain over C1).

## 5. Mandatory confirmation protocol (decision-grade)

Run C1 (optionally C3 alongside) on the owner's **corrected-fidelity** head-to-head
harness, same pairing discipline as the E3 run:
1. **Screen**: 20,000 paired paths vs v1.31. **Promote only if BOTH**: hard-halt ≤
   0.370% AND paired pass-LB vs v1.31 > 0.
2. **Confirmation**: 100,000 paired paths on the screen winner, same two gates.
3. Only then flip the live default (v1.33 EA already encodes it via renamed inputs) —
   owner sign-off, deploy on flat account, journal everything.

**Recorded caveat on halt-transfer:** this harness under-measures halts vs the corrected
one (E3: 0.010% here → 0.435% corrected). C1's 0/20k here is the strongest measurable
signal (Wilson 95% upper ≈ 0.015%) but does NOT guarantee the corrected gate; that is
what the confirmation is for. Pass-rate optimism here is ~+1.3–3.6pp geometry-dependent.

## 6. Exact EA settings (no code change needed on v1.32; v1.33 file pre-packages them)

| Setting | v1.31 | E3 (failed) | **C1 (candidate)** |
|---|---|---|---|
| `InpPartialCloseFractionV130` (`V133` on the v1.33 file) | 0.50 | 0.67 | **0.75** |
| `InpTakeProfitAtrMultV130` (`V133`) | 2.0 | 1.5 | **1.5** |
| Partial trigger `InpPartialCloseAtRV130` | 1.0 | 1.0 | 1.0 |
| Risk (trio / USDJPY) | 0.30% / 0.05% | same | same |
| Everything else | frozen | frozen | frozen |

`MomentumPullbackEA_v133_C1.mq5` ships these behind renamed inputs (house convention:
chart-saved V130 values cannot survive) + a CANDIDATE banner. It is otherwise
byte-identical to reviewed v1.32 (fidelity fixes A1–A9 ON; research arms B1–B3 OFF).
Partial-volume rounding (floor-to-step, min-volume skip) handles 0.75 with no code change.

## 7. Provenance

Grid script `backtest/run_v133_geometry_grid.py` (pre-registered docstring), results
`backtest/v133_geometry_grid_results.json`, chunk checkpoints `backtest/v133_chunks/`
(in the analysis workspace; reproducible end-to-end from repo main + LFS data).
C# kernel built unmodified from `v130_pass_policy_kernel.cs` (net8.0); path-0 parity
exact per tape. Note: the repo-harness JSON mislabels two paired fields
(`estimate`=p10_lower, `p_value`=p01_upper of the Bonferroni CP bound) — cosmetic;
all conclusions above use (n10−n01)/N point deltas and the exact lower bound.
