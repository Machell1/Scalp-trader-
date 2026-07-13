# v1.30 FTMO pass-policy deterministic chunk execution — pre-registration

The registered 100,000-path experiment is computationally non-viable as one
single-threaded, non-checkpointed call. No MC outcome has been exposed by prior
attempts. This repair changes execution only:

- add `path_start` to the MC engine; path IDs and bootstrap streams remain exact;
- execute deterministic 5,000-path chunks with two workers;
- concatenate and sort by original path ID;
- require byte-identical monolithic-vs-chunked synthetic output;
- print/checkpoint progress after every completed chunk.

Policies, 100,000 total path IDs (0..99,999), seed, CRN sharing, E1/E2 tapes,
FTMO rules, costs, gates and ledger are inherited unchanged. New hypothesis
charge zero. Confirmation/holdout/terminal writes remain denied.

Registered command: `python -u backtest/run_v130_pass_policy.py --development`.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `57f465900d0f0d04033f850d50802bac10d61c22276b48c8db43f40c074669b0`
