# v1.36-A1 corrected-fidelity head-to-head report

Date: 2026-07-18

Verdict: **A1_CONFIRMED_BEATS_V133_C1**.

This is a research verdict, not deployment authorization. No MT5 terminal was
written, restarted, or reconfigured during this study.

## Provenance and frozen protocol

[MEASURED: SHA256 verification of the supplied `v1.36-A1` folder @ `d517a26`]
All seven entries in `SHA256SUMS_v136.txt` matched. The supplied candidate EA
SHA256 was
`397ece9d1c8b841bbe3ed763ef2a6d8ddb3cd207f9ea69244d8857f162feef82`.
The EA's only executable strategy change from its supplied v1.33-C1 base was
the momentum threshold rename/default change from 2.0 ATR to 3.0 ATR; the
remaining differences were comments, version, description, panel, and log
text.

[MEASURED: `Get-FileHash` @ `d517a26`] The pre-run specification SHA256 was
`2cea62afeb05e1fcbe38500c393c28db408f7b3c9e1e43561609591bae3aace1`.
It was committed before the additive harness implementation and before any
new tape or Monte Carlo execution.

[MEASURED: package report @ `d517a26`] The supplied optimistic screen claimed
93.22% pass, 0.015% hard halt, 6.77% timeout, and a +2.82 percentage-point
paired lower bound. These values are kept separate from the corrected results
below.

## Pre-run fidelity gates

[MEASURED: `python backtest/verify_data.py` @ `e3461c2`] Output verbatim:
`verified 46 OK, 0 missing, 0 mismatched`.

[MEASURED: pass/risk policy synthetic tests @ `e3461c2`] All 10 pass-policy
tests and all 16 risk-policy tests passed.

[MEASURED: legacy regression @ `e3461c2`] The default builder reproduced
1,645 trades, 7,317 events, and event SHA256
`3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f`
exactly.

[MEASURED: C1 control regression @ `e3461c2`] The explicit 2.0-ATR control
reproduced 1,684 admitted trades, 7,145 events, and event SHA256
`b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187`
exactly.

