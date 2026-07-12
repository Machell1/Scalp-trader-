# v1.30 executable-price cost-ledger parity audit — pre-registration

**Date:** 2026-07-12 UTC

**Branch:** `codex/v130-cost-ledger-audit`

**Outcome frame:** frozen FTMO development split only; confirmation and holdout
are not authorized by this protocol

**Expectation:** neutral fidelity measurement, not an improvement claim

## 1. Question and frozen premise

Does the current v1.30 F2 calculation debit the index spread twice: first by
requiring executable-side bid/ask trade-through for every limit-side fill, and
again by subtracting one median full spread from the completed trade?

This audit does not change the EA, signal, W2 predicate, symbol universe,
pending behavior, partial close, TP, SL, holding period, risk, portfolio caps,
or FTMO rules. It changes no terminal input and sends no order. It only
recomputes the cash R ledger from executable bid/ask prices.

The prior risk-policy idea remains disposed. Its recorded F2 strict-ask result
was `+0.0025410956R`; its F2 strict-ask plus doubled legacy spread debit was
`-0.0445521560R`. Those numbers are controls, not targets. [MEASURED:
`python backtest/run_v130_risk_study.py --development-edge` @
`18b04c7a8613fcfdee952d2ceb7cddbed54eccd4`]

## 2. Pre-outcome broker and source calibration

FTMO states that simulated index trading is commission-free. The frozen demo
account history through `2026-07-12T06:46:04.142549+00:00` contained six
matching MomentumPullbackEA index deals, representing three completed
positions. Total commission was `0.00000000`; total fee was `0.00000000`.
[MEASURED: official FTMO
`https://ftmo.com/en/blog/zero-commissions-on-indices/` and read-only
`MetaTrader5.history_deals_get` on login 1513946641]

For the same three positions, requested order levels were matched to actual
deals. All were shorts and none contained a v1.30 partial. The execution deltas
in signal-risk R were:

| position | symbol | entry delta R | exit delta R | total execution delta R | exit reason |
|---:|---|---:|---:|---:|---:|
| 492634097 | US100.cash | +0.0023289665 | -0.0113537118 | -0.0090247453 | stop |
| 492791197 | US100.cash | +0.0487804878 | -0.0103057369 | +0.0384747509 | EA market close |
| 493187993 | US30.cash | +0.0200862967 | -0.0145811635 | +0.0055051332 | stop |

Positive is favorable. The worst adverse single execution leg was
`0.0145811635R`; the worst adverse completed round trip was `0.0090247453R`.
[MEASURED: read-only FTMO `history_orders_get` plus `history_deals_get`; no
terminal write]

The calibration is small, all-short, and contains no partial execution. It is
not treated as a statistical upper bound. Before any strategy outcome is read,
this protocol therefore rounds the worst adverse leg up to a fixed
`0.02R` full-position slippage debit and registers `0.04R` as the mandatory
double-slippage stress.

The frozen bars do not contain historical swap terms. A read-only symbol-info
snapshot taken before the outcome run registered `swap_mode=1` (points) and
Friday (`swap_rollover3days=5`) as the triple day for all three symbols:

| symbol | swap long points | swap short points | point | tick size | profit tick value | loss tick value |
|---|---:|---:|---:|---:|---:|---:|
| US30.cash | -1139.46 | +47.42 | 0.01 | 0.01 | 0.01 | 0.01 |
| US100.cash | -645.63 | +26.87 | 0.01 | 0.01 | 0.01 | 0.01 |
| JP225.cash | -870.78 | -373.19 | 0.01 | 0.01 | 0.0006182686006108494 | 0.0006183221210922042 |

[MEASURED: read-only `MetaTrader5.symbol_info` on FTMO-Demo login 1513946641]

Because these are current rather than historical rates, the primary
conservative column applies negative swaps but never credits positive swaps.
The mandatory stress doubles negative swap. A rollover is Europe/Helsinki
broker midnight; Friday charges three days. Swap is multiplied by the volume
fraction still open at that instant.

Source inspection fixed the following facts before the outcome run:

- The EA builds a long/short SL and TP from the requested pending entry price;
  the simulator assumes an exact limit fill at that price. Live limit price
  improvement and market-fallback slippage can make the weighted deal entry
  differ. The v1.30 partial registry uses the actual weighted deal entry.
- F2 already requires long entries and short protective/exit buys to cross on
  the ask proxy (`bid + observed spread`) while sell-side executions use bid.
- The current engine then debits `2 * median_cost_per_side`, where
  `median_cost_per_side = 0.5 * median(spread_price) / median(ATR)`.

