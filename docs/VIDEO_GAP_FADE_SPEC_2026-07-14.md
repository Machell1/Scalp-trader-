# Video-inspired cash-session gap-fade research protocol

## Source and scope

The supplied video, *Millionaire Trader developed his QUANT TRADING
ALGORITHM*, describes a stock-specific observation: large positive daily gaps
often close below their opening price.  It does not disclose executable
threshold, entry, stop, target, or exit rules.  This document therefore
records a **new research translation**, not a reproduction of the creator's
undisclosed algorithm.

The candidate is research-only. It neither modifies MomentumPullbackEA nor
authorises any FTMO terminal action.

## Frozen data and universe

- Run `python backtest/verify_data.py` before the test; use only the frozen
  M15 `derivM15_spreadgated` CSVs for `Wall_Street_30`, `US_Tech_100`, and
  `Japan_225`.
- The source frames are UTC. Cash-session timestamps are converted to
  `America/New_York` for US30/US100 and `Asia/Tokyo` for JP225.
- This data has no financing, swap, auction, real opening-print, or FTMO
  broker-fill field. Any positive output remains non-deployable until those
  gaps are independently resolved.

## Single candidate cell

The strategy is a **same-day short gap fade**:

| Instrument | Prior reference | Candidate signal | Entry | Exit |
|---|---|---|---|---|
| US30, US100 | prior 15:45 NY M15 close | 09:30 NY M15 open is >= 0.50% above prior reference | short at 09:30 bid open | cover at 15:45 NY close ask |
| JP225 | prior 15:15 Tokyo M15 close | 09:00 Tokyo M15 open is >= 0.50% above prior reference | short at 09:00 bid open | cover at 15:15 Tokyo close ask |

The `0.50%` threshold is a stated operational assumption for the phrase
"large percent gapper"; it is not claimed to come from the video. There are
no other filters, parameter sweeps, position-sizing rules, stops, targets, or
symbol-selection rules. Signals with missing required bars or invalid prices
are skipped and counted.

For an entry at `open` and cover at `close`, net short return is
`(entry_bid - (close + multiplier * spread_price)) / entry_bid * 10,000`
bps. E1 uses multiplier 1; E2 uses multiplier 2. The final 30% of signal
bars in each source frame is OOS.

## Decision gates

Report all per-symbol and pooled OOS samples, mean net bps, total net bps,
win rate, worst result, and skipped counts for E1 and E2.

This single candidate has a provisional research edge only when its E2 mean
is positive in every symbol with at least 25 OOS signals, the pooled E2 mean
is positive, and pooled E2 OOS count is at least 300. These sample gates are
intentionally stricter than a single attractive aggregate because the video
emphasizes large samples and data-backed rules.

Failing any gate disposes of this exact candidate. A pass does not permit a
live build because the strategy lacks a stop/gap-risk and FTMO-cost model.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `8f5acbfc8cf7d216bb16e4150184d33bab9a26e918559ada842960f5cad8901e`
