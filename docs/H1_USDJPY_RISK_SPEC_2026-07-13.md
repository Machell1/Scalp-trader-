# H1 USDJPY dynamic-risk sleeve — pre-registration

## Trigger and question

The full predeclared universe screen found only one account-level near-miss:
adding USDJPY at the same 0.30% risk produced a 20,000-path E2 pass estimate of
82.225%, Wilson lower 81.776%, positive paired lower delta, and lower timeout,
but a 1.520% hard-halt rate exceeded the frozen 1% safety gate.

Can a smaller dynamic cash-risk allocation for USDJPY preserve an expanded
portfolio above the owner's amended 78.887% stress threshold while bringing
hard halts to 1% or less? This changes position sizing only. Entries, exits,
H1 construction, symbols, costs, cluster/global caps, and the 0.30% allocation
for US30/US100/JP225 remain frozen.

## Cells and frozen method

USDJPY phase-1 and phase-2 risk are tested symmetrically at exactly 0.05%,
0.10%, 0.15%, 0.20%, and 0.25%. The already-observed 0.30% cell is the frozen
control and is not rerun as a new discovery cell. Use the identical E2 USDJPY
portfolio tape, FTMO metadata snapshot, seed 13020260711, 20-day common moving
blocks, two sequential phases, and 20,000 common path IDs. The three existing
symbols remain 0.30% in both phases.

Python and C# must match exactly at path 0 for every policy. Report all cells.
A screen cell passes only if:

1. both-phases point estimate is at least 78.887%;
2. one-sided 95% Wilson lower bound is at least 78.887%;
3. exact paired one-sided 95% lower delta versus the no-USDJPY control is above zero;
4. hard-halt probability is at most 1%; and
5. timeout probability is no higher than the paired control.

Among screen passers, select the highest both-phases point estimate; ties go to
the lower USDJPY risk. Confirm that one cell on 100,000 common E2 paths with the
same gates. A failed confirmation means no USDJPY admission and no further risk
levels or filters are tried.

If the confirmation passes, implementation may add a deterministic per-symbol
risk override for USDJPY while retaining the global 0.30% default, compile 0/0,
and deploy only on a flat FTMO account with graceful restart and verified H1
init output. No other candidate is revived by this test.

Ledger charge: five predeclared USDJPY risk cells and one conditional 100,000-path
confirmation.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `63e68c3a6b420638d93609473864049c6bccfae3d40b3982a18632a9bf61d6b1`