[MEASURED: `mql5/MomentumPullbackEA.mq5`, `backtest/v130_coupled.py`,
`backtest/v130_crosscheck.py`, and `backtest/walkforward_dsr.py` @ merged main
`170f7ad92800c07c85064adecbc6a13a684ec959`]

## 3. Immutable data and access controls

Before every audit run:

1. `python backtest/freeze_ftmo_v130_blind.py --verify` must print exactly
   `verified FTMO blind freeze 9 OK, 0 missing, 0 mismatched, 0 extra`.
2. `python backtest/verify_data.py` must print exactly
   `verified 46 OK, 0 missing, 0 mismatched`.
3. The outcome runner may call only `load_ftmo_split("mined")` and must not
   expose an `authorize_blind` option.
4. Any other verification result stops the run.

The owner-attestation caveat remains: repository lineage can prove what this
runner accesses, but cannot prove that no manual or untracked process ever read
the nominally blind frames.

## 4. Frozen execution and ledger columns

All columns use the same causal coupled scheduler: whitelist order
US30.cash, US100.cash, JP225.cash; W2 adverse wick `>=0.30`; four working fill
bars; pending/position symbol occupancy; US30/US100 shared cluster; JP225 own
cluster; one seat per cluster; global cap two; eight fills per EA-server day;
four final losses per EA-server day; partial keeps its seat; SL before partial
and TP on an ambiguous bar; seven post-entry bars with time exit on the eighth
bar convention already frozen in v1.30.

For E0/E1/E2, the four-loss classifier must reproduce the deployed EA's
current server-day truncation rather than reuse whole-lifecycle R. At a final
exit it sums only that position's modeled partial/final deal cashflows whose
event time is on the final exit's Europe/Helsinki day; negative increments the
streak, positive resets it, and exact zero leaves it unchanged. Slippage is
allocated pro rata to the partial/final exit fractions for this classifier.
Accumulated negative swap is attached to the final deal, matching how the EA
reads `DEAL_SWAP` from history. The account-equity stress may still debit fixed
slippage at entry, but that conservative timing must not alter the EA streak
classification. C0 remains the exact committed control, including its already
reported cross-midnight approximation.

### C0 — current recorded controls

- `C0_F1`: existing `F1_PER_BAR`, including its median full-spread R debit.
- `C0_F2`: existing `F2_STRICT_ASK`, including its median full-spread R debit.
- `C0_F2X`: existing `F2_STRICT_ASK_2X`, including twice that debit.

These must reproduce the committed JSON exactly before any new number is
reported.

### E0 — executable-price ledger, zero added slippage diagnostic

For every bar, synthetic ask OHLC is bid OHLC plus that bar's nonnegative
`spread_price`. Entry, stop, partial, target, and time-exit rules are:

- long limit entry: ask low `<= entry`; booked at the limit entry price;
- short limit entry: bid high `>= entry`; booked at the limit entry price;
- long stop: bid low `<= stop`; booked at stop;
- short stop: ask high `>= stop`; booked at stop;
- long partial/TP: bid high `>= level`; booked at level;
- short partial/TP: ask low `<= level`; booked at level;
- long time exit: bid close of the registered time-exit bar;
- short time exit: ask close, equal to bid close plus observed spread on that
  bar.

Limit fills receive no favorable price improvement. Stops receive no favorable
fill. Gap and tick-path slippage are not inferable from M15 OHLC and are handled
only by the fixed stress columns below.

The zero-slippage price R is:

`banked_partial_R + remaining_fraction * side * (exit_exec - entry_exec) / frozen_risk`.

No median-spread debit is applied because both entry eligibility and exit
prices are already expressed on executable sides and all bracket levels are
anchored to the modeled requested entry, which is itself executable only after
the side-correct touch. Index commission and fee are zero under the frozen
broker calibration. This is the accounting claim under audit, not an assumed
favorable result.

E0 is the zero-slippage, zero-swap decomposition diagnostic only. It is not the
promotion column.

### E1 — primary measured-rounded executable ledger

`E1_R = E0_R - 0.02R + conservative_swap_R`. Each closed volume fraction is
charged `0.02R * closed_fraction`; fractions sum to one whether or not the
partial executes. Negative current-broker swap is charged at every crossed
Europe/Helsinki midnight on the then-open fraction; positive swap is set to
zero. For points-mode swap, cash per lot is
`swap_points * point / tick_size * trade_tick_value_loss`; it is divided
by full-position frozen-stop risk cash per lot to obtain R. Friday rollover is
multiplied by three when the Europe/Helsinki calendar day immediately before
the crossed midnight is Friday. The slippage debit is applied at entry in any
later account simulation so it cannot improve an intraday drawdown path; swap
remains timed at rollover.

