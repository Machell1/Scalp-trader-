# v1.31 E3 Challenger Head-to-Head Specification

Status: PRE-REGISTERED — no candidate results have been run on this branch.

Pre-registration date: 2026-07-16

Starting commit: `785fa58fc37299b621c1f73b5e28c5c1c5e0d1f1` (PR #46 head)

Branch: `codex/v131-challenger-headtohead`

## Purpose and contamination status

This is a paired confirmation of the already-selected E3 exit in PR #46 against the current v1.31 exit. The PR states that a result was archived in another workspace, so E3 is not an uncontaminated discovery. It receives one confirmatory cell here. No exit-family sweep, parameter tuning, symbol changes, risk changes, or post-result rescue are allowed.

The owner amended PR #46's 0.01-lot research cap for this head-to-head: both cells must use the existing v1.31 dynamic risk policy. This is necessary both for a fair account comparison and because a two-thirds close from 0.01 lot is below the 0.01 broker minimum/step on the registered symbols and would be skipped.

## Frozen data and provenance

- Use only the repository's 46 files pinned by `backtest/data/MANIFEST.sha256`.
- Before results, `python backtest/verify_data.py` must print exactly `verified 46 OK, 0 missing, 0 mismatched`. Any other result stops the study.
- Record the tested commit, spec hash, code hashes, result hash, and all command output.
- The derived H1 bars come from the pinned M15 files. No data refresh or MT5 history pull is allowed for the backtest.

## Frozen signal, entry, universe, and portfolio rules

Both cells use the same registered v1.31 rules:

- Symbols: `US30.cash`, `US100.cash`, `JP225.cash`, `USDJPY`.
- Timeframe: H1 bars derived on the hour from the pinned M15 data.
- Momentum: six-bar impulse at least 2.0 Wilder ATR(14).
- W2 gate: signal adverse wick at least 0.30 signal-bar ATR.
- Entry: 0.6 signal-bar ATR pullback limit.
- Pending window: the existing three subsequent-bar enumeration and live-parity pending occupancy.
- Stop: 1.0 frozen signal-bar ATR.
- Maximum hold: eight H1 bars from entry, inclusive.
- Portfolio: one active seat per symbol, one seat for the shared `US30.cash`/`US100.cash` cluster, and two global seats.
- Costs: registered per-symbol measured cost doubled for the `E2_STRESS` challenge.
- Intrabar order: stop first; if the stop is not hit, the +1R partial is processed before the farther target. This matches `backtest/retest_engine.py::resolve` and tick-checked EA behavior under OHLC uncertainty.
- Partial volume: requested from original entry volume, floored to broker volume step, and skipped if either resulting leg would be below the broker minimum. The shared account engine's `partial_close_volume` is authoritative.

## Frozen cells

| Cell | Partial at +1R | Remainder target | All other rules |
|---|---:|---:|---|
| `V131_CONTROL` | close 50.0000000% of original volume | +2.0 ATR | frozen above |
| `E3_CHALLENGER` | close 66.6666667% of original volume | +1.5 ATR | frozen above |

## Frozen risk sizing

The two cells use identical dynamic cash risk in both challenge phases:

- `US30.cash`, `US100.cash`, `JP225.cash`: 0.30% of current policy equity per admitted trade.
- `USDJPY`: 0.05% of current policy equity per admitted trade.
- No fixed-lot substitution and no 0.01 cap in the account comparison.
- Broker tick value, tick size, minimum volume, step, and maximum volume come from the pinned `backtest/h1_universe_broker_meta.json` snapshot.

## Implementation and regression gates

1. Add configurable exit parameters without changing the legacy tape builder's default output.
2. Prove the default legacy control tape is byte-identical at the serialized event-field level before and after the additive change.
3. Build both challenge tapes with the reference same-bar partial semantics above.
4. Run the repository risk-policy self-tests.
5. Run exact Python/C# path-0 parity separately for control and challenger. Any mismatch stops the study.
6. Report raw/accepted trades by symbol, event counts, tape/code SHA256 hashes, and common eligible bootstrap-block count.

## Monte Carlo protocol

- Engine: shared audited FTMO two-step account simulator, two-stop equity mode.
- Bootstrap: common moving-block bootstrap, seed `13020260711`, block length 20 days, using only flat block starts eligible in both tapes.
- Screen: 20,000 paired paths.
- Confirmation: 100,000 paired paths, run only if the screen passes every frozen gate.
- Chunk size: 500 paths.
- Compare control and candidate on the same path indexes and common bootstrap blocks.

Report for both cells: Phase 1 probability, conditional Phase 2 probability, both-phase probability and Wilson lower bound, hard-halt probability, timeout probability, median days where available, row SHA256, and all simulator counters. Report paired `n10`, `n01`, point delta, lower bound, and p-value.

## Frozen promotion gates

E3 passes a stage only if every condition is true:

1. both-phase probability is strictly greater than 85.4740%;
2. both-phase Wilson lower bound is strictly greater than 85.2898%;
3. hard-halt probability is no greater than 0.3700%;
4. timeout probability is strictly less than 14.1560%;
5. paired candidate-minus-control lower bound is strictly positive.

The confirmation verdict is `CONFIRMATION_PASS` only if E3 passes all five gates at 100,000 paths. Otherwise it is `NO_CONFIRMATION_PASS`.

## Deployment gate

Installation is prohibited unless the verdict is `CONFIRMATION_PASS`, the challenger compiles with 0 errors and 0 warnings, its live inputs preserve the v1.31 risk policy above, and a fresh read proves the connected FTMO account is a demo account. If there are open positions or working orders, installation stops pending an explicit safe transition decision. No order may be placed as part of installation verification.

If any research, parity, compile, account-type, or position-state gate fails, leave the installed v1.31 EA unchanged and report the failure as the headline result.

## Reporting and trial charge

Every numeric result will be tagged `[MEASURED: command @ commit]` or `[DERIVED]`; untested claims will be tagged `[HYPOTHESIS]`. All tested cells and failed gates will be reported. This study charges one confirmatory candidate cell and zero discovery cells.

---

END OF PRE-REGISTRATION. Results may be appended only below this line after the pre-registration SHA256 is recorded.
