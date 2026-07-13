# v1.30 FTMO pass-policy status

## Outcome

The registered two-phase account simulation did **not** reach the requested 88%
pass rate. The measured-cost result for the best registered policy, P1, is
76.052% with a 75.829% one-sided Wilson lower bound. The stress-cost result is
54.963% with a 54.704% lower bound. The runner verdict is
`KILLED_AT_MC_GATE`.

All values below are [MEASURED: `python -u backtest/run_v130_pass_policy.py
--development` @ commit `1b763b9`], using the frozen 46-file data, seed
13020260711, 20-day moving blocks, 100,000 paths per mode, sequential Challenge
then Verification phases, and the exact C# kernel gates validated at path IDs 0
and 137 for E1/E2.

| Cost mode | Policy | Both-pass | Wilson lower | Hard halt | Timeout | Median success days | P90 success days |
|---|---:|---:|---:|---:|---:|---:|---:|
| E1 measured | C0 | 36.837% | 36.586% | 54.319% | 8.844% | 225 | 402 |
| E1 measured | C1 | 60.636% | 60.382% | 26.653% | 12.711% | 749 | 1,392 |
| E1 measured | P1 | 76.052% | 75.829% | 7.917% | 16.031% | 805 | 1,357 |
| E2 stress | C0 | 16.448% | 16.256% | 78.834% | 4.718% | 235 | 422 |
| E2 stress | C1 | 23.281% | 23.062% | 70.561% | 6.158% | 1,031 | 2,128 |
| E2 stress | P1 | 54.963% | 54.704% | 32.752% | 12.285% | 1,204 | 2,268 |

The ledger remained at cell 211: [MEASURED: result JSON @ commit `1b763b9`]
`start=211`, `end=211`, `charged_cells=[repair_same_development_cells]`.

The positive control deltas were [MEASURED: same command @ commit `1b763b9`]:
P1 versus C0 paired lower `+0.3874965856` in E1 and `+0.3808724074` in E2;
P1 versus C1 paired lower `+0.1494690596` in E1 and `+0.3125425704` in E2.
There were zero lot-rejection, minimum-lot-substitution, and partial-rounding
divergences in every policy/mode cell.

## Exploratory risk screen

The preregistered screen in
`docs/V130_FTMO_PASS_RISK_SCREEN_SPEC_2026-07-13.md` tested only risk
allocation, not entries. It used 10,000 paths per mode. Each C# result matched
the Python reference at path 0 for all three candidates. [MEASURED: `python -u
backtest/run_v130_pass_risk_screen.py` @ commit `82a3866`]

| Mode | Candidate | Both-pass | Wilson lower | Hard halt | Timeout | P90 success days | Screen result |
|---|---:|---:|---:|---:|---:|---:|---|
| E1 measured | R4 | 51.190% | 50.368% | 36.390% | 12.420% | 575 | KILLED |
| E1 measured | R3 | 62.620% | 61.821% | 22.580% | 14.800% | 822 | KILLED |
| E1 measured | R5 | 41.940% | 41.131% | 47.640% | 10.420% | 398 | KILLED |
| E2 stress | R4 | 33.550% | 32.778% | 57.550% | 8.900% | 720 | KILLED |
| E2 stress | R3 | 42.690% | 41.878% | 46.090% | 11.220% | 1,180 | KILLED |
| E2 stress | R5 | 27.960% | 27.228% | 64.600% | 7.440% | 484 | KILLED |

## Finding

Changing account risk alone cannot produce an 88% FTMO pass probability on this
frozen entry tape. Higher risk accelerates target attainment but raises hard
halts; lower risk reduces hard halts but times out before the target. The stress
edge is only `+0.0173443000R` pooled and US30 expectancy is `-0.0320216954R`.
Therefore no v1.30 risk policy is promoted, no terminal was accessed, and no EA
or entry rule was changed. Reaching 88% requires a separately preregistered
improvement to entry expectancy/robustness or a change to the account objective;
claiming 88% from the current tape would be unsupported.
