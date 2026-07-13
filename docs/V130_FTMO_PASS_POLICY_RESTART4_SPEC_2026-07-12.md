# v1.30 FTMO pass-policy detached-host restart 4 — pre-registration

Restart 3 was terminated by the attached execution host during E1 MC without an
outcome or artifact. This restart inherits every original/repair/restart policy,
seed, 100,000-path count, cost mode, block rule, gate, data freeze and ledger term
unchanged. The sole operational change is launching the exact registered command
as a hidden detached process with stdout/stderr redirected to immutable attempt
logs, preventing the interactive execution host from terminating the worker.

Command executed by the detached process:
`python -u backtest/run_v130_pass_policy.py --development`.

New hypothesis charge zero. Confirmation, holdout and terminal writes denied.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `1780c9886bfb9ff74f8d368bebbe957384ddbec08b0d5d186bb55b74d848b2fd`
