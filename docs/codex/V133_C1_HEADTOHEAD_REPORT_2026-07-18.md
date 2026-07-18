# v1.33-C1 corrected-fidelity head-to-head report

Date: 2026-07-18

Verdict: **C1_CONFIRMED_BEATS_V131 — GEOMETRY CONFIRMED; EA IMPLEMENTATION NOT
SUPPLIED OR DEPLOYMENT-VALIDATED.**

## Provenance and integrity

- [MEASURED: attachment SHA256 @ `748390ca3a9ef76dbaeaaff52d9a1da0590cb903`]
  Owner-supplied C1 text SHA256:
  `11c43f24c6597f5824391914e8b29dd5d59645dab01f3aac60d5ea5e2b8ce1ea`.
- [MEASURED: `Get-FileHash docs/V133_C1_CORRECTED_HEADTOHEAD_SPEC_2026-07-18.md`
  @ `748390ca3a9ef76dbaeaaff52d9a1da0590cb903`] Registered pre-run spec SHA256:
  `1ade5f5735230381cccbbc16d61dd51bad751811af8ca83c63ff1694886b51e3`.
- [MEASURED: `python backtest/verify_data.py` @ `748390c`] Verbatim:
  `verified 46 OK, 0 missing, 0 mismatched`.
- [MEASURED: runner regression @ `748390c`] Legacy default: 1,645 trades,
  7,317 events, exact event SHA256
  `3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f`.
- [MEASURED: runner path-0 gate @ `748390c`] Python/C# parity was exact for
  both `V131_CONTROL` and `V133_C1`.
- [MEASURED: `python backtest/v130_pass_policy.py` @ `748390c`] 10 synthetic
  pass-policy tests passed.
- [MEASURED: `python backtest/v130_risk_policy.py --self-test` @ `748390c`]
  16 synthetic risk-policy tests passed.
- [MEASURED: `Get-FileHash backtest/v133_c1_headtohead_results.json` @
  `748390c`] Result JSON SHA256:
  `e49e9f5212c56a4943f09bbc46a8addcf75e16fd9f15a037f4b79669abc74431`.

## Frozen comparison

[MEASURED: runner configuration @ `748390c`] Both cells used E2 stressed costs,
seed `13020260711`, 20-day moving blocks, 373 common eligible flat-block starts,
the same four-symbol H1 universe, corrected stop/partial/final same-bar ordering,
and the same dynamic risk: 0.300% for US30, US100, and JP225 and 0.050% for
USDJPY.

| Cell | Partial | Trigger | Final target |
|---|---:|---:|---:|
| v1.31 control | 50% | +1.0R | 2.0 ATR |
| v1.33-C1 | 75% | +1.0R | 1.5 ATR |

No entry, signal, universe, risk, cost, scheduler, or account-rule change was
included.

## 20,000-path screen

[MEASURED/DERIVED: `python -u backtest/run_v133_c1_headtohead.py` @ `748390c`]

| Metric | v1.31 | C1 | C1 minus v1.31 |
|---|---:|---:|---:|
| Phase-1 pass | 86.9600% | 93.7550% | +6.7950 pp |
| Conditional phase-2 pass | 88.2590% | 94.0590% | +5.8000 pp |
| Both-phase pass | 76.7500% | **88.1850%** | **+11.4350 pp** |
| Both-phase Wilson lower | 76.2551% | **87.8044%** | +11.5493 pp |
| Both-phase Wilson upper | 77.2377% | 88.5553% | +11.3176 pp |
| Hard halt | 4.0550% | **0.2650%** | -3.7900 pp |
| Hard-halt Wilson upper | 4.2907% | **0.3319%** | -3.9588 pp |
| Timeout | 19.1950% | **11.5500%** | -7.6450 pp |
| Timeout Wilson upper | 19.6572% | 11.9270% | -7.7302 pp |
| Firm breach | 0.0000% | 0.0000% | 0.0000 pp |
| Median successful completion | 772.0 days | **573.0 days** | -199.0 days |
| P90 successful completion | 1,361 days | **945 days** | -416 days |

[MEASURED: paired screen @ `748390c`] Candidate-only passes `n10=4,027`;
control-only passes `n01=1,740`; paired point delta `+11.4350 pp`;
conservative paired lower bound `+10.4820 pp`; exact one-sided McNemar p-value
`7.009609227749693e-205`.

| Frozen screen gate | Result | Decision |
|---|---:|---|
| C1 hard halt <= 0.3700% | 0.2650% | PASS |
| Paired lower bound > 0 | +10.4820 pp | PASS |

