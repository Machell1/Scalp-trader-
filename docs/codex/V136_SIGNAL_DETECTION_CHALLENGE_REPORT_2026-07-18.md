# v1.36-A1 signal-detection challenge report

Date: 2026-07-18

Status: **COMPLETE — NO SURVIVOR. RESEARCH ONLY.**

## Decision

`SIGNAL_SURFACE_EXHAUSTED_NO_SURVIVOR`

[MEASURED: `python backtest/run_v136_signal_detection.py` @
`22402ef3af92099e7ef58c3ca04f8532348a8718`] None of the three frozen
Kimi-sourced signal-detection ideas passed discovery. Consequently, none was
eligible for the 20,000-path account screen or fresh 100,000-path
confirmation. v1.36-A1 remains the corrected-fidelity research champion.
There is no EA change, compile, MT5 write, attachment, or deployment from this
study.

R_DRIVE was the closest failed cell: [MEASURED: registered discovery @
`22402ef`] its full stitched-OOS expectancy was `+0.194239R`, versus
`+0.183646R` for A1, and its win rate was `64.7541%`, versus `62.5000%` for
A1. [DERIVED from the same rows] Those deltas are `+0.010593R` and
`+2.2541pp`. They are not decision-grade improvements: R_DRIVE's selected
marginal arm was worse than `139/200` matched random arms, empirical
one-sided `p=0.696518`, and its full-tape DSR was only `0.628450` against the
frozen `0.95` gate. The apparent uplift is therefore disposed of rather than
promoted.

## Provenance and execution gates

All values in this table are [MEASURED: registered runner @ `22402ef`].

| Item | Result |
|---|---:|
| Pre-run spec SHA256 | `c7113dabe1ace5fa28e243781beb942c4d7682767662165fab9ebe337d2c4fd6` |
| Clean experiment-bundle SHA256 | `522bf6ba94450381fd556c9fabd68edf9b8efe7958e83b0d08efef8557b0f461` |
| Canonical tracked blobs in bundle | 20 |
| Data verification | `verified 46 OK, 0 missing, 0 mismatched` |
| Pass-policy synthetic checks | 10 passed |
| Risk-policy synthetic checks | 16 passed |
| R_STRUCT causal signal closes checked | 4,984 |
| R_DRIVE causal signal closes checked | 4,984 |
| Exact four-M15 timestamp assertions | 4,984 |
| Missing allowed M15 constituents | 0 |
| Next-hour M15 access | false |
| Discovery trial charge | 3 cells |
| Conditional confirmation charge | 0 cells |

The protected tape regressions are [MEASURED: pre-candidate gates @
`22402ef`].

| Tape | Accepted lifecycles | Events | Event SHA256 | Decision |
|---|---:|---:|---|---|
| Legacy default | 1,645 | 7,317 | `3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f` | PASS |
| v1.33-C1 | 1,684 | 7,145 | `b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187` | PASS |
| v1.36-A1 uncached | 662 | 2,819 | `3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573` | PASS |
| v1.36-A1 cached | 662 | 2,819 | `3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573` | PASS |

## Pooled stitched-OOS result

All cells below are [MEASURED: registered discovery @ `22402ef`]. Deltas are
[DERIVED from the displayed candidate and paired A1 rows]. The DSR hurdle was
computed with the frozen program-wide trial count of 300.

| Cell | OOS fills | Expectancy | Delta vs A1 | Win rate | Delta vs A1 | DSR | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| A1 control | 120 | +0.183646R | — | 62.5000% | — | 0.227012 | context |
| R_STRUCT | 243 | +0.177052R | -0.006594R | 63.7860% | +1.2860pp | 0.516819 | FAIL |
| S_ZSEAT | 119 | +0.173715R | -0.009931R | 62.1849% | -0.3151pp | 0.192638 | FAIL |
| R_DRIVE | 244 | +0.194239R | +0.010593R | 64.7541% | +2.2541pp | 0.628450 | FAIL |

[MEASURED: registered discovery @ `22402ef`] A1 itself has DSR `0.227012`
under the deliberately conservative 300-trial program-wide hurdle. That does
not revoke A1's prior corrected account-MC result; it means none of these
discovery comparisons may use inherited A1 trades to claim fresh statistical
validation.

## Falsification results

