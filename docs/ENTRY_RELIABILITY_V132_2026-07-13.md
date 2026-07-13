# v1.32 entry reliability and symbol portability

## Objective

Improve live entry reliability and broker portability without changing the
validated H1 alpha definition:

* 6-bar, 2 ATR continuation impulse;
* W2 adverse wick of at least 0.30 ATR;
* 0.6 ATR pullback limit;
* frozen signal ATR, SL1, 50% at +1R, TP2, and eight-bar hold;
* spread/ATR, portfolio, cluster, and drawdown gates.

This is an execution-hardening release, not a claim that native M5 or M15 has
matched H1 expectancy.

## Changes

### Crossed-limit recovery

Live telemetry documented a decision-to-send race: price can cross a valid
pullback limit after the EA checks it but before the broker validates it. The
broker then returns `TRADE_RETCODE_INVALID_PRICE` (10015), losing a signal that
the parity engine counts as filled.

v1.32 retries once as a market order only when a refreshed executable quote has
already crossed the original limit at an equal-or-better price and the symbol
uses MT5 request/instant execution:

* buy: refreshed ask is at or below the buy limit;
* sell: refreshed bid is at or above the sell limit.

The retry sends the refreshed quote and caps deviation to the smaller of the
configured deviation and the remaining price cushion to the original limit.
Market/exchange execution modes are not retried because those modes do not
enforce that cap. No retry occurs when price moved away, for other rejection
codes, or after the single attempt. SL and TP are rebuilt around the refreshed
entry while retaining the frozen ATR distances and risk-sized volume. The
behavior can be disabled with `InpRetryCrossedLimitV132`.

If the intended limit has not traded but falls inside the broker's minimum stop
distance, the EA now moves the pending one tick beyond that minimum instead of
entering at market early. Market conversion remains reserved for a limit price
the executable quote has actually crossed.

### Fail-closed candle data

The W2 filter previously skipped its predicate when high/low data was missing.
That admitted an unverifiable signal. v1.32 rejects missing or internally
inconsistent signal-bar OHLC instead.

### Broker symbol portability

Whitelist names now resolve exact symbols first, then one unique broker-suffixed
name when `InpResolveBrokerSuffixesV132` is enabled. For example, a canonical
`USDJPY` configuration may resolve to `USDJPY.a`. Zero or multiple matches fail
closed.

Cluster membership and risk sleeves use the same canonical suffix matching. The
longest matching token wins, so overlapping canonical names are deterministic
and suffix resolution cannot accidentally remove a symbol from its correlation
cap or promote reduced-risk USDJPY to base risk.

### Explicit risk sleeves

`InpRiskOverridesV132` accepts comma-separated `SYMBOL=percent` entries. Every
override must be positive and no larger than `InpRiskPercent`; malformed or
over-risking maps prevent initialization. Duplicate risk or cluster tokens also
fail initialization rather than relying on list order. Unspecified symbols
retain base risk.

This makes additional *validated* assets deployable without adding one hard-coded
input per symbol. It does not admit assets automatically: the whitelist,
spread/ATR gate, cluster map, and external universe-admission evidence remain
required.

## Timeframe interpretation

Attaching the EA to an M5 or M15 chart does not make it an M5/M15 strategy. The
host chart is irrelevant because the EA uses a timer and per-symbol clocks.
`InpTimeframeV131` controls the alpha clock and remains H1 by default.

The existing limit is broker-side and can fill tick-by-tick, already finer than
M5. Therefore the safe way to use lower-timeframe execution is to retain the H1
signal clock and let the broker execute its pullback limit intrabar. Changing
`InpTimeframeV131` to M5 or M15 changes the strategy itself and remains an
unvalidated experiment. Repository evidence shows M15 is materially more
cost-sensitive, and no canonical M5 dataset is present.

## Validation boundary

The default H1 signal and exit geometry is unchanged, so historical alpha
results are not relabeled. Required deployment checks remain:

1. MetaEditor compile with zero errors and warnings.
2. Demo journal confirms exact or unique-suffix symbol resolution.
3. Force/test a crossed-limit 10015 path and confirm at most one retry, only on
   request/instant execution and with a deviation cap no worse than the original
   limit.
4. Confirm every resolved symbol retains its intended cluster and risk sleeve.
5. Continue forward fill-reconciliation before increasing size or admitting a
   new asset.
