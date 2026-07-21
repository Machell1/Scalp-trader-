# v1.36-A1 execution-fidelity audit report

Date: 2026-07-20

Verdict: **AUDIT STOPPED — LIVE PARTIAL-LOG SCHEMA MISMATCH.**

The registered historical cells `C0_FROZEN_R_STEP`, `F1_PLACED_R_STEP`, and
`B1_PLACED_R_TP_FIRST` were not constructed or run. No account Monte Carlo
path was run and no candidate performance result was viewed. The registered
allocation of three confirmatory fidelity cells was therefore not consumed;
the conservative trial ledger remains at 300. [MEASURED: failed context
capture and no-result-file check @
`f1ff01fcab6c6bab6213b9653189795f8b73741f` plus capture-tool SHA256
`5d06691229c57672886f84d91b9ccb3a13bf5a44d0ed42d8cdd212d9d62edaa4`]

## Provenance

- Branch: `codex/v136-a1-fidelity-audit`.
- Parent main commit:
  `7c21153900b83e3253ee4c1713bf1913740b9b85`. [MEASURED: `git rev-parse
  origin/main` before branch creation @ `f1ff01f`]
- Pre-registration commit:
  `f1ff01fcab6c6bab6213b9653189795f8b73741f`. [MEASURED: `git rev-parse
  HEAD` @ `f1ff01f`]
- Registered spec SHA256:
  `c9992830199687dfd2cacc8ef5ac5f351fd32645d3df01d14a5dbb7e65fab620`.
  [MEASURED: `Get-FileHash docs\\V136_A1_EXECUTION_FIDELITY_SPEC_2026-07-20.md
  -Algorithm SHA256` @ `f1ff01f`]
- The sidecar and recomputed spec hash matched exactly after the failed
  capture. [MEASURED: `Get-FileHash ...` and `Get-Content
  docs\\V136_A1_EXECUTION_FIDELITY_SPEC_2026-07-20.sha256` @ `f1ff01f`]
- Capture-tool SHA256:
  `5d06691229c57672886f84d91b9ccb3a13bf5a44d0ed42d8cdd212d9d62edaa4`.
  The capture command ran from an uncommitted, subsequently preserved copy of
  this tool rooted at `f1ff01f`; this qualification is intentional and must
  not be shortened to “command at a clean commit.” [MEASURED: `Get-FileHash
  backtest\\capture_v136_a1_execution_context.py -Algorithm SHA256` @ dirty
  worktree rooted at `f1ff01f`]

## Completed controls before the stop

These controls completed before the failed context capture:

```text
verified 46 OK, 0 missing, 0 mismatched
```

[MEASURED: `python backtest/verify_data.py` @ `f1ff01f`]

```text
v130 pass-policy synthetic tests: 10 passed
```

[MEASURED: `python backtest/v130_pass_policy.py` @ `f1ff01f`]

The risk-policy output began with `V130_RISK_POLICY_SYNTHETIC`, printed 16
individual `PASS` lines, and ended with `PASS total=16`. [MEASURED: `python
backtest/v130_risk_policy.py --self-test` @ `f1ff01f`]

```text
V130_PASS_ADAPTER_SYNTHETIC passed=23
```

[MEASURED: `python backtest/v130_pass_adapter.py` @ `f1ff01f`]

The new read-only capture helper and its schema/identity/output guards passed
all 20 targeted offline tests before terminal access. [MEASURED: `python -m
pytest -q backtest/test_capture_v136_a1_execution_context.py` @ dirty
worktree rooted at `f1ff01f`; output `20 passed in 0.98s`]

Immediately before the capture, the documented FTMO executable was already
running as process 2700 at
`C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe`; a separate
MetaTrader installation was process 3868 and was not selected. [MEASURED:
`Get-CimInstance Win32_Process -Filter "Name = 'terminal64.exe'" | Select-Object
ProcessId,ExecutablePath,CommandLine` @ `f1ff01f`]

## Failed registered capture — verbatim

Command:

```powershell
python backtest\capture_v136_a1_execution_context.py --output backtest\v136_a1_execution_context_20260720.json --partials-csv "C:\Users\Sanique Richards\AppData\Roaming\MetaQuotes\Terminal\81A933A9AFC5DE3C23B15CAB19C63850\MQL5\Files\MomentumPullback_partials_v130.csv"
```

