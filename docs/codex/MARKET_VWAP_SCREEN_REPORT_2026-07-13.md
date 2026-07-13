# Market-entry VWAP discount/premium screen

## Verdict

**KILLED — no FTMO confirmation cell and no EA change.** The market-at-next-open
entry with a causal session VWAP discount/premium gate failed the preregistered
OOS and stress gates.

[MEASURED: `python backtest/verify_data.py` @ commit `3366758`]

```text
verified 46 OK, 0 missing, 0 mismatched
```

[MEASURED: `python -u backtest/run_market_vwap_screen.py` @ commit `37109df`]

Protocol: W2 `watr >= 0.30`, market entry at next M15 open, UTC session VWAP
using the supplied `volume` column, eight-bar calibration, long close <= VWAP,
short close >= VWAP, 1ATR stop, 3ATR target, eight-bar hold, real per-side cost.
The pending-limit control used the same signal and bracket.

| Arm | Cost | N | Full expectancy | Full win rate | OOS N | OOS expectancy | OOS win rate |
|---|---|---:|---:|---:|---:|---:|---:|
| Pending W2 control | measured | 3,664 | −0.011861R | 34.307% | 1,075 | +0.015380R | 35.442% |
| Pending W2 control | 2× stress | 3,664 | −0.053339R | 33.679% | 1,075 | −0.026696R | 34.698% |
| Market + VWAP | measured | 382 | −0.119363R | 30.628% | 132 | −0.132224R | 31.061% |
| Market + VWAP | 2× stress | 382 | −0.165667R | 30.628% | 132 | −0.177554R | 31.061% |

Per-symbol OOS expectancy for market+VWAP was [MEASURED: same command @
`37109df`]: Wall Street 30 `+0.037536R` (`N=34`), US Tech 100 `−0.023452R`
(`N=43`), and Japan 225 `−0.322205R` (`N=55`). Under 2× cost the values were
`+0.004886R`, `−0.047807R`, and `−0.391773R`, respectively.

The two failed runner invocations were recorded verbatim in the preregistration:
the first stopped at `ValueError: too many values to unpack (expected 2)` and
the second at `ValueError: 'Wall_Street_30' is not in list`; neither emitted a
result. They were wiring fixes only and did not change the frozen cell.

Conclusion: VWAP discount/premium plus market execution reduces the sample to
382 trades and loses the edge out of sample. The idea is disposed of under the
kill gates; pursuing the 88% FTMO target requires a different, preregistered
entry hypothesis rather than deploying this arm.
