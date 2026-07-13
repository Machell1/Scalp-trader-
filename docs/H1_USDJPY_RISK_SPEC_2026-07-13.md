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

## Results appended after the hash

Frozen-data verification: `verified 46 OK, 0 missing, 0 mismatched`.
[MEASURED: `python backtest/verify_data.py` @ branch `codex/h1-universe-admission`]

The Python reference and C# account kernel matched byte-for-byte on path 0 for
the paired control and every USDJPY risk policy. The screen used 20,000 common
path IDs and 117 common eligible moving blocks. The no-USDJPY paired control
was 77.1800% both-phases pass, 76.6882% Wilson lower, 0.3600% hard halt, and
22.4600% timeout. [MEASURED: `python -u backtest/run_h1_usdjpy_risk.py`]

| USDJPY dynamic risk | Both phases | Wilson lower | Hard halt | Timeout | Paired lower delta | Verdict |
|---:|---:|---:|---:|---:|---:|---|
| 0.05% | 85.7150% | 85.3032% | 0.3400% | 13.9450% | +7.5415 pp | PASS |
| 0.10% | 85.4650% | 85.0503% | 0.2350% | 14.3000% | +7.2977 pp | PASS |
| 0.15% | 85.1600% | 84.7418% | 0.2650% | 14.5750% | +6.9857 pp | PASS |
| 0.20% | 84.7600% | 84.3373% | 0.4250% | 14.8150% | +6.5836 pp | PASS |
| 0.25% | 83.7300% | 83.2962% | 0.7250% | 15.5450% | +5.5416 pp | PASS |

The frozen selector chose 0.05% because it had the highest both-phases point
estimate. [DERIVED: pre-registered ranking applied to the measured screen]

The selected 0.05% cell passed the 100,000-path confirmation: 85,474/100,000
both-phases passes = 85.4740%, one-sided 95% Wilson lower 85.2898%, hard halt
0.3700% (Wilson upper 0.4030%), timeout 14.1560%, phase-1 pass 92.2660%, and
phase-2 conditional pass 92.6387%. The paired no-USDJPY control was 76.8220%
both-phases pass, 76.6018% Wilson lower, 0.3700% hard halt, and 22.8080%
timeout. Exact paired counts were n10=19,854 and n01=11,202; the registered
paired lower delta was +8.2080 percentage points. Median and p90 completion
time among successful USDJPY paths were 676 and 1,090 days. All five gates
passed. [MEASURED: `python -u backtest/run_h1_usdjpy_risk.py`]

**Verdict: ADMIT USDJPY at 0.05% dynamic cash risk.** Keep US30.cash,
US100.cash, and JP225.cash at 0.30%; do not convert any symbol to fixed lots.