All values below are [MEASURED: 200 declared placebos per cell @ `22402ef`].
Every individual placebo mask/seed, tape SHA256, OOS result, and all 600
placebo rows are retained in `backtest/v136_signal_detection_results.json`.

| Cell | Observed statistic | Matched placebo p95 | Placebos >= observed | Empirical p | Negative control | Retention admitted / filled | Breadth symbols / quarters | Failed gates |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| R_STRUCT | arm +0.205566R, n=152 | +0.259091R | 84/200 | 0.422886 | inside-channel +0.154268R, n=60 | 75.3776% / 75.6962% | 1/4 / 1/3 | DSR; placebo-95; Bonferroni p; symbol breadth; quarter breadth |
| S_ZSEAT | full +0.173715R, n=119 | +0.195772R | 127/200 | 0.636816 | ascending-z +0.182839R | 95.9215% / 96.2025% | 3/4 / 3/3 | DSR; placebo-95; Bonferroni p; negative control; filled retention |
| R_DRIVE | arm +0.216866R, n=148 | +0.314898R | 139/200 | 0.696517 | back-half +0.188022R, n=75 | 77.4924% / 79.4937% | 3/4 / 2/3 | DSR; placebo-95; Bonferroni p |

The frozen significance threshold was [MEASURED: spec @ `22402ef`]
`p <= 0.0166666667`; every observed p-value is far above it. The placebos were
all finite: [MEASURED: result JSON @ `22402ef`] 200/200 for each cell, with
zero unavailable rows.

## Symbol and complete-quarter breadth

Every row is [MEASURED: stitched OOS @ `22402ef`]. `Delta` is [DERIVED] from
the paired candidate and A1 expectancy shown in the result JSON.

| Cell | Symbol | A1 n | A1 expectancy | Candidate n | Candidate expectancy | Delta |
|---|---|---:|---:|---:|---:|---:|
| R_STRUCT | JP225.cash | 32 | +0.192874R | 64 | +0.144969R | -0.047905R |
| R_STRUCT | US100.cash | 11 | +0.013648R | 30 | +0.224702R | +0.211054R |
| R_STRUCT | US30.cash | 47 | +0.174471R | 91 | +0.154341R | -0.020130R |
| R_STRUCT | USDJPY | 30 | +0.250509R | 58 | +0.223438R | -0.027071R |
| S_ZSEAT | JP225.cash | 32 | +0.192874R | 32 | +0.192874R | +0.000000R |
| S_ZSEAT | US100.cash | 11 | +0.013648R | 14 | +0.201766R | +0.188118R |
| S_ZSEAT | US30.cash | 47 | +0.174471R | 43 | +0.096748R | -0.077723R |
| S_ZSEAT | USDJPY | 30 | +0.250509R | 30 | +0.250509R | +0.000000R |
| R_DRIVE | JP225.cash | 32 | +0.192874R | 78 | +0.194596R | +0.001723R |
| R_DRIVE | US100.cash | 11 | +0.013648R | 32 | +0.235642R | +0.221994R |
| R_DRIVE | US30.cash | 47 | +0.174471R | 73 | +0.184136R | +0.009665R |
| R_DRIVE | USDJPY | 30 | +0.250509R | 61 | +0.184153R | -0.066356R |

Complete-quarter slices are classified separately per symbol. All values are
[MEASURED: registered quarter policy @ `22402ef`].

| Cell | Complete quarter | A1 n | A1 expectancy | Candidate n | Candidate expectancy | Delta |
|---|---|---:|---:|---:|---:|---:|
| R_STRUCT | 2025Q4 | 7 | +0.347027R | 16 | +0.141060R | -0.205967R |
| R_STRUCT | 2026Q1 | 37 | +0.199934R | 83 | +0.139842R | -0.060092R |
| R_STRUCT | 2026Q2 | 26 | +0.069261R | 60 | +0.260539R | +0.191277R |
| S_ZSEAT | 2025Q4 | 7 | +0.347027R | 7 | +0.347027R | +0.000000R |
| S_ZSEAT | 2026Q1 | 37 | +0.199934R | 37 | +0.199971R | +0.000037R |
| S_ZSEAT | 2026Q2 | 26 | +0.069261R | 26 | +0.069261R | +0.000000R |
| R_DRIVE | 2025Q4 | 7 | +0.347027R | 16 | +0.029451R | -0.317576R |
| R_DRIVE | 2026Q1 | 37 | +0.199934R | 87 | +0.260214R | +0.060279R |
| R_DRIVE | 2026Q2 | 26 | +0.069261R | 58 | +0.301900R | +0.232638R |

