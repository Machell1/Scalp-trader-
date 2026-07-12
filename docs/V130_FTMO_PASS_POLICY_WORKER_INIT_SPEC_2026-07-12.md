# v1.30 FTMO pass-policy worker-initializer repair — pre-registration

The micro-chunk execution reached the measured-cost MC start but created no
checkpoint in ten minutes. Code inspection found that every queued chunk sends
the same full compiled tape and symbol metadata through the Windows process-pool
serialization boundary. This repair will initialize each of two workers with
the immutable tape and metadata once, then submit only `(start, count)` path-ID
ranges. The parent will keep at most the registered chunks as ordinary work
items; checkpoint files remain keyed by mode and starting path ID.

Frozen: 100,000 path IDs 0..99,999; seed 13020260711; 20-day moving blocks;
policies C0/C1/P1; common random numbers; E1/E2 tapes and costs; two-stop equity;
FTMO and EA rules; Wilson, timeout, completion-time, paired-delta and divergence
gates; ledger 211; development-only exposure. No strategy, risk, data, bootstrap,
outcome, or gate change is allowed.

Before the full run, add a deterministic synthetic invariant comparing worker-
initialized chunk output with direct `run_monte_carlo` output for the same path
IDs byte-for-byte. Failure stops execution. The full registered command remains
`python -u backtest/run_v130_pass_policy.py --development`.

Hypothesis charge: zero. This changes execution transport only and yields no new
policy cell. No blind frame or trading terminal access is permitted.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `0db2f86fb5dd791ff0d27afbc536ccdddd326005e38ea9c6689356d3448c43f6`
