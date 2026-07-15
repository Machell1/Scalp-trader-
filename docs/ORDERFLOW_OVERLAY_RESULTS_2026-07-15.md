# Order-flow confirmation overlay on v1.31 — Stage A RESULTS (2026-07-15)

**Verdict: STAGE A FAIL. The proposal is closed. v1.31 is not modified.**
Per the pre-registration (`docs/ORDERFLOW_OVERLAY_SPEC_2026-07-15.md`, committed
`25ee1f2` before any outcome join), no re-parameterized variant of this overlay
may be tested without a new pre-registration on data not used here. Stage B
(account MC) does not run.

## Provenance

* `python backtest/verify_data.py` printed `verified 46 OK, 0 missing,
  0 mismatched`. [MEASURED @ `25ee1f2` working tree]
* Engine at origin/main `61f42c9`; geometry parity: the extended trade
  extractor asserted exact `(epoch, R, oos)` equality with the registered
  `run_cell` on every symbol/cost cell (E1 and E2, both symbols) — zero
  mismatches. [MEASURED: assertions in `backtest/run_orderflow_overlay.py`]
* Tick inputs matched the frozen hashes:
  `US100_cash_ticks.parquet` `3ea00484...` and `US30_cash_ticks.parquet`
  `f83d41f2...` re-hashed at run time. [MEASURED]
* Runner convention (declared, within spec): 1-minute bars accumulate from
  09:00 ET (open − 30 min) so the 30-bar avg|delta| baseline is fully seeded by
  the earliest possible 10:00 ET decision.
* Seed 13020260715, 10,000 within-symbol permutations.

## Conditioning

| Symbol | Tape trades | Conditioned (10:00/11:00 ET decisions, covered ticks) | Arm P vetoed | Arm S vetoed |
|---|---:|---:|---:|---:|
| US100.cash | 287 | 29 | 18 | 1 |
| US30.cash | 322 | 54 | 25 | 10 |
| pooled | 609 | 83 | 43 | 11 |

Sample floor (n_conditioned >= 40, n_vetoed >= 10) was met for Arm P: the
verdict is a substantive FAIL, not an insufficient-sample outcome.

## Arm P (primary): session-delta agreement — FAIL

E2 R values, conditioned trades:

| Group | n | mean R |
|---|---:|---:|
| all conditioned (control) | 83 | +0.192 |
| confirmed (overlay keeps) | 40 | +0.166 |
| vetoed (overlay removes) | 43 | **+0.217** |

Gap (confirmed − vetoed) = **−0.051**, permutation p = **0.4735**.

Gate evaluation [MEASURED: `backtest/orderflow_overlay_results.json`]:

1. Power floor: met (83 / 43).
2. `meanR(vetoed) < 0`: **FAIL** — the trades the order-flow gate would have
   blocked were the *better* trades (+0.217 vs +0.166).
3. Permutation p <= 0.05: **FAIL** (0.47 — indistinguishable from a random
   coin-flag).
4. Overlay above control: **FAIL** (+0.166 < +0.192).

The confirmation layer would have vetoed ~52% of the NY-morning book and made
the book *worse* — the same direction as the standalone order-flow backtest
(timing at the 5th percentile vs random on US500) and the removed M5/M15
monitor. Three independent experiments now agree.

## Arm S (secondary): opposing-aggression veto — non-signal

| Group | n | mean R |
|---|---:|---:|
| confirmed | 72 | +0.241 |
| vetoed | 11 | −0.128 |

Gap +0.369 but permutation p = **0.2512** on 11 vetoes — noise. Under the
fixed multiplicity rule Arm S cannot admit anything; with p = 0.25 it does not
justify even a follow-up pre-registration. Recorded and closed.

## Context notes

* The conditioned slice itself (v1.31's 10:00/11:00 ET entries) carries +0.192
  E2 expectancy on 83 trades — the morning book is healthy without any overlay.
* Artifact: `backtest/orderflow_overlay_results.json` (full per-trade join,
  states, and arm tables).
* Deployed v1.31 on FTMO trial: untouched throughout; this study was
  research-only and wrote nothing to any terminal.