Screen row SHA256: v1.31
`bdad29e6fafe7a27f296f06793c769b30b9b0e22d67d8e0f26a08b338b1ea24d`;
C1 `5ee84ca96624508eda1ef1538af99067b70255358dea81f2ccebe4bc39d6d598`.

## 100,000-path confirmation

[MEASURED/DERIVED: `python -u backtest/run_v133_c1_headtohead.py` @ `748390c`]

| Metric | v1.31 | C1 | C1 minus v1.31 |
|---|---:|---:|---:|
| Phase-1 pass | 87.0940% | 93.9030% | +6.8090 pp |
| Conditional phase-2 pass | 88.2070% | 94.0055% | +5.7985 pp |
| Both-phase pass | 76.8230% | **88.2740%** | **+11.4510 pp** |
| Both-phase Wilson lower | 76.6028% | **88.1056%** | +11.5028 pp |
| Both-phase Wilson upper | 77.0418% | 88.4403% | +11.3985 pp |
| Hard halt | 3.9440% | **0.2660%** | -3.6780 pp |
| Hard-halt Wilson upper | 4.0465% | **0.2942%** | -3.7523 pp |
| Timeout | 19.2330% | **11.4600%** | -7.7730 pp |
| Timeout Wilson upper | 19.4388% | 11.6267% | -7.8121 pp |
| Firm breach | 0.0000% | 0.0000% | 0.0000 pp |
| Median successful completion | 772.0 days | **572.0 days** | -200.0 days |
| P90 successful completion | 1,358 days | **936 days** | -422 days |

[MEASURED: paired confirmation @ `748390c`] Candidate-only passes
`n10=20,143`; control-only passes `n01=8,692`; paired point delta
`+11.4510 pp`; conservative paired lower bound `+11.0265 pp`; exact one-sided
McNemar p-value underflowed to `0.0` in double precision.

| Frozen confirmation gate | Result | Decision |
|---|---:|---|
| C1 hard halt <= 0.3700% | 0.2660% | PASS |
| Paired lower bound > 0 | +11.0265 pp | PASS |

Confirmation row SHA256: v1.31
`9d1e039dfebff8abac73b982383c2865febc96369d5a7d1e74b68790ae7822f8`;
C1 `af6043776f5a5a29f2f29a2ef025d21a681fb684e1fc58330b95991d2c8787b1`.

[DERIVED] C1 also exceeded the owner's 88% modeled-pass target: the point estimate
was 88.2740% and its Wilson lower bound was 88.1056%. This is a historical
simulation result, not a guarantee that a live account will pass.

## Tape census

[MEASURED: tape records @ `748390c`]

| Item | v1.31 | C1 |
|---|---:|---:|
| Accepted trades | 1,645 | 1,684 |
| US30 | 440 | 450 |
| US100 | 271 | 282 |
| JP225 | 426 | 437 |
| USDJPY | 508 | 515 |
| Filled/entry events | 969 | 987 |
| Partial events | 548 | 558 |
| Same-bar partial and final | 96 | 218 |
| Pending opens | 1,645 | 1,684 |
| Pending cancels | 676 | 697 |
| Mark events | 2,606 | 2,232 |
| Total events | 7,413 | 7,145 |

Event-tape SHA256: v1.31
`19e87996bea044c19b8789a905fe65c1aab687e90fc6542aa641afe44725b218`;
C1 `b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187`.

## Simulator counters

Every counter is retained below and in the result JSON. All partial-close rounding
skips, min-lot rejections/substitutions, fill-cap skips, daily-halt skips/cancels,
positive-swap suppressions, and swap events were zero in every cell, phase, and
stage.

[MEASURED: screen counters @ `748390c`]

