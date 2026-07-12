# v1.30 FTMO pass-policy MC restart 3 — pre-registration

The repair-2 execution passed every preflight and both E1/E2 edge gates, printed
`MC_START mode=E1_MEASURED paths=100000`, then its worker was terminated by the
Codex task transition. It wrote no JSON/NPZ artifact and exposed no MC outcome.

This restart inherits without change every policy, seed, path count, block rule,
cost mode, FTMO rule, Wilson/paired gate, timeout, edge gate, data freeze and
ledger term from:

- original protocol `0bccf0057f65b30e70a3b70663476ecadf6348efaee5aa366f3e235a3dfad671`;
- boundary repair actual prefix `486bc9ae857332f29dbe1bb434399d3baeaaa0e3938f6e338ddb22bab05bc4b3`;
- repair-2 prefix `fa63f652cb5dbe5005bba23b48756fccdb5f2819949fa476bbc4e387d016138c`.

Registered command: `python -u backtest/run_v130_pass_policy.py --development`.
Outputs are restart-specific and may not overwrite earlier names. This is the
same already-charged C1/P1 development measurement; new hypothesis charge zero.
No confirmation/holdout or terminal write is authorized.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `PENDING`

