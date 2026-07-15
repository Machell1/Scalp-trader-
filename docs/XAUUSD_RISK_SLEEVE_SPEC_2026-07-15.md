# H1 XAUUSD dynamic-risk sleeve — pre-registration (2026-07-15)

## Trigger and question

The owner asked whether XAUUSD can join the deployed book (prompted by generic
"loosen your filters for gold" advice; the correct diagnosis is recorded here).
The predeclared universe screen already answered the entry question: XAUUSD
PASSED the causal per-symbol Stage A gate with the best E2 OOS expectancy of
the five passers (+0.110202R on 107 trades) — the v1.31 signal engine does not
need loosening to see gold. It failed Stage B at equal 0.30% risk: 71.795%
both-phases (vs 78.887% control), hard halt 10.425% (gate: 1%), paired lower
delta -5.2420 pp.

Question: does a SMALL dynamic cash-risk sleeve for XAUUSD — the same door
USDJPY was admitted through — improve the DEPLOYED v1.31 portfolio? This
changes position sizing only. Entries, exits, H1 construction, costs,
cluster/global caps, and all deployed allocations remain frozen.

Honest prior, recorded before results: USDJPY entered its sleeve study with a
POSITIVE paired delta (+4.02 pp) needing only hard-halt taming; XAUUSD enters
with a NEGATIVE paired delta at 0.30%, so the sleeve must flip the sign, not
just calm the tails. Expected outcome is NO_ADMISSION.

## Cells and frozen method

* Control: the deployed v1.31 configuration — US30.cash, US100.cash,
  JP225.cash at 0.30% and USDJPY at 0.05% in both phases. This control IS
  rerun on the common paths (it has not previously been run as a 5-symbol
  tape/portfolio cell).
* Candidate cells: XAUUSD phase-1 and phase-2 risk symmetric at exactly
  0.05%, 0.10%, 0.15%, 0.20%, 0.25%; all deployed allocations unchanged.
  The already-observed 0.30% equal-risk cell is historical context, not rerun.
* Identical machinery to the USDJPY sleeve study: E2 double-cost tapes via
  `build_h1_universe_tape`, frozen FTMO metadata snapshot (SHA256
  `ba1f3cde...`), seed 13020260711, 20-day common moving blocks, two
  sequential FTMO phases, 20,000 common path IDs for the screen, chunked C#
  kernel with Python/C# exact path-0 match required for every policy,
  `verify_data.py` must print `verified 46 OK, 0 missing, 0 mismatched`.
* XAUUSD sits in the metals cluster (currently empty seat); with USDJPY it is
  the second and final global candidate seat — within the registered
  one-per-cluster / two-global rule.

A screen cell passes only if ALL of:

1. both-phases point estimate at least 78.887% (the owner's standing amended
   stress threshold);
2. one-sided 95% Wilson lower bound at least 78.887%;
3. exact paired one-sided 95% lower delta versus the DEPLOYED control above
   zero;
4. hard-halt probability at most 1%; and
5. timeout probability no higher than the paired control.

Among screen passers, select the highest both-phases point estimate; ties go
to the lower XAUUSD risk. Confirm that one cell on 100,000 common E2 paths
with the same gates. A failed confirmation means no XAUUSD admission and no
further risk levels, filters, indicator changes ("21 EMA", "short RSI",
"DXY filter", CHoCH entries), or timeframe variants are tried for gold on this
data. A passed confirmation is a v1.32 build PROPOSAL for the owner, not an
auto-deployment.

Ledger charge: five predeclared XAUUSD risk cells and one conditional
100,000-path confirmation.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `5170da78961ac538c774196e2b061174c48d9d9b1d31fa6b423071e98f1ee4b2`

## Results appended after the hash

Frozen-data verification: `verified 46 OK, 0 missing, 0 mismatched`.
[MEASURED: `python backtest/verify_data.py` @ `3efe9fa`]

The Python reference and C# account kernel matched byte-for-byte on path 0 for
the deployed control and every XAUUSD risk policy. The screen used 20,000
common path IDs and 116 common eligible moving blocks. The deployed-v1.31
paired control measured 82.1350% both-phases pass, 81.6851% Wilson lower,
0.2150% hard halt, and 17.6500% timeout on the common paths.
[MEASURED: `python -u backtest/run_h1_xauusd_risk.py`]

| XAUUSD dynamic risk | Both phases | Wilson lower | Hard halt | Timeout | Paired lower delta | Verdict |
|---:|---:|---:|---:|---:|---:|---|
| 0.05% | 81.2650% | 80.8070% | 0.1100% | 18.6250% | -1.8647 pp | FAIL |
| 0.10% | 78.6800% | 78.1998% | 0.4050% | 20.9150% | -4.4787 pp | FAIL |
| 0.15% | 76.4900% | 75.9932% | 1.2500% | 22.2600% | -6.6716 pp | FAIL |
| 0.20% | 72.8450% | 72.3246% | 3.6400% | 23.5150% | -10.3398 pp | FAIL |
| 0.25% | 68.4050% | 67.8618% | 7.9050% | 23.6900% | -14.8008 pp | FAIL |

No screen cell passed; the 100,000-path confirmation did not run.
[MEASURED: `backtest/h1_xauusd_risk_results.json`]

**Verdict: NO_ADMISSION.** The paired delta never approaches zero — even the
smallest sleeve (0.05%) makes the deployed book worse (-1.86 pp lower bound),
and degradation is monotonic in size. The pre-registered prior held: gold's
per-symbol expectancy (+0.110R OOS, best of the universe passers) does not
survive account-level integration at ANY size — its tail profile consumes more
pass probability through halts and timeouts than its expectancy contributes.
Per the pre-registration, XAUUSD is closed on this data: no further risk
levels, filters, indicator changes, or timeframe variants.
