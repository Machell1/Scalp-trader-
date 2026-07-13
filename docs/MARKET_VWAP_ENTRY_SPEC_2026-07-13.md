# Market-entry VWAP discount/premium screen — pre-registration

## Question

Does replacing the validated pullback-limit entry with a market entry at the
next M15 bar open, while requiring buys below a causal session VWAP and sells
above it, improve realizable expectancy and FTMO pass prospects?

## Frozen protocol

* Primary frame: the three FTMO symbols in
  `backtest/data/derivM15_spreadgated/`: `Wall_Street_30`, `US_Tech_100`, and
  `Japan_225`. The canonical data verification must be run immediately before
  the cell: `python backtest/verify_data.py`.
* Signal: the existing continuation momentum signal and W2 adverse-wick gate
  (`watr >= 0.30`) from `retest_engine.py`; no signal or exit redesign.
* Entry arm: market order at the next bar open, with the frozen spread/cost
  model. There is no pending order, fill window, or pending occupancy for this
  arm.
* VWAP: session-anchored cumulative typical-price VWAP, reset at each UTC
  calendar day because the frozen files have timezone-naive UTC timestamps;
  weights are the supplied CSV `volume` column. VWAP uses bars through the
  signal close only. The first eight bars of each session are ineligible.
* Discount/premium: long signals require `close <= VWAP`; short signals require
  `close >= VWAP`. Equality is included and is not a tunable boundary.
* Exit: the existing live-parity bracket, 1.0 ATR stop, 3.0 ATR target,
  eight-bar maximum hold, stop-first intrabar ordering, and actual per-side
  cost. No partial close, lock, or trail is added in this cell.
* Comparison: the pre-existing W2 pullback-limit cell under the same frame,
  cost, signal, and exit rules. Report every symbol, pooled IS/OOS, OOS
  expectancy, win rate, trade count, fill rate, and 2x-cost stress. This is an
  exploratory entry cell, not a promotion or FTMO confirmation.

## Kill gates

The market+VWAP cell is killed if pooled OOS expectancy is non-positive, any
symbol OOS expectancy is negative, or its 2x-cost pooled OOS expectancy is
non-positive. A positive screen does not authorize EA changes; it requires a
new account-level preregistration and owner review.

Ledger charge proposed: one exploratory entry cell, with the pending-limit arm
as a control. No API refresh, terminal access, or live deployment.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `4750df93e80cab40a44206277dfa28ac9babb974a4f40bba22164b13a6609051`