[MEASURED: quarter policy @ `22402ef`] The result JSON also reports every
excluded edge-partial symbol-quarter for A1 and all candidates. The complete
slices were index symbols in 2026Q1/2026Q2 and USDJPY in 2025Q4/2026Q1; eight
edge-partial symbol-quarter slices were excluded from the 60% gate exactly as
pre-registered.

## Lifecycle census

All values below are [MEASURED: full E2-stress tapes @ `22402ef`]. `Raw` is
the audited base directional signal count; `A1W2` and `MargW2` are W2-qualified
raw cohorts; `Feat` is feature-positive marginal; `Pred` is predicate-admitted;
`Local` is after symbol pending occupancy; `Accepted` is after portfolio seats.

| Cell | Raw | A1W2 | MargW2 | Feat | Pred | Local | Accepted | Filled | Canceled | Events | Tape SHA256 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A1 | 7,669 | 1,041 | 1,806 | 0 | 1,041 | 757 | 662 | 395 | 267 | 2,819 | `3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573` |
| R_STRUCT | 7,669 | 1,041 | 1,806 | 1,321 | 2,362 | 1,688 | 1,428 | 846 | 582 | 6,057 | `2647b033a44fb5ffa0c7a9c0b1afd990a18339e6052c22385d2dade3150b2149` |
| S_ZSEAT | 7,669 | 1,041 | 1,806 | 0 | 1,041 | 757 | 662 | 395 | 267 | 2,812 | `7c7551019a4010db5caf5b967b7ba57c3f5b27f8d0e98d742d7a2d2212e8a5d4` |
| R_DRIVE | 7,669 | 1,041 | 1,806 | 1,166 | 2,207 | 1,618 | 1,380 | 804 | 576 | 5,963 | `8fc210907c06d05fc0ddb6312114488d177c0b7ba12573f6a0474c15e99034de` |

The by-symbol/side census is [MEASURED: result JSON @ `22402ef`]. This table
records the decision-critical admitted/fill layers; the JSON additionally
retains raw, A1W2, MargW2, feature, local-fill, and event counts for every row.

| Cell | Symbol | Side | Predicate admitted | Local | Portfolio accepted | Filled | Canceled | Events |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A1 | JP225.cash | short | 126 | 98 | 95 | 64 | 31 | 454 |
| A1 | JP225.cash | long | 81 | 66 | 65 | 32 | 33 | 260 |
| A1 | US100.cash | short | 169 | 117 | 71 | 44 | 27 | 279 |
| A1 | US100.cash | long | 94 | 68 | 47 | 19 | 28 | 165 |
| A1 | US30.cash | short | 151 | 109 | 102 | 74 | 28 | 457 |
| A1 | US30.cash | long | 158 | 114 | 106 | 61 | 45 | 453 |
| A1 | USDJPY | short | 168 | 117 | 112 | 68 | 44 | 487 |
| A1 | USDJPY | long | 94 | 68 | 64 | 33 | 31 | 264 |
| R_STRUCT | JP225.cash | short | 275 | 199 | 184 | 108 | 76 | 829 |
| R_STRUCT | JP225.cash | long | 215 | 167 | 164 | 88 | 76 | 708 |
| R_STRUCT | US100.cash | short | 331 | 230 | 130 | 80 | 50 | 532 |
| R_STRUCT | US100.cash | long | 232 | 170 | 114 | 59 | 55 | 410 |
| R_STRUCT | US30.cash | short | 323 | 221 | 194 | 143 | 51 | 888 |
| R_STRUCT | US30.cash | long | 305 | 225 | 202 | 117 | 85 | 793 |
| R_STRUCT | USDJPY | short | 398 | 263 | 239 | 137 | 102 | 1,000 |
| R_STRUCT | USDJPY | long | 283 | 213 | 201 | 114 | 87 | 897 |
| S_ZSEAT | JP225.cash | short | 126 | 98 | 94 | 64 | 30 | 452 |
| S_ZSEAT | JP225.cash | long | 81 | 66 | 65 | 32 | 33 | 260 |
| S_ZSEAT | US100.cash | short | 169 | 117 | 83 | 52 | 31 | 324 |
| S_ZSEAT | US100.cash | long | 94 | 68 | 55 | 22 | 33 | 205 |
| S_ZSEAT | US30.cash | short | 151 | 109 | 87 | 64 | 23 | 387 |
| S_ZSEAT | US30.cash | long | 158 | 114 | 98 | 58 | 40 | 419 |
| S_ZSEAT | USDJPY | short | 168 | 117 | 115 | 70 | 45 | 499 |
| S_ZSEAT | USDJPY | long | 94 | 68 | 65 | 33 | 32 | 266 |
| R_DRIVE | JP225.cash | short | 280 | 202 | 191 | 112 | 79 | 852 |
| R_DRIVE | JP225.cash | long | 214 | 172 | 168 | 90 | 78 | 728 |
| R_DRIVE | US100.cash | short | 299 | 213 | 120 | 73 | 47 | 490 |
| R_DRIVE | US100.cash | long | 205 | 161 | 100 | 48 | 52 | 393 |
| R_DRIVE | US30.cash | short | 299 | 209 | 187 | 121 | 66 | 825 |
| R_DRIVE | US30.cash | long | 265 | 195 | 181 | 110 | 71 | 780 |
| R_DRIVE | USDJPY | short | 374 | 263 | 240 | 148 | 92 | 1,045 |
| R_DRIVE | USDJPY | long | 271 | 203 | 193 | 102 | 91 | 850 |

