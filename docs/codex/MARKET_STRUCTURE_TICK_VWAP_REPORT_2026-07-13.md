# Market-structure + candle/tick + VWAP screen

## Verdict

**KILLED — no FTMO confirmation and no EA change.**

[MEASURED: `python -u backtest/run_market_structure_tick_vwap.py` @ commit `5b42f27`]

The candidate used W2, market entry at the next M15 open, volume-weighted UTC
session VWAP, higher-low/lower-high structure, body/range >= 0.60, close
location >= 0.75/<=0.25, and current volume >= 1.20x the prior-20-bar median.
Exits were v1.30: 1ATR stop, 50% bank at +1R, TP2, eight-bar hold.

| Arm | Cost | Full N | Full exp | Full win | OOS N | OOS exp | OOS win |
|---|---|---:|---:|---:|---:|---:|---:|
| Market W2 control | measured | 5,620 | −0.040467R | 39.556% | 1,731 | +0.006858R | 41.305% |
| Market W2 control | 2x stress | 5,620 | −0.082259R | 39.395% | 1,731 | −0.035349R | 41.248% |
| Structure + candle + tick + VWAP | measured | 43 | −0.305311R | 27.907% | 18 | −0.331606R | 22.222% |
| Structure + candle + tick + VWAP | 2x stress | 43 | −0.357023R | 27.907% | 18 | −0.385434R | 22.222% |

Candidate per-symbol OOS expectancy at measured cost was Wall Street 30
`−0.407650R` (`N=4`), US Tech 100 `+0.142312R` (`N=3`), and Japan 225
`−0.433204R` (`N=11`). The candidate is killed by pooled OOS <= 0, negative
symbols, negative 2x stress, and insufficient trade frequency.

Conclusion: adding structure, candle quality, tick-volume expansion, and VWAP
to a market entry made the signal too sparse and worsened expectancy. It is
disposed of; the 88% FTMO target remains unsupported by the current entry tape.
