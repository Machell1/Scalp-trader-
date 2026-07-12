# v1.30 FTMO pass-policy C# kernel repair — pre-registration

Both object-level Python and Numba execution proved infeasible on this host.
The built-in Windows 64-bit .NET Framework C# compiler is available at
`C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe`.

Implement the same primitive-array state machine registered in the Numba spec
as a C# executable. Python remains responsible for the canonical tape adapter,
the existing `CompiledBootstrap.source_indices` RNG streams, and conversion to
the unchanged `RESULT_DTYPE`. For each checkpoint chunk, Python writes primitive
tape, broker metadata, policies, and the exact source-index matrix to a binary
input; the executable writes fixed-width integer and IEEE-754 double results.
No C# RNG is permitted. Compile without unsafe arithmetic or floating-point
relaxation.

Frozen: 100,000 IDs 0..99,999; seed 13020260711; 20-day moving blocks; C0/C1/P1;
CRN; E1/E2 tapes and costs; two-stop equity; FTMO/EA parameters; output schema;
all Wilson, timeout, completion-time, paired and divergence gates; ledger 211;
development only. No strategy, data, risk, bootstrap, output, or gate change.

Equivalence gate before full execution: both E1 and E2, path IDs 0 and 137,
all three policies, every `RESULT_DTYPE` field, including byte-identical doubles.
Any mismatch stops execution and is reported. Existing golden and synthetic
preflight remains mandatory. Full command remains
`python -u backtest/run_v130_pass_policy.py --development`.

Hypothesis charge: zero. No blind-frame unlock or trading-terminal access.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `13f771393bc9de6b47760be7dc4c25492bdceb9f3aa0ddd7a17fc5aef78774f8`