| Counter | v1.31 P1 | v1.31 P2 | C1 P1 | C1 P2 |
|---|---:|---:|---:|---:|
| completed | 9,285,061 | 4,135,863 | 6,842,099 | 3,321,440 |
| daily_halts | 0 | 0 | 0 | 0 |
| entries | 9,285,675 | 4,136,188 | 6,842,137 | 3,321,464 |
| ignored_lifecycle | 28,001,164 | 25,873,615 | 16,030,125 | 15,361,310 |
| max_active | 40,000 | 34,784 | 40,000 | 37,502 |
| min_lot_rejections | 0 | 0 | 0 | 0 |
| min_lot_substitutions | 0 | 0 | 0 | 0 |
| partial_executed | 5,248,555 | 2,338,398 | 3,855,299 | 1,870,622 |
| partial_skipped_rounding | 0 | 0 | 0 | 0 |
| pending_admitted | 15,837,082 | 7,054,684 | 11,727,770 | 5,685,984 |
| pending_cancel_daily_halt | 0 | 0 | 0 | 0 |
| pending_cancel_source | 6,547,844 | 2,915,413 | 4,882,367 | 2,361,504 |
| pending_cancel_target | 3,442 | 3,024 | 3,254 | 3,013 |
| positive_swap_suppressed | 0 | 0 | 0 | 0 |
| skipped_consecutive | 20,651 | 9,324 | 4,011 | 2,013 |
| skipped_daily_halt | 0 | 0 | 0 | 0 |
| skipped_fill_cap | 0 | 0 | 0 | 0 |
| skipped_target_freeze | 9,099,177 | 8,437,446 | 5,739,346 | 5,500,378 |
| swap_events | 0 | 0 | 0 | 0 |

Screen reason counts: v1.31 P1 `{1:17392, 4:531, 6:2077}`, v1.31 P2
`{1:15350, 4:280, 6:1762, 7:2608}`, C1 P1
`{1:18751, 4:35, 6:1214}`, C1 P2 `{1:17637, 4:18, 6:1096, 7:1249}`.

[MEASURED: confirmation counters @ `748390c`]

| Counter | v1.31 P1 | v1.31 P2 | C1 P1 | C1 P2 |
|---|---:|---:|---:|---:|
| completed | 46,288,762 | 20,711,168 | 34,096,556 | 16,499,837 |
| daily_halts | 0 | 0 | 0 | 0 |
| entries | 46,291,868 | 20,712,614 | 34,096,740 | 16,499,957 |
| ignored_lifecycle | 137,972,965 | 132,463,857 | 78,499,262 | 77,380,776 |
| max_active | 200,000 | 174,188 | 200,000 | 187,806 |
| min_lot_rejections | 0 | 0 | 0 | 0 |
| min_lot_substitutions | 0 | 0 | 0 | 0 |
| partial_executed | 26,164,377 | 11,714,357 | 19,213,872 | 9,299,605 |
| partial_skipped_rounding | 0 | 0 | 0 | 0 |
| pending_admitted | 78,947,956 | 35,323,114 | 58,431,427 | 28,249,259 |
| pending_cancel_daily_halt | 0 | 0 | 0 | 0 |
| pending_cancel_source | 32,638,452 | 14,595,309 | 24,318,437 | 11,734,100 |
| pending_cancel_target | 16,937 | 14,878 | 16,198 | 15,182 |
| positive_swap_suppressed | 0 | 0 | 0 | 0 |
| skipped_consecutive | 103,285 | 46,137 | 19,726 | 10,067 |
| skipped_daily_halt | 0 | 0 | 0 | 0 |
| skipped_fill_cap | 0 | 0 | 0 | 0 |
| skipped_target_freeze | 44,827,172 | 43,203,683 | 28,098,338 | 27,717,963 |
| swap_events | 0 | 0 | 0 | 0 |

Confirmation reason counts: v1.31 P1 `{1:87094, 4:2699, 6:10207}`, v1.31
P2 `{1:76823, 4:1245, 6:9026, 7:12906}`, C1 P1
`{1:93903, 4:163, 6:5934}`, C1 P2 `{1:88274, 4:103, 6:5526, 7:6097}`.

## Implementation and deployment boundary

[MEASURED: filename search and Git remote inspection before registration] The
owner-supplied text named `MomentumPullbackEA_v133_C1.mq5`,
`backtest/run_v133_geometry_grid.py`, and
`backtest/v133_geometry_grid_results.json`, but none of those files was present in
the supplied workspace or the GitHub remote. The geometry was therefore tested by
parameterizing the already audited corrected-fidelity tape builder.

[DERIVED] This result confirms the C1 exit geometry. It does **not** establish that
an unseen v1.33 EA implements that geometry correctly. Before deployment, the exact
EA source must be supplied, diff-audited against the reviewed EA, cross-checked
against this tape, compiled with 0 errors/0 warnings, and separately authorized by
the owner on a flat account.

Terminal-write journal: MT5 file writes 0; chart/input changes 0; process changes 0;
orders placed/modified/closed 0; positions changed 0.

Trial ledger: one confirmatory candidate cell, zero discovery cells.
