# v1.30 FTMO pass-policy micro-chunk execution — pre-registration

The 5,000-path chunks did not finish before an interactive task message caused
the host to terminate all child workers, leaving no checkpoint or outcome. This
execution-only repair reduces checkpoint granularity from 5,000 to 500 path IDs.
Two workers, total IDs 0..99,999, seed, policies, CRN, tapes, FTMO rules, costs,
gates and ledger remain unchanged. Monolithic/chunk equality is already a passing
synthetic invariant. New hypothesis charge zero; no blind/terminal access.

Registered command: `python -u backtest/run_v130_pass_policy.py --development`.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `PENDING`

