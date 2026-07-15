# Short-only v1.31 counterfactual — sealed FTMO holdout result

## Verdict

**DISPOSED.** S1 short-only failed the pre-registered E2 positivity and final
complete-quarter gates. No account Monte Carlo, EA edit, basket change, or
FTMO terminal write is authorized by this result.

## Provenance

- Protocol SHA256: `8b4e81360ed37631933785eb09ce9510aa7f94687987ea14a79ac81d0df51b0a`.
- Frozen input verification printed: `verified FTMO blind freeze 9 OK, 0
  missing, 0 mismatched, 0 extra`.
- Frame: sealed FTMO M15 `holdout` slice; US30.cash, US100.cash, JP225.cash;
  same C1/live scheduler, capacity rules, and exits as the control.
- [MEASURED: `python backtest/run_short_only_counterfactual.py` @ `e00db76`]

## Complete cells

| Mode | Cell | Trades | Expectancy R | Total R | Win rate | Delta vs C0 |
|---|---|---:|---:|---:|---:|---:|
| E1 measured | C0 both-sides | 2,016 | -0.05345 | -107.75 | 37.80% | — |
| E1 measured | S1 short-only | 1,205 | -0.01464 | -17.64 | 39.00% | +0.03881 |
| E2 2× broker-cost stress | C0 both-sides | 2,015 | -0.17532 | -353.26 | 35.93% | — |
| E2 2× broker-cost stress | S1 short-only | 1,210 | -0.17158 | -207.61 | 35.79% | +0.00374 |

S1 emitted zero long trades in both modes. Its E2 final complete quarter was
2023Q3 at **-0.15213R** over 177 trades. It is therefore not an edge, even
though it was marginally less negative than the control on that stress frame.

### E2 short-only per symbol

| Symbol | Trades | Expectancy R | Total R |
|---|---:|---:|---:|
| JP225.cash | 459 | -0.38898 | -178.54 |
| US100.cash | 290 | -0.01487 | -4.31 |
| US30.cash | 461 | -0.05369 | -24.75 |

## Interpretation

[DERIVED] The earlier Deriv directional advantage did not transfer to the
unopened broker-native FTMO holdout. It is not evidence for a short-only live
variant. The recorded result JSON contains the full trade, quarterly, side,
and event-tape details.
