# v1.36-A1 M15-grain universe-admission report

Date: 2026-07-18

## Headline verdict

**STUDY STOPPED AT MANDATORY CONTROL GATE — NO SYMBOL ADMITTED.**

[MEASURED: `python backtest/run_v136_a1_universe_admission.py` @
`3ac108a0e48e4d47c0483f584b0c2dac6fb32463`] The corrected A1 control failed
the pre-registered real-data E1/E2 structural-parity gate before either
candidate cell began:

```text
FATAL RuntimeError A1_CONTROL:discovery: E1/E2 structural parity failed: ['source_lifecycle']
```

[DERIVED] This means the discovery control's source lifecycle changed outside
the permitted charged-cost fields between E1 and E2. Under the registered stop
rule, the control is invalid for admission comparison. `FRA40.cash` and
`AUS200.cash` are therefore **not tested, not passed, and not admitted**. No
post-hoc reconciliation or modified rerun was performed.

## Frozen provenance

- [MEASURED: `git rev-parse HEAD` @ `3ac108a`] tested commit:
  `3ac108a0e48e4d47c0483f584b0c2dac6fb32463`.
- [MEASURED: SHA256 @ `3ac108a`] registered spec:
  `665d90cd5b9e6d0644dd5cdc824115be460ff8ba896e53198d382d370507c119`.
- [MEASURED: `python backtest/verify_data.py` @ `3ac108a`] exact output:
  `verified 46 OK, 0 missing, 0 mismatched`.
- [MEASURED: SHA256 @ `3ac108a`] data manifest:
  `ec1fcc26132366ab157b8d298c1cf60d79d63ac16708d1a887a1740ad46de49f`.
- [MEASURED: SHA256 @ `3ac108a`] frozen broker metadata:
  `bb0b3489c48e7cad83e5a85c3eea6005db7c5ec0e7ed9098c76814bb049cd3a6`.
- [MEASURED: SHA256 @ `3ac108a`] live v1.36-A1 source, read only:
  `531d2a8b305e145241d00b9db11f716b49f1d90f190914046ce7b7cdae02b833`.
- [MEASURED: SHA256 @ `3ac108a`] runner:
  `7676857034ec336f4b3491f2649cbc18d79d52011d850e1d1f432676d23f8382`.
- [MEASURED: SHA256 @ `3ac108a`] M15 builder:
  `9e09529bc9ee7d9eba174f2faabdfe31df9247b5a29b257d8bea9eb95766338d`.
- [MEASURED: SHA256 @ `3ac108a`] synthetic suite:
  `431ad367c75485bc98463486c2b50699af8c5b103548d3249708af4ae3dfe3b3`.

## Mandatory pre-outcome output

[MEASURED: registered runner @ `3ac108a`] The protected regression and
synthetic lines were:

```text
DATA_VERIFY verified 46 OK, 0 missing, 0 mismatched
PROTECTED_REGRESSION legacy PASS trades=1645 events=7317 sha256=3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f
PROTECTED_REGRESSION c1 PASS trades=1684 events=7145 sha256=b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187
PROTECTED_REGRESSION a1 PASS trades=662 events=2819 sha256=3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573
SYNTHETIC_TESTS PASS universe=36 pass_policy=10 risk_policy=16 adapter=23
TIMESTAMP_SPLIT {"cutoff_epoch": 1759773600, "cutoff_utc": "2025-10-06T18:00:00+00:00", "end_epoch": 1782849600, "end_utc": "2026-06-30T20:00:00+00:00", "start_epoch": 1705921200, "start_utc": "2024-01-22T11:00:00+00:00"}
FATAL RuntimeError A1_CONTROL:discovery: E1/E2 structural parity failed: ['source_lifecycle']
```

[MEASURED: registered runner @ `3ac108a`] The full fatal traceback is retained
verbatim in `backtest/v136_a1_universe_admission_failures.jsonl`. Its staged
LF Git-blob SHA256 is
`fc198bcc2f461d2e205e445f790d19ee456b63a7861721883ddc48262640fd4f`.

## Cell disposition and ledger

| Registered item | Status | Charge |
|---|---:|---:|
| Mandatory M15 A1 control gate | [MEASURED: runner @ `3ac108a`] failed | [DERIVED] 0 |
| `FRA40.cash` discovery | [MEASURED: runner @ `3ac108a`] not run | [DERIVED] 0 |
| `AUS200.cash` discovery | [MEASURED: runner @ `3ac108a`] not run | [DERIVED] 0 |
| 20,000-path account screens | [MEASURED: runner @ `3ac108a`] not run | [DERIVED] 0 |
| 100,000-path confirmation | [MEASURED: runner @ `3ac108a`] not run | [DERIVED] 0 |

- [DERIVED] Trial ledger: `300 -> 300`; charged strategy cells: `0`.
- [MEASURED: result-file check @ `3ac108a`] No
  `v136_a1_universe_admission_results.json` was created.
- [MEASURED: checkpoint-directory check @ `3ac108a`] No Monte Carlo checkpoint
  or path was created by this study.

## Aborted pre-cell attempt

[MEASURED: failure ledger @ `b288a06`] A prior process was deliberately
interrupted during `load_contexts()` after an independent audit found the
nominal-placement timestamp defect. It produced `KeyboardInterrupt` before the
new M15 control, either candidate, any placebo, or any Monte Carlo path. Its
verbatim traceback is the first row of the same failure JSONL. [DERIVED] Its
ledger charge is `0`.

## Safety and next decision

[MEASURED: repository diff and terminal journal @ `3ac108a`] No EA source,
symbol whitelist, MT5 file, terminal setting, order, position, or live account
was changed. The deployed four-symbol v1.36-A1 remains untouched.

[HYPOTHESIS] A separately pre-registered diagnostic could identify whether the
source-lifecycle mismatch is a numeric serialization difference or a genuine
cost-dependent execution path. That is new work; it cannot be used to rescue
or reinterpret this failed admission study.
