# v1.30 FTMO pass-policy C# path-parallel repair — pre-registration

The exact C# kernel produced a 500-path checkpoint in about three minutes.
Independent path/policy simulations will be dispatched with .NET `Parallel.For`
into a preallocated result matrix, then written sequentially in original path
and policy order. Thread count uses the host runtime default. No shared mutable
simulation state is allowed; the immutable tape/source arrays are read-only.

Frozen: all data, path IDs, seed, source streams, policies, rules, costs,
`RESULT_DTYPE`, gates, 500-path checkpoint boundaries, ledger 211, and
development-only scope. Existing checkpoints are reused only after path-ID
validation. Rerun the exact Python/C# gate for E1/E2 IDs 0/137 before resuming.
Any mismatch stops. Hypothesis charge zero; no blind or terminal access.

Full command remains `python -u backtest/run_v130_pass_policy.py --development`.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `f364738910824cc5bf249a9958d8ad25a3defced2e881b7af31ecb889d896465`
