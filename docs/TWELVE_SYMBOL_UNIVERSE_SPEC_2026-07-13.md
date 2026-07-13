# Twelve-symbol H1 universe diagnostic — pre-registration

## Decision question

Can the deployed v1.31 H1 strategy scan and trade at least 12 FTMO symbols,
increase actual filled-trade frequency, and retain the owner's account-risk
floors without changing signal or exit geometry?

This study does not authorize a live whitelist change. The terminal and
deployed four-symbol v1.31 configuration remain untouched until all registered
gates pass and a separate forward-shadow review is accepted.

## Selection disclosure and fixed basket

The 33-symbol H1 screen outcomes are already known. Therefore this is an
exploratory portfolio/frequency diagnostic, not a blind confirmation of entry
edge. To prevent further cherry-picking, the basket is fixed before this run as
the 12 FTMO symbols with positive E2 OOS expectancy in the completed screen:

| FTMO symbol | Frozen source | Role |
|---|---|---|
| US30.cash | Wall_Street_30 | current v1.31 |
| US100.cash | US_Tech_100 | current v1.31 |
| JP225.cash | Japan_225 | current v1.31 |
| USDJPY | USDJPY | current v1.31 |
| US500.cash | US_SP_500 | added candidate |
| FRA40.cash | France_40 | added candidate |
| AUS200.cash | Australia_200 | added candidate |
| EURUSD | EURUSD | added candidate |
| XAUUSD | XAUUSD | added candidate |
| XCUUSD | XCUUSD | added candidate |
| XPTUSD | XPTUSD | added candidate |
| LTCUSD | LTCUSD | added candidate |

No symbol may be replaced or removed after the run begins. Known weaknesses
remain visible: several additions failed the prior full Stage-A gate because of
sample size, quarter consistency, or full-frame expectancy. Passing this
account diagnostic cannot erase those failures.

## Frozen data, mechanics, and costs

1. Run `python backtest/verify_data.py`; only `verified 46 OK, 0 missing, 0
   mismatched` passes.
2. Use only the manifest-pinned CSVs and frozen FTMO metadata SHA256
   `ba1f3cdeaca429764129685f79a4267e1bbc55b2fead70c8187db431fd828928`.
   No API or terminal price refresh is permitted.
3. Preserve v1.31 geometry exactly: causal complete 4xM15 UTC H1 aggregation,
   six-bar 2ATR continuation momentum, aligned signal candle, W2 adverse wick
   at least 0.30ATR, 0.60ATR pullback limit, three-bar fill window, 1ATR stop,
   50% partial at +1R, +2R final target, stop-first ordering, and eight H1 bars
   maximum hold.
4. Preserve one position/pending per symbol, one seat per registered cluster,
   two global seats, eight fills per Prague EA day, four final-loss day stop,
   and current whitelist-first then alphabetical scan priority.
5. E2 doubles the registered all-in per-side cost. The stress tape is primary.

## Risk cells

The current index trio remains at 0.30% dynamic balance risk per fill and
USDJPY remains at 0.05%. All eight added symbols share one predeclared sleeve
risk. Test exactly three cells at 20,000 common paths:

* T12-R01: additions at 0.01% each;
* T12-R02: additions at 0.02% each;
* T12-R03: additions at 0.03% each.

There is no interpolation. If multiple cells pass, select the highest
both-phase point estimate; ties select the lower added-symbol risk. Confirm the
selected cell once on 100,000 common paths.

Use the existing deterministic C#/Python sequential Challenge/Verification
engine, seed 13020260711, 20-day moving blocks, common eligible flat blocks,
two-stop equity mode, current lot floors/steps, sequential phases, Prague day
rules, minimum trading days, 3,650-day phase timeout, and current FTMO/EA
daily/static/trailing rails. Python and C# path 0 must match exactly before any
screen path is accepted.

## Frequency and edge census

Before account Monte Carlo, report for the control four and fixed 12-symbol
tapes under E2:

* accepted pending lifecycles, actual entries, unfilled cancellations, and
  fill rate;
* entries by symbol and registered cluster;
* mean fills per calendar day and per Monday-Friday Prague trading day;
* median, p10, p90, maximum, zero-fill weekdays, and proportion of weekdays
  with at least six fills;
* pooled and per-symbol trade count, expectancy, and win rate, plus complete
  quarterly expectancy.

The owner’s prior frequency target remains binding: the 12-symbol candidate
must average at least 6.000 actual entries per Monday-Friday Prague day. A
weekday with zero fills stays in the denominator. Frequency is measured after
all occupancy, cluster, global, daily-fill, and loss-streak rules.

## Account gates

Each screen and confirmation cell must satisfy all of the following:

1. both-phase point estimate at least 78.887%;
2. one-sided 95% Wilson lower both-phase probability at least 78.887%;
3. paired one-sided lower delta versus the deployed four-symbol control above
   zero on common paths;
4. hard-halt probability no greater than 1.000%;
5. timeout probability no higher than the deployed result, 14.156%;
6. pooled E2 expectancy positive and no added symbol with non-positive E2 OOS
   expectancy; and
7. the registered 6.000-fill weekday average.

Failure of either the edge or frequency gate is the headline even if account
Monte Carlo passes. A historical survivor is only forward-shadow eligible;
because basket construction used already-seen OOS outcomes, it cannot be
installed from this study alone.

Ledger charge: one fixed 12-symbol portfolio diagnostic, three predeclared
risk cells, and at most one 100,000-path confirmation. No new entry hypothesis
is claimed.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `ab5e4be70b5cd76cec22579a1e0839522365d41b946a3844cb35ff94e01b0872`

## Results appended post-run

The 12-symbol tape averaged 2.404118 actual entries per Monday-Friday Prague
day and only 2.3166% of weekdays reached six fills. Its registered-round-trip
E2 expectancy was +0.043201R versus +0.079031R for the four-symbol control;
five additions were negative. The frequency and edge gates failed, so no risk
cell or account Monte Carlo was opened. [MEASURED: `python -u
backtest/run_twelve_symbol_census.py` @ `d925398`]

The census also found that the H1 account tape's one-time entry debit differs
from the reference resolver's two-sided registered cost by +0.075039R per
candidate trade (+0.057315R control). This must be reconciled before another
H1 account-probability claim. [MEASURED: same command and source inspection @
`d925398`]

Verdict: **FAILED — DO NOT EXPAND THE LIVE WHITELIST.** Complete results are in
`docs/codex/TWELVE_SYMBOL_UNIVERSE_REPORT_2026-07-13.md` and
`backtest/twelve_symbol_census_results.json`.
