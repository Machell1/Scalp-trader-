# v1.31 versus E3 Challenger Head-to-Head Report

Date: 2026-07-16

Verdict: **NO_CONFIRMATION_PASS — DO NOT INSTALL E3. KEEP v1.31 UNCHANGED.**

Headline finding: E3 materially improved the paired 20,000-path two-step pass estimate, but it failed its own pre-registered hard-halt gate. The screen stopped the protocol before 100,000-path confirmation, compilation for deployment, or any MT5 write.

## Provenance and integrity

- [MEASURED: `git rev-parse HEAD` and `python backtest/run_v131_challenger_headtohead.py` @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] Tested commit: `042dfe49955f1057bb2d0a389a28661cce0f8dd7`.
- [MEASURED: `Get-FileHash -Algorithm SHA256 docs/V131_CHALLENGER_HEADTOHEAD_SPEC_2026-07-16.md` @ `7200a72589ffa9e975bc2c90c3e37f3ba480d333`] Pre-registration SHA256: `0ef15210cb19bc22903d1165ed27c640f691c522d7b58e89ea3557253685c87a`.
- [MEASURED: `python backtest/verify_data.py` @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] Verbatim: `verified 46 OK, 0 missing, 0 mismatched`.
- [MEASURED: `python backtest/v130_pass_policy.py` @ `462580bf274dc9c74448e60176fbb4bcb84f7279`] Account-policy synthetic suite: 10 passed, 0 failed.
- [MEASURED: `python backtest/v130_risk_policy.py --self-test` @ `462580bf274dc9c74448e60176fbb4bcb84f7279`] Risk/lot/partial synthetic suite: 16 passed, 0 failed.
- [MEASURED: runner path-0 comparison @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] Python/C# parity: exact for both `V131_CONTROL` and `E3_CHALLENGER`.
- [MEASURED: `Get-FileHash -Algorithm SHA256 backtest/v131_challenger_headtohead_results.json` @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] Final result SHA256: `1e3183d8739029dbd7deb02bcbf1ba8fa096197e885b96bd5c6d2b8fe532889e`.

## Fair-comparison controls

[MEASURED: runner configuration @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] Both cells used the same four-symbol universe, H1 signal/entry rules, E2 stressed cost tape, common moving-block bootstrap (`seed=13020260711`, block length 20), 373 common eligible flat blocks, one-seat cluster/global coupling, and the same dynamic cash-risk map: 0.30% for `US30.cash`, `US100.cash`, and `JP225.cash`; 0.05% for `USDJPY`.

[MEASURED: `LEGACY_DEFAULT_REGRESSION` @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] The additive tape-builder change preserved the legacy default tape exactly: 1,645 trades, 7,317 events, event SHA256 `3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f`.

[MEASURED: challenge tape records @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] The actual head-to-head used the pre-registered reference resolver for both cells: stop first, then the +1R partial, then the final target on ambiguous same bars.

| Tape census | v1.31 control | E3 challenger | Evidence |
|---|---:|---:|---|
| Accepted trades | 1,645 | 1,684 | [MEASURED: runner @ `042dfe4`] |
| `US30.cash` | 440 | 450 | [MEASURED: runner @ `042dfe4`] |
| `US100.cash` | 271 | 282 | [MEASURED: runner @ `042dfe4`] |
| `JP225.cash` | 426 | 437 | [MEASURED: runner @ `042dfe4`] |
| `USDJPY` | 508 | 515 | [MEASURED: runner @ `042dfe4`] |
| Filled trades | 969 | 987 | [MEASURED: runner @ `042dfe4`] |
| Source partial events | 548 | 558 | [MEASURED: runner @ `042dfe4`] |
| Same-bar partial plus final | 96 | 218 | [MEASURED: runner @ `042dfe4`] |
| Event-tape SHA256 | `19e87996bea044c19b8789a905fe65c1aab687e90fc6542aa641afe44725b218` | `13e1d03561701b97bbdccfe71d80fc6ab3f8491af945560da0cfedc5b18722f5` | [MEASURED: runner @ `042dfe4`] |

## Frozen 20,000-path screen

