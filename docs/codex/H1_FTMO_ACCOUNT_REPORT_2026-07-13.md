# H1 FTMO account-level test

## Verdict

**Improves M15 but fails the 88% FTMO target and the completion-time gate.** No
EA change is authorized.

[MEASURED: `python -u backtest/check_h1_ftmo_csharp.py` @ commit `7e93f1b`]
Python and C# outputs matched exactly at path 0 for C0, C1, and P1 in both
E1/E2. The tape scheduler retained one US30/US100 cluster seat and two global
seats; accepted lifecycles were US30 `447`, US100 `273`, JP225 `454`.

[MEASURED: `python -u backtest/run_h1_ftmo_account.py` @ commit `389a1fe`]
The registered seed was `13020260711`, block length `20`, and `100,000` paths
per cost mode. E2 resumed from validated checkpoints after one exit-code-1
interruption at path `85,500`; no completed checkpoint was rerun.

| Cost mode | Policy | Both pass | Wilson lower | Hard halt | Timeout | Median success days | P90 success days |
|---|---:|---:|---:|---:|---:|---:|---:|
| E1 measured | C0 | 79.033% | 78.820% | 0.576% | 20.391% | 391 | 633 |
| E1 measured | C1 | 79.564% | 79.353% | 0.006% | 20.430% | 800 | 1,139 |
| E1 measured | P1 | 80.390% | 80.183% | 0.113% | 19.497% | 1,486 | 2,207 |
| E2 stress | C0 | 78.887% | 78.674% | 0.908% | 20.205% | 416 | 684 |
| E2 stress | C1 | 79.869% | 79.660% | 0.016% | 20.115% | 856 | 1,234 |
| E2 stress | P1 | 80.176% | 79.968% | 0.258% | 19.566% | 1,636 | 2,474 |

P1 versus C0 paired lower bounds were [MEASURED: same command @ `389a1fe`]
`+0.008998` E1 and `+0.008312` E2. P1 versus C1 was `+0.003714` E1 and
`−0.001473` E2. The stress P1 paired comparison therefore does not clear zero.

## Interpretation

The H1 timeframe raises the account pass estimate from the M15 P1 results of
76.052% E1 / 54.963% E2 to 80.390% E1 / 80.176% E2. That is a material
improvement, but it remains below the requested 88% target. The dominant
failure is timeout, not FTMO breach: roughly one-fifth of paths do not complete
within the registered 3,650-day phase ceilings, and P1 P90 completion exceeds
the 1,825-day gate in both cost modes.

This is a derived-H1 OHLC model, not a native H1 broker feed. It requires native
H1/forward validation before any timeframe change. The live EA remains M15;
there was no terminal access or EA modification.
