# v1.30 FTMO pass-policy repair 2 — registration correction

This is a bookkeeping repair of `docs/V130_FTMO_PASS_POLICY_REPAIR_SPEC_2026-07-12.md`.
That repair stopped before MC because its recorded hash was truncated by one byte.
No policy, data, engine, seed, or hypothesis changes are authorized. The exact
same development command is rerun only after this protocol is committed.

Original protocol hash: `0bccf0057f65b30e70a3b70663476ecadf6348efaee5aa366f3e235a3dfad671`
Repair-1 actual prefix hash: `486bc9ae857332f29dbe1bb434399d3baeaaa0e3938f6e338ddb22bab05bc4b3`
No new ledger charge; this is a registration correction for the same charged cells.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `fa63f652cb5dbe5005bba23b48756fccdb5f2819949fa476bbc4e387d016138c`

## Execution record

The registered command passed every preflight check, both E1/E2 weighted edge
gates, and printed `MC_START mode=E1_MEASURED paths=100000`. The worker later
terminated during the surrounding Codex task transition without a terminal
result line and without writing either registered result artifact. Therefore
zero MC outcome cells are reported from this execution and no pass probability
is inferred. This is an infrastructure interruption, not a measured strategy
failure or success.