### E2 — mandatory conservative double-slippage/swap stress

`E2_R = E0_R - 0.04R + 2 * conservative_negative_swap_R`. This is a double
stress of measured adverse-leg slippage and current negative swap; it is not
labeled a second spread.

## 5. Implementation and regression gates

The new ledger mode must be additive and default-off. With it off:

- all 46 canonical manifest files remain trade-for-trade and R-identical;
- committed C0_F1/C0_F2/C0_F2X trade IDs, event bytes, hashes, counts, R,
  expectancy, and win rate reproduce exactly;
- no production EA or terminal file changes.

With E0/E1/E2 on:

- for the same admitted signal, E0/E1/E2 resolve identical price geometry;
  E1/E2 then add only their registered slippage and swap cashflows;
- each column is scheduled independently because a slippage/swap-induced final
  sign change legitimately changes the EA's four-loss day gate. Any later
  lifecycle divergence must be fully attributed to those sign changes;
- a default-off execution-plan loss-classification value may be added to the
  shared scheduler; when absent, all historical behavior remains byte-identical;
- a policy-neutral diagnostic replay freezes E0 admissions and proves the
  per-trade E1/E2 slippage delta plus timed swap exactly, but that diagnostic is
  not substituted for the independently causal headline columns;
- C0_F2 and E0 use identical raw candidate geometry before any loss-gate
  divergence, except that short time-exit execution prices/R may differ and the
  legacy cost component is absent;
- synthetic tests cover long and short SL, partial+SL, partial+TP, same-bar
  stop-first, long/short time exits with nonzero spread, ordinary rollover,
  partial-before-rollover, Friday triple rollover, and the deployed
  cross-midnight day-truncated four-loss classification;
- an independent small reference implementation must match E0 at `1e-12`.

Any mismatch stops before development results.

## 6. Development report and gates

Report every C0/E0/E1/E2 cell, pooled and per symbol:

- completed trades, expectancy, win rate, total R, and deterministic SHA256;
- every complete and partial calendar quarter;
- last-four-complete-quarter expectancy;
- expectancy after deleting each symbol;
- counts by long/short, exit reason, and partial state;
- the exact legacy-debit removal contribution, short-time-exit correction,
  `0.02R` debit, and `0.04R` debit;
- counts crossing each broker rollover, volume fraction open, ordinary/triple
  negative swap R by symbol and side, and positive swap credits suppressed;
- counts and exact trade IDs whose final sign changes between columns, followed
  by all later day-gate admission divergences;
- all fidelity checks, failures, and commands verbatim.

This fidelity audit is considered robust enough to support a later risk-policy
study only if all of the following hold:

1. E1 and E2 pooled expectancy are strictly positive.
2. E2 last-four-complete-quarter expectancy is strictly positive.
3. Every symbol has nonnegative E2 expectancy.
4. E2 pooled expectancy remains positive after deleting each symbol.
5. At least four complete quarters and at least 250 E2 trades per symbol exist.
6. No lifecycle, regression, hash, or access-control gate fails.

Failure is the headline and no account Monte Carlo runs on this branch. Passage
only authorizes a separately hashed risk-policy protocol; it does not prove an
88% Challenge pass probability, authorize an EA input change, or open a blind
frame.

## 7. Ledger, disposition, and live validation

This is a fidelity remeasurement of already-recorded trades, not a new trading
hypothesis. Proposed trial ledger charge: `209 -> 209` (zero). Any later symbol
deletion, spread threshold, risk schedule, entry pause, or activation rule is a
new hypothesis with its own registration and charge.

If the executable ledger fails a gate, the accounting result is retained but
the idea is disposed for promotion. No threshold or stress is relaxed. If it
passes, the next protocol must still require strict-ask fills, FTMO daily/static
loss rules, EA rails, current-balance lot rounding, coupled occupancy,
sequential phases, 100,000 paths, and a one-sided 95% lower bound strictly above
88%. Forward v1.30 trades remain the decision-grade validation.

---
**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `1991c5163c08e368448502226f9758980666a0cc363e3dc36d5a74363eb2c8ae`

---
## RESULTS

Registration note: commit `a9de11c` exposed three intentional Markdown hard
breaks as `git diff --check` trailing-whitespace failures. Before any outcome
cell, those breaks were normalized and the protocol was rehashed. The binding
pre-outcome hash is the recorded value above; the earlier
`68d1b852aa23db69b02c6b50bd9344b4d3c36aaba0814d2e84f39e6e407c39cc` is
superseded and was never used for an outcome run.

Not run at registration. Results may be appended here only; the protocol above
the recorded hash is immutable.