Output, verbatim:

```text
READ_JOURNAL [{"operation": "verify_terminal_executable", "status": "ok", "target": "C:\\Program Files\\FTMO Global Markets MT5 Terminal\\terminal64.exe", "utc": "2026-07-21T00:37:02.237Z"}, {"detail": {"timeout_ms": 30000}, "operation": "initialize", "status": "ok", "target": "C:\\Program Files\\FTMO Global Markets MT5 Terminal\\terminal64.exe", "utc": "2026-07-21T00:37:02.248Z"}, {"operation": "account_info", "status": "returned", "target": "account", "utc": "2026-07-21T00:37:02.248Z"}, {"operation": "terminal_info", "status": "returned", "target": "terminal", "utc": "2026-07-21T00:37:02.250Z"}, {"operation": "symbol_info", "status": "returned", "target": "US30.cash", "utc": "2026-07-21T00:37:02.252Z"}, {"operation": "symbol_info", "status": "returned", "target": "US100.cash", "utc": "2026-07-21T00:37:02.253Z"}, {"operation": "symbol_info", "status": "returned", "target": "JP225.cash", "utc": "2026-07-21T00:37:02.253Z"}, {"operation": "symbol_info", "status": "returned", "target": "USDJPY", "utc": "2026-07-21T00:37:02.253Z"}, {"operation": "shutdown", "status": "ok", "target": "MetaTrader5 API", "utc": "2026-07-21T00:37:02.253Z"}, {"detail": {"error_type": "ValidationError"}, "operation": "read_partial_csv", "status": "failed", "target": "external:MomentumPullback_partials_v130.csv", "utc": "2026-07-21T00:37:02.276Z"}]
ERROR: partial CSV missing required columns: ['trigger_tag']
```

[MEASURED: command above @ dirty worktree rooted at `f1ff01f`; capture-tool
SHA256 `5d06691229c57672886f84d91b9ccb3a13bf5a44d0ed42d8cdd212d9d62edaa4`]

The command returned exit code 1 and created no context JSON. [MEASURED:
capture command and `Test-Path
backtest\\v136_a1_execution_context_20260720.json` @ dirty worktree rooted at
`f1ff01f`; `False`]

## Meaning of the failure

The current v1.36-A1 source declares a 14-column partial-log header ending in
`trigger_tag`, but it writes the header only when the existing file size is
zero. An older nonempty file can therefore retain its legacy header after a
newer EA begins appending rows. [DERIVED: static source inspection of
`mql5/MomentumPullbackEA_v136_A1.mq5`]

That source behavior is a plausible explanation for the observed missing
column, but this audit does not reinterpret, repair, or reread the live file.
The registered capture treated the mismatch as invalid evidence and stopped.
[DERIVED]

No assertion can be made from this stopped run about whether placed-stop R is
materially better or worse than frozen-signal R, whether the 90.994% published
estimate changes, or whether A1+D1 improves v1.36-A1. [DERIVED]

## Access and change journal

The only MT5 API operations were `initialize`, `account_info`,
`terminal_info`, four `symbol_info` calls, and `shutdown`, in the order shown
in the verbatim journal. There were zero price-history calls, zero
position/order/deal queries, and zero trade requests. [MEASURED: static call
census plus the verbatim read journal @ dirty worktree rooted at `f1ff01f`]

No EA source, compiled EA, terminal file, chart, input, setting, order, or
position was changed. The partial CSV was opened read-only and was not altered.
The same FTMO process ID 2700 was present at the same executable before and
after the capture; no terminal process was started, restarted, or killed.
[MEASURED: capture-tool code, matching pre/post-capture running-process checks,
and read journal @ dirty worktree rooted at `f1ff01f`]

## Required next step

A separately hashed repair protocol should first define how to freeze and
parse both the legacy header and the newer 14-field row format without
silently shifting columns. It should use an offline copy/fixture of the exact
bytes before any second terminal connection. Only after that control passes
may the execution-fidelity cells be preregistered again. [HYPOTHESIS]