[MEASURED: Python/C# path-0 comparison @ `e3461c2`] Both the C1 control and A1
candidate matched exactly. There were 389 common eligible flat blocks.

[MEASURED: MetaEditor compile @ `e3461c2`] The exact supplied candidate source
compiled with `Result: 0 errors, 0 warnings, 13283 ms elapsed,
cpu='X64 Regular'`. The resulting EX5 was not copied into any terminal data
folder.

## Tape census

[MEASURED: `backtest/v136_a1_headtohead_results.json` @ `e3461c2`]

| Measure | v1.33-C1 control | v1.36-A1 | Delta/retention |
|---|---:|---:|---:|
| Admitted trades | 1,684 | 662 | 39.31% retained |
| Filled entries/finals | 987 | 395 | 40.02% retained |
| Partial events | 558 | 231 | 41.40% retained |
| Pending cancels | 697 | 267 | 38.31% retained |
| Mark events | 2,232 | 869 | 38.93% retained |
| Total events | 7,145 | 2,819 | 39.45% retained |
| Same-bar partial/final | 218 | 93 | 42.66% retained |
| Calendar days in source tape | 1,032 | 1,032 | unchanged |

Accepted trades by symbol:

| Symbol | v1.33-C1 | v1.36-A1 | Retention |
|---|---:|---:|---:|
| US30.cash | 450 | 208 | 46.22% |
| US100.cash | 282 | 118 | 41.84% |
| JP225.cash | 437 | 160 | 36.61% |
| USDJPY | 515 | 176 | 34.17% |

Candidate event SHA256:
`3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573`.

## Stage 1 — 20,000-path screen

[MEASURED: registered screen @ `e3461c2`]

| Metric | v1.33-C1 control | v1.36-A1 | A1 minus control |
|---|---:|---:|---:|
| Phase-1 pass | 94.3450% | 95.4400% | +1.0950 pp |
| Conditional phase-2 pass | 94.2869% | 95.3112% | +1.0243 pp |
| Both-phase pass | 88.9550% | **90.9650%** | **+2.0100 pp** |
| Both-phase Wilson interval | 88.5851%–89.3143% | **90.6260%–91.2929%** | — |
| Hard halt | 0.2200% | **0.0400%** | -0.1800 pp |
| Hard-halt Wilson upper | 0.2816% | **0.0710%** | — |
| Timeout | 10.8250% | **8.9950%** | -1.8300 pp |
| Timeout Wilson upper | 11.1917% | **9.3333%** | — |
| Firm breach | 0.0000% | 0.0000% | 0.0000 pp |
| Successful median days | 503 | 979 | **+476** |
| Successful p90 days | 817 | 1,505 | **+688** |

[MEASURED: paired screen @ `e3461c2`] Candidate-only passes were 2,010 and
control-only passes were 1,608. The paired point delta was +2.0100 percentage
points; the conservative paired lower bound was +1.2112 points; the exact
one-sided McNemar p-value was `1.2498199294805204e-11`.

Both registered screen gates passed: A1 hard halt was below 0.3700%, and the
paired lower bound was strictly positive. The confirmation therefore ran.

Screen row hashes: control
`a3cf941dfb3b1828f81f3732292a07aa1ef411b418dbc419b3f0bb4ed7a081a5`;
A1 `ecfba59cccce36172b15284d20854cc3ee15743b3bf7b7b0585b19c21b066f13`.

## Stage 2 — 100,000-path confirmation

[MEASURED: registered confirmation @ `e3461c2`]

| Metric | v1.33-C1 control | v1.36-A1 | A1 minus control |
|---|---:|---:|---:|
| Phase-1 pass | 94.3450% | 95.4380% | +1.0930 pp |
| Conditional phase-2 pass | 94.2307% | 95.3436% | +1.1128 pp |
| Both-phase pass | 88.9020% | **90.9940%** | **+2.0920 pp** |
| Both-phase Wilson interval | 88.7376%–89.0643% | **90.8440%–91.1418%** | — |
| Hard halt | 0.1910% | **0.0350%** | -0.1560 pp |
| Hard-halt Wilson upper | 0.2151% | **0.0462%** | — |
| Timeout | 10.9070% | **8.9710%** | -1.9360 pp |
| Timeout Wilson upper | 11.0702% | **9.1208%** | — |
| Firm breach | 0.0000% | 0.0000% | 0.0000 pp |
| Successful median days | 499 | 978 | **+479** |
| Successful p90 days | 815 | 1,508 | **+693** |

[MEASURED: paired confirmation @ `e3461c2`] Candidate-only passes were 10,066
and control-only passes were 7,974. The paired point delta was +2.0920
percentage points; the conservative paired lower bound was +1.7366 points;
the exact one-sided McNemar p-value was `4.563894255373358e-55`.

Both confirmation gates passed. A1's 90.8440% Wilson lower bound also remained
above the owner's 88% modeled-pass target. This is not a guarantee of a future
challenge outcome.

Confirmation row hashes: control
`c95758cc00f260aec6009ce9a3fac0f83bda5c37cab34f8a9c11a0a25be553ef`;
A1 `2c5b5d61f104ca6fcc010d0dd5ffac3baa6b7b0145cb974dd71699c112ee97fd`.

## Corrected fidelity versus supplied screen

[DERIVED from the supplied report and registered confirmation]

| A1 metric | Supplied optimistic | Corrected 100k | Corrected minus supplied |
|---|---:|---:|---:|
| Both-phase pass | 93.220% | 90.994% | -2.226 pp |
| Hard halt | 0.015% | 0.035% | +0.020 pp |
| Timeout | 6.770% | 8.971% | +2.201 pp |
| Successful median days | 895 | 978 | +83 |

The supplied 93.22% headline did not reproduce at corrected fidelity. The core
claim did survive: the 3.0-ATR threshold beat its paired C1 control, reduced
hard halts and timeouts, and cleared both frozen gates. The cost also survived:
median completion time rose from 499 to 978 days, approximately 1.96×, while
the source tape retained about 40% of C1 opportunities.

The C1 control here measured 88.902%, not the 88.274% from the earlier
v1.31-versus-C1 confirmation. [DERIVED] This is expected because the eligible
flat-block intersection is treatment-pair-specific: 389 blocks here versus
373 in the earlier experiment. The valid decision statistic is the paired A1
minus C1 comparison inside this frozen run, not a cross-experiment subtraction.

## Complete simulator counter ledger

[MEASURED: result JSON @ `e3461c2`] Counter values are sums across the stated
number of paths. P1 and P2 are the two sequential FTMO phases.

### Screen counter totals

| Counter | Control P1 | Control P2 | A1 P1 | A1 P2 |
|---|---:|---:|---:|---:|
| `completed` | 6,068,651 | 2,961,642 | 4,553,660 | 2,247,503 |
| `daily_halts` | 0 | 0 | 0 | 0 |
| `entries` | 6,068,683 | 2,961,660 | 4,553,667 | 2,247,504 |
| `ignored_lifecycle` | 15,108,506 | 15,285,363 | 4,229,720 | 4,645,594 |
| `max_active` | 40,000 | 37,738 | 40,000 | 38,176 |
| `min_lot_rejections` | 0 | 0 | 0 | 0 |
| `min_lot_substitutions` | 0 | 0 | 0 | 0 |
| `partial_executed` | 3,458,402 | 1,688,222 | 2,645,695 | 1,306,057 |
| `partial_skipped_rounding` | 0 | 0 | 0 | 0 |
| `pending_admitted` | 10,294,958 | 5,025,337 | 7,644,318 | 3,774,918 |
| `pending_cancel_daily_halt` | 0 | 0 | 0 | 0 |
| `pending_cancel_source` | 4,223,211 | 2,060,624 | 3,088,113 | 1,524,922 |
| `pending_cancel_target` | 3,058 | 3,048 | 2,536 | 2,491 |
| `positive_swap_suppressed` | 0 | 0 | 0 | 0 |
| `skipped_consecutive` | 2,329 | 1,224 | 0 | 0 |
| `skipped_daily_halt` | 0 | 0 | 0 | 0 |
| `skipped_fill_cap` | 0 | 0 | 0 | 0 |
| `skipped_target_freeze` | 5,344,909 | 5,405,950 | 1,508,225 | 1,653,539 |
| `swap_events` | 0 | 0 | 0 | 0 |

Screen reason counts: control P1 `{1: 18869, 4: 28, 6: 1103}`, control P2
`{1: 17791, 4: 16, 6: 1062, 7: 1131}`, A1 P1
`{1: 19088, 4: 7, 6: 905}`, A1 P2 `{1: 18193, 4: 1, 6: 894, 7: 912}`.

### Confirmation counter totals

| Counter | Control P1 | Control P2 | A1 P1 | A1 P2 |
|---|---:|---:|---:|---:|
| `completed` | 30,281,305 | 14,691,175 | 22,789,256 | 11,170,179 |
| `daily_halts` | 0 | 0 | 0 | 0 |
| `entries` | 30,281,452 | 14,691,252 | 22,789,283 | 11,170,188 |
| `ignored_lifecycle` | 75,725,564 | 77,497,406 | 21,207,537 | 23,127,970 |
| `max_active` | 200,000 | 188,690 | 200,000 | 190,876 |
| `min_lot_rejections` | 0 | 0 | 0 | 0 |
| `min_lot_substitutions` | 0 | 0 | 0 | 0 |
| `partial_executed` | 17,260,821 | 8,378,874 | 13,239,584 | 6,496,592 |
| `partial_skipped_rounding` | 0 | 0 | 0 | 0 |
| `pending_admitted` | 51,376,843 | 24,916,757 | 38,268,719 | 18,759,007 |
| `pending_cancel_daily_halt` | 0 | 0 | 0 | 0 |
| `pending_cancel_source` | 21,079,512 | 10,210,389 | 15,466,683 | 7,576,600 |
| `pending_cancel_target` | 15,850 | 15,099 | 12,749 | 12,218 |
| `positive_swap_suppressed` | 0 | 0 | 0 | 0 |
| `skipped_consecutive` | 12,163 | 6,104 | 0 | 0 |
| `skipped_daily_halt` | 0 | 0 | 0 | 0 |
| `skipped_fill_cap` | 0 | 0 | 0 | 0 |
| `skipped_target_freeze` | 26,767,533 | 27,397,846 | 7,559,782 | 8,239,882 |
| `swap_events` | 0 | 0 | 0 | 0 |

Confirmation reason counts: control P1 `{1: 94345, 4: 126, 6: 5529}`,
control P2 `{1: 88902, 4: 65, 6: 5378, 7: 5655}`, A1 P1
`{1: 95438, 4: 26, 6: 4536}`, A1 P2
`{1: 90994, 4: 9, 6: 4435, 7: 4562}`.

## Artifact hashes and ledger

[MEASURED: SHA256 @ `e3461c2`]

- Result JSON committed LF blob:
  `712bd41522d7874dd8a20dff6ccea8d919b6e167ee70d5937f646e0c27d82c3d`.
  The pre-stage Windows working-tree CRLF form was
  `64e9082e938ca3e19b457349b2d985bbe582094477a52118917b8d744fafa54a`;
  Git normalization changed line endings only.
- Builder:
  `cccbfc12c6ae45b524a3873b7f7d59a54ec60e3f1f2165d36491ecb50472031b`.
- Runner:
  `db6a70de2433cea74f5c411370a5281695ec725e55bff5cff4bc946cfd50a04d`.
- Candidate EA:
  `397ece9d1c8b841bbe3ed763ef2a6d8ddb3cd207f9ea69244d8857f162feef82`.

Trial ledger charge: one confirmatory cell, zero discovery cells.

## Post-result diagnostic incident

[MEASURED: first independent tape-equivalence diagnostic @ `e3461c2`] One
post-result diagnostic ended with `AssertionError`. The script imported the
same `parity_engine.py` under two module names (`backtest.parity_engine` and
top-level `parity_engine`) and changed the inactive module's global threshold.
This was not a registered Monte Carlo run and did not alter the committed
runner or result JSON.

[MEASURED: corrected single-module diagnostic @ `e3461c2`] The explicit
`momentum_atr_mult=3.0` tape then matched the supplier's module-global 3.0
method exactly, candidate event SHA256
`3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573`.
Two independent tape builds produced identical control/candidate hashes and
the same 389 common blocks. Result assertions also passed.

## Final decision

**A1_CONFIRMED_BEATS_V133_C1.** v1.36-A1 is the new research champion for
modeled FTMO pass probability under this corrected-fidelity test. It is not
the live EA and has not been installed. Its principal trade-off is nearly
doubling modeled completion time while retaining roughly 40% of signals.
