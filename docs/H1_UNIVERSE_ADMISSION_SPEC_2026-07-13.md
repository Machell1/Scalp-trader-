# H1 v1.30 FTMO universe admission — pre-registration

## Decision question

Can additional FTMO symbols improve the deployed H1 v1.30 portfolio while the
uniform dynamic risk remains **0.30% of current balance per filled trade**, and
raise the two-phase pass probability to at least 80% under the registered E2
double-cost stress?

The fixed-lot proposal is withdrawn. The EA will continue to convert the same
0.30% cash-risk budget into broker-valid volume from each symbol's frozen ATR
stop, tick value, minimum volume, and volume step.

## Baseline correction

The previously quoted 80.176% E2 result is the symbol-specific lower-risk P1
policy. It is not the live uniform-risk setting. The deployed 0.30% configuration
is C0: 78.887% E2 both-phases pass probability, with 78.6739% Wilson lower bound,
0.908% hard halt, and 20.205% timeout in the existing 100,000-path result.
This study must reproduce the C0 control before comparing any expansion.

## Frozen inputs

* Run `python backtest/verify_data.py`; any result other than
  `verified 46 OK, 0 missing, 0 mismatched` stops the study.
* Price data are only the manifest-pinned M15 CSVs in
  `derivM15_spreadgated` and `derivM15_diverse`. Duplicate source symbols use
  `derivM15_spreadgated` first. No price refresh or API bars are allowed.
* Broker metadata are frozen in `backtest/h1_universe_broker_meta.json`, SHA256
  `ba1f3cdeaca429764129685f79a4267e1bbc55b2fead70c8187db431fd828928`, captured
  read-only from FTMO account 1513946641 on terminal build 5836.
* Commission rules are frozen before outcomes: FTMO indices zero commission;
  FX, metals, and commodities use USD 2.50 per side per lot; crypto uses
  0.0325% of notional per side. The FX and index rules are from FTMO's current
  symbol specifications; the crypto rate is FTMO's published July-2025 model.

## Candidate universe

The live control is `US30.cash`, `US100.cash`, and `JP225.cash`. Every other
manifest symbol with an exact FTMO twin is tested once (30 cells):

`US500.cash`, `US2000.cash`, `GER40.cash`, `FRA40.cash`, `UK100.cash`,
`AUS200.cash`, `HK50.cash`, `NATGAS.cash`, `UKOIL.cash`, `USOIL.cash`,
`AUDJPY`, `EURGBP`, `EURJPY`, `EURUSD`, `GBPJPY`, `GBPUSD`, `NZDUSD`,
`USDCAD`, `USDCHF`, `USDJPY`, `XAUUSD`, `XAGUSD`, `XCUUSD`, `XPTUSD`,
`BTCUSD`, `ETHUSD`, `SOLUSD`, `XRPUSD`, `BCHUSD`, and `LTCUSD`.

Clusters are fixed as US indices (`US30/US100/US500/US2000`), Europe indices
(`GER40/FRA40/UK100`), Asia indices (`JP225/AUS200/HK50`), FX, metals,
energy, and crypto. Portfolio rules remain one seat per cluster and two seats
globally. Candidate order is the alphabetical FTMO-symbol order; it is not
reordered after results are observed.

## H1 construction and unchanged trading geometry

Each H1 bar is made only from a complete contiguous UTC group of four M15 bars:
first open, extrema high/low, last close, summed volume, and maximum source
spread. Incomplete hours are discarded. Keep momentum lookback 6, threshold
2 ATR, Wilder ATR(14), continuation direction, W2 adverse wick at least 0.30,
limit entry 0.6 ATR from the signal close, three-bar pending window, 1 ATR stop,
50% bank at +1R, TP2.0 remainder, eight-bar maximum hold, and stop-first OHLC
ordering.

Cost per side is the larger of the frozen source half-spread and a non-zero
FTMO snapshot half-spread, divided by median H1 ATR, plus the frozen commission
converted to ATR through the FTMO tick metadata. E1 uses that cost. E2 doubles
the entire per-side cost.

## Stage A — causal per-symbol gate

Use the chronological final 30% after H1 aggregation as OOS. Report full and OOS
trade count, expectancy, win rate, all OOS quarters, E1, and E2 for every cell.
A candidate advances only if all are true:

1. E1 OOS expectancy is positive.
2. E2 OOS expectancy is positive with at least 50 OOS trades.
3. At least 60% of complete OOS quarters are positive under E2, and the latest
   complete OOS quarter is positive.
4. FTMO metadata permit trading and all sizing fields are positive.

## Stage B — account screen and confirmation

Construct pending/entry/mark/partial/final events exactly as in the registered
H1 account tape. Apply clusters before bootstrap. Use the same seed 13020260711,
20-day moving blocks, sequential FTMO phases, C0 risk 0.30% in both phases,
daily/static/EA halts, minimum trading days, rounding, cluster cap, and global
cap as the existing account engine.

The C# and Python engines must match exactly on path 0 for the control and every
tested portfolio. The 20,000-path E2 screen uses common path IDs for control and
candidate. A candidate screen-pass requires:

* both-phases point estimate at least 80%;
* one-sided 95% Wilson lower bound at least 80%;
* exact paired one-sided 95% lower delta versus the control above zero;
* hard-halt probability no more than one percentage point; and
* timeout probability no higher than the control.

If one or more candidates screen-pass, confirm the strongest paired candidate
on 100,000 E2 paths. Final admission requires the same gates at 100,000 paths.
Then repeat greedy forward selection from the admitted portfolio until no
remaining Stage-A passer meets every gate. Ties are resolved alphabetically.

## Controls, reporting, and kill rules

The existing three-symbol C0 tape is the control. Defaults-off engine behavior
must reproduce its prior path-0 result and 100,000-path summary when the full
control is requested. Report every candidate, failure, error, and tested
portfolio. Do not reinterpret a failed asset as a diversification success.

If no candidate clears final admission, the universe remains unchanged. If an
asset clears final admission, only the whitelist and fixed cluster map may be
changed; strategy geometry and risk remain unchanged. Deployment is permitted
only while the FTMO account is flat, with a graceful restart and verified H1
init line. The forward test remains the live validation.

Ledger charge: 30 predeclared per-symbol cells, one 20,000-path account cell for
each Stage-A passer, and one 100,000-path confirmation per greedy admission.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `458dc2f63a7faf5e608df1f803c7b9e4cbbc4eccdf44f681c6114f24072200fe`
