# H1 v1.30 timeframe screen — pre-registration

## Question

Does running the unchanged W2 momentum-pullback strategy on causal H1 bars
improve out-of-sample expectancy enough to justify an FTMO account-level test?

## Frozen protocol

* Source is the frozen FTMO trio of M15 CSVs: `Wall_Street_30`, `US_Tech_100`,
  and `Japan_225` from `derivM15_spreadgated`. Run
  `python backtest/verify_data.py` immediately before the cell.
* Aggregate only complete contiguous four-bar UTC hours. H1 open is the first
  M15 open, high/low are extrema, close is the last M15 close, volume is the
  sum, and spread_price is the maximum of the four source spreads. Incomplete
  hours are discarded; no API data is allowed.
* Keep signal geometry unchanged: continuation momentum lookback 6 H1 bars,
  threshold 2 ATR, Wilder ATR(14), W2 adverse-wick threshold 0.30, buy/sell
  limit offset 0.6 ATR, three-bar pending window, one-symbol occupancy.
* Keep v1.30 exits unchanged: 1ATR stop, 50% bank at +1R, TP2.0, eight-bar
  maximum hold, stop-first ordering, measured cost and 2x-cost stress.
* Chronological 70/30 OOS split is applied after aggregation. Report every
  symbol, pooled/full and OOS expectancy, win rate, trade count, and stress.

Kill gates: pooled OOS <= 0, any symbol OOS <= 0, or pooled 2x-cost OOS <= 0.
A surviving screen is exploratory only and requires a new 100,000-path FTMO
account specification; no EA change follows from this cell.

Ledger charge proposed: one H1 timeframe cell and its pending control. No API
refresh, terminal access, or live deployment.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `2c990c6662a411c4e20f9fd0fc371da6c1149b63abff9889c0407709cd912b87`