## A1 lifecycle retention

Counts are [MEASURED: candidate vs paired A1 lifecycle IDs @ `22402ef`].

| Symbol | Side | R_STRUCT admitted / filled | S_ZSEAT admitted / filled | R_DRIVE admitted / filled |
|---|---:|---:|---:|---:|
| JP225.cash | short | 71/95 / 45/64 | 93/95 / 63/64 | 73/95 / 51/64 |
| JP225.cash | long | 55/65 / 28/32 | 65/65 / 32/32 | 53/65 / 28/32 |
| US100.cash | short | 50/71 / 29/44 | 69/71 / 43/44 | 51/71 / 31/44 |
| US100.cash | long | 35/47 / 14/19 | 47/47 / 19/19 | 32/47 / 13/19 |
| US30.cash | short | 76/102 / 62/74 | 87/102 / 64/74 | 78/102 / 63/74 |
| US30.cash | long | 80/106 / 49/61 | 98/106 / 58/61 | 90/106 / 54/61 |
| USDJPY | short | 83/112 / 46/68 | 112/112 / 68/68 | 85/112 / 48/68 |
| USDJPY | long | 49/64 / 26/33 | 64/64 / 33/33 | 51/64 / 26/33 |

## Account-stage decision and conclusion

[MEASURED: registered gate flow @ `22402ef`] `account_screen=null` and
`account_confirmation=null`. The account trial charge is therefore zero. No
candidate has a corrected FTMO pass probability, and it would be false to
compare any of these discovery rows to A1's prior `90.9940%` corrected
100,000-path pass estimate as though an account challenge had run.

[DERIVED from the complete registered evidence] The actionable decision is to
keep v1.36-A1 unchanged, dispose of R_STRUCT, S_ZSEAT, and R_DRIVE, and avoid
mining threshold neighbors or combinations from their failures. R_DRIVE did
recover opportunity count, but its feature did not select marginal trades
better than matched random masks. More trade frequency alone did not produce
a validated entry-quality edge.

## Immutable artifacts

- [MEASURED: result file @ `22402ef`]
  `backtest/v136_signal_detection_results.json`, SHA256
  `5bbc82165732656f0b1bb97bfbaa63d9e411153a4b5b1e4de6209938f4d777bb`.
- [MEASURED: sidecar @ `22402ef`]
  `backtest/v136_signal_detection_results.sha256` matches the result bytes.
- [MEASURED: runtime @ `22402ef`] No
  `backtest/v136_signal_detection_failures.jsonl` was created.
- [MEASURED: Git/terminal audit @ `22402ef`] No MQL5 source or EX5 was changed,
  no MT5 terminal was written, and no live/demo account state was touched.
