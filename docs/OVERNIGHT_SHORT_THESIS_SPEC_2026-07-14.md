# Overnight short thesis: cash-session versus broker-day close/open

## Question

For the current index trio, is a short entered at a close and covered at the
next relevant open profitable after observed spread, and which of two fixed
definitions has the better out-of-sample edge?

## Universe and frozen data

- Only `Wall_Street_30`, `US_Tech_100`, and `Japan_225` from the canonical
  `backtest/data/derivM15_spreadgated` M15 frames. Verify the 46-file manifest
  before execution.
- This is a Deriv-data research thesis, not FTMO-deployment evidence. It has
  no swap/financing field, so any positive result requires broker-native FTMO
  cost and financing confirmation before it can be considered for deployment.

## Fixed cells

| Cell | Entry short | Cover | Time zone |
|---|---|---|---|
| CASH | cash-session closing M15 bar | next cash-session opening M15 bar | NY for US30/US100; Tokyo for JP225 |
| BROKER | M15 bar ending at broker midnight | next M15 bar beginning at broker midnight | Europe/Helsinki |

- CASH: US30/US100 enter at the close of the 15:45–16:00 America/New_York
  bar and cover at the 09:30 open of the next cash session. NYSE core hours
  are 09:30–16:00 ET. JP225 enters at the close of 15:15–15:30 Asia/Tokyo and
  covers at the next 09:00 Tokyo cash opening; JPX cash hours are
  09:00–11:30 and 12:30–15:30 JST.
- BROKER: enter at the close of the local 23:45–00:00 Europe/Helsinki bar and
  cover at the open of the following local 00:00 bar. This is deliberately
  tested even if it is only one M15 interval in normal conditions.
- Entry is at the bar close bid. Cover is at the next-open ask:
  `cover = open + cost_multiplier * spread_price`; E1 multiplier 1 and E2
  multiplier 2. Net short return is `(entry - cover) / entry * 10,000` bps.
- No threshold, filter, symbol selection, leverage, stop, target, or exit
  timing is swept. Missing bars or invalid prices are skipped and counted.

## Evaluation and decision

- The final 30% of each source frame by signal bar is OOS. Report every cell,
  symbol, E1/E2, count, mean net bps, win rate, total bps, worst net bps, and
  skipped count.
- A cell has a provisional OOS edge only if under E2 its pooled OOS mean is
  positive and every symbol has positive OOS mean with at least 50 OOS trades.
- If both cells pass, the larger E2 pooled mean is the better edge. If one
  passes, it is the only provisional edge. If neither passes, the thesis is
  disposed. No live EA change follows from a pass because there is no
  pre-registered stop/gap-risk or FTMO financing model.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `2cf705ceb2e9c665b80088cdfb20500674e49825d2fa52005c75c017bb869607`