| Metric | v1.31 control | E3 challenger | E3 minus control | Evidence |
|---|---:|---:|---:|---|
| Phase 1 pass | 86.9600% | 93.1000% | +6.1400 pp | [MEASURED/DERIVED: runner @ `042dfe4`] |
| Conditional Phase 2 pass | 88.2590% | 93.0827% | +4.8237 pp | [MEASURED/DERIVED: runner @ `042dfe4`] |
| Both phases | 76.7500% | 86.6600% | +9.9100 pp | [MEASURED/DERIVED: runner @ `042dfe4`] |
| Both-phase Wilson lower | 76.2551% | 86.2596% | +10.0045 pp | [MEASURED/DERIVED: runner @ `042dfe4`] |
| Hard halt | 4.0550% | 0.4350% | -3.6200 pp | [MEASURED/DERIVED: runner @ `042dfe4`] |
| Timeout | 19.1950% | 12.9050% | -6.2900 pp | [MEASURED/DERIVED: runner @ `042dfe4`] |
| Firm breach | 0.0000% | 0.0000% | 0.0000 pp | [MEASURED/DERIVED: runner @ `042dfe4`] |
| Median total days among successes | 772.0 | 595.5 | -176.5 | [MEASURED/DERIVED: runner @ `042dfe4`] |
| P90 total days among successes | 1,361 | 988 | -373 | [MEASURED/DERIVED: runner @ `042dfe4`] |
| Both-phase passes | 15,350 / 20,000 | 17,332 / 20,000 | +1,982 | [MEASURED/DERIVED: runner @ `042dfe4`] |
| Row SHA256 | `bdad29e6fafe7a27f296f06793c769b30b9b0e22d67d8e0f26a08b338b1ea24d` | `ac5a98e6b4768fdec1a2f797e1949eb6d272b4bc6147a091fbe89d87bfe49797` | — | [MEASURED: runner @ `042dfe4`] |

[MEASURED: paired outcomes @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] E3-only passes `n10=3,960`; control-only passes `n01=1,978`; paired point delta `+9.9100 pp`; conservative paired lower bound `+8.9376 pp`; exact one-sided McNemar/binomial p-value `7.79336244209871e-149`. The Clopper–Pearson marginal terms used by the conservative bound were `p10_lower=0.1924964796412242` and `p01_upper=0.1031208002813065`.

[MEASURED: account counters @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] Partial-close rounding skips were 0 in both phases for both cells across all 20,000 paths. This confirms that preserving v1.31 dynamic sizing removed PR #46's 0.01-lot partial-execution mismatch. Every simulator counter and result-reason count is retained in `backtest/v131_challenger_headtohead_results.json`.

## Gate decision

| Frozen E3 screen gate | Measured E3 result | Decision | Evidence |
|---|---:|---|---|
| Both phases > 85.4740% | 86.6600% | PASS | [MEASURED: runner @ `042dfe4`] |
| Wilson lower > 85.2898% | 86.2596% | PASS | [MEASURED: runner @ `042dfe4`] |
| Hard halt <= 0.3700% | 0.4350% | **FAIL** | [MEASURED: runner @ `042dfe4`] |
| Timeout < 14.1560% | 12.9050% | PASS | [MEASURED: runner @ `042dfe4`] |
| Paired lower > 0 | +8.9376 pp | PASS | [MEASURED: runner @ `042dfe4`] |

[DERIVED] E3 missed the hard-halt ceiling by 0.0650 percentage points. Four gates passed and one failed. The protocol requires all five, so the result is `NO_CONFIRMATION_PASS`.

## Fidelity finding

[DERIVED] The previously quoted 85.4740% v1.31 benchmark came from the legacy tape whose default bytes were preserved above. That tape omits the +1R partial when the partial and final target occur in the same OHLC bar. Applying the pre-registered `retest_engine.resolve` ordering to v1.31 reduced its 20,000-path estimate to 76.7500%. This is a live-fidelity correction, not evidence that the installed EA suddenly changed. It means the older account estimate was optimistic for the frozen reference semantics.

## Reporting correction and deterministic rerun

[MEASURED: first screen @ `462580bf274dc9c74448e60176fbb4bcb84f7279`] The first screen produced the same control and E3 row hashes and the same gate failure, but the runner inherited an old helper's incorrect labels for two Clopper–Pearson terms. Its superseded JSON SHA256 was `7ad3e1cbf6a981a2e653246a4c3028a5791af81040dc2bfabcd558053acfe65c`.

[MEASURED: corrected screen @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] Commit `042dfe4` corrected reporting only, added the true paired point delta and exact p-value, and reran the unchanged frozen paths. Both 20,000-path row SHA256 values reproduced exactly. The gate decision did not change.

## Deployment and terminal-write journal

- [MEASURED: protocol execution @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] 100,000-path confirmation runs: 0, because the screen failed.
- [MEASURED: protocol execution @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] MetaEditor deployment compiles: 0, because the deployment phase was not entered.
- [MEASURED: terminal-write journal @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] MT5 file/chart/input/process/order/position writes: 0.
- [MEASURED: terminal-write journal @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] Orders placed, modified, or closed: 0.
- [MEASURED: repository diff @ `042dfe49955f1057bb2d0a389a28661cce0f8dd7`] The installed v1.31 EA was not modified or replaced.

## Final decision

E3 beats the faithfully resolved v1.31 control on paired pass probability, speed, timeout rate, and hard-halt rate, but it does not clear its absolute hard-halt safety ceiling. Under the pre-registered rules, a near miss is still a failure. Do not install it on the FTMO demo account and do not reinterpret this screen as a deployment approval.

Trial ledger: one confirmatory cell, zero discovery cells.
