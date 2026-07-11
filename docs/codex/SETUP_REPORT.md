# Codex Setup Verification Report

## Contributor

- Date: `2026-07-11` `[MEASURED: Get-Date -Format 'yyyy-MM-dd' @ c212fd12a2cbbc453a1f975a6033fe9e8018089b]`
- Model/version: `[HYPOTHESIS]` GPT Codex 5.6, using the owner-specified contributor designation; the workspace does not expose an independently verifiable runtime build identifier.
- Verification base commit: `c212fd12a2cbbc453a1f975a6033fe9e8018089b`

Before running any command in the repository, I read `CODEX_CONSTITUTION.md`, the `LIVE STATE`, `Rules for changes`, and dead-ends sections of `README.md`, and the current `docs/*SPEC*.md` files.

## Main update and pinned-data verification

`[MEASURED: git pull origin main @ c212fd12a2cbbc453a1f975a6033fe9e8018089b]`

```text
From https://github.com/Machell1/Scalp-trader-
 * branch            main       -> FETCH_HEAD
Already up to date.
```

`[MEASURED: python backtest/verify_data.py @ c212fd12a2cbbc453a1f975a6033fe9e8018089b]`

```text
verified 46 OK, 0 missing, 0 mismatched
```

## Environment verification

### Python scientific dependencies

Command:

```powershell
python -c "import numpy, pandas, scipy; print('py deps OK')"
```

`[MEASURED: python -c "import numpy, pandas, scipy; print('py deps OK')" @ c212fd12a2cbbc453a1f975a6033fe9e8018089b]`

```text
py deps OK
```

### MetaTrader5 package import

Command:

```powershell
python -c "import MetaTrader5; print('mt5 pkg OK')"
```

`[MEASURED: python -c "import MetaTrader5; print('mt5 pkg OK')" @ c212fd12a2cbbc453a1f975a6033fe9e8018089b]`

```text
mt5 pkg OK
```

This check imported the package only. It did not initialize, launch, or operate any terminal.

### Canonical dataset counts

Command:

```powershell
$spread = @(Get-ChildItem -LiteralPath 'backtest\data\derivM15_spreadgated' -File -Filter '*.csv')
$diverse = @(Get-ChildItem -LiteralPath 'backtest\data\derivM15_diverse' -File -Filter '*.csv')
Write-Output "backtest/data/derivM15_spreadgated/: $($spread.Count) CSVs"
Write-Output "backtest/data/derivM15_diverse/: $($diverse.Count) CSVs"
if ($spread.Count -ne 12 -or $diverse.Count -ne 29) { exit 1 }
```

`[MEASURED: PowerShell canonical dataset-count command reproduced above @ c212fd12a2cbbc453a1f975a6033fe9e8018089b]`

```text
backtest/data/derivM15_spreadgated/: 12 CSVs
backtest/data/derivM15_diverse/: 29 CSVs
```

### Backtest harness imports

Working directory: `backtest/`

Command:

```powershell
python -c "import scalper_backtest, walkforward_dsr; print('harness OK')"
```

`[MEASURED: python -c "import scalper_backtest, walkforward_dsr; print('harness OK')" (workdir=backtest/) @ c212fd12a2cbbc453a1f975a6033fe9e8018089b]`

```text
harness OK
```

### GitHub CLI availability

`[MEASURED: gh --version @ c212fd12a2cbbc453a1f975a6033fe9e8018089b]`

```text
gh version 2.90.0 (2026-04-16)
https://github.com/cli/cli/releases/tag/v2.90.0
```

### GitHub authentication and repository reachability

`[MEASURED: gh auth status @ c212fd12a2cbbc453a1f975a6033fe9e8018089b]`

```text
github.com
  ✓ Logged in to github.com account Machell1 (keyring)
  - Active account: true
  - Git operations protocol: https
  - Token: gho_************************************
  - Token scopes: 'delete_repo', 'gist', 'read:org', 'repo', 'workflow'
```

Repository reachability was also demonstrated by the successful `git pull origin main` output reproduced above.

## Obligations under Articles I-IV

I will work only on a one-topic `codex/<topic>` branch created from fresh `main`, and changes will reach `main` only through a pull request merged by the human owner; I will never commit or push to `main`, alter protections, settings, workflows, or history, or merge, approve, or close my own pull request. I will use only executed and provenance-cited results, label derived claims and hypotheses, preserve failures verbatim, keep the pinned datasets unchanged, and report every experimental cell. Before research I will pre-register and SHA256-hash the exact hypothesis, mechanization, cells, controls, and gates, append results only below the hash, charge every tested cell to the binding ledger, and reject post-hoc flips or documented dead ends. The specified FTMO terminal, account state, deployed MomentumPullbackEA, magic, inputs, positions, orders, processes, and data folder are read-only and untouchable: permitted access is limited to approved reads, and I will never place, modify, or close an order, change terminal or EA state, install or copy files, compile or attach anything, or start, restart, or kill the terminal.

`[DERIVED]` Trial-ledger increment: 0; this bootstrap performed no research or experimental cells.

Article compliance: setup verification only; no research, strategy change, live-terminal access, repository-setting change, or deployment occurred.

I acknowledge that work produced outside the constitution is discarded unreviewed.
