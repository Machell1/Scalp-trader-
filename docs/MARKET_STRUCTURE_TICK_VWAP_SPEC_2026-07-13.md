# Market-structure + candle/tick + VWAP market-entry screen — pre-registration

## Cell definition

On the existing M15 W2 continuation signal (`watr >= 0.30`), enter at the next
bar open only when all conditions below hold at the signal close:

* VWAP: UTC-session anchored typical-price VWAP weighted by the supplied CSV
  `volume`; long close <= VWAP (discount), short close >= VWAP (premium); at
  least eight session bars have elapsed.
* Structure: long signal low is above the minimum low of the prior three bars
  and its close is above the prior close; short is the exact mirror (higher-low
  / lower-high continuation structure).
* Candle: body/range >= 0.60 and close location is >= 0.75 for long or <= 0.25
  for short. Zero-range candles fail.
* Tick-volume confirmation: signal volume >= 1.20 times the median positive
  volume of the preceding 20 bars. Fewer than 20 valid prior bars fails.

The control is market-at-next-open with W2 only and the same signal frame. Both
arms use the v1.30 bracket: 1ATR stop, 50% bank at +1R, TP2.0, eight-bar maximum
hold, stop-first ordering, and measured/stress costs. No pending order, trail,
or parameter sweep is permitted.

Primary frame is the FTMO trio (`Wall_Street_30`, `US_Tech_100`, `Japan_225`) in
the frozen `derivM15_spreadgated` directory. Report full and 70/30 OOS per
symbol and pooled, win rate, trade count, measured cost and 2x stress. Kill if
pooled OOS <= 0, any symbol OOS <= 0, or pooled 2x-cost OOS <= 0. A positive
screen is not FTMO evidence; it requires a new account-level preregistration.

Ledger charge proposed: one exploratory composite entry cell plus its market
control. No API refresh, terminal access, or EA modification.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `32dd1c414f99fc9377f90c07034d6b79fa0fff1b4638871cfb3b3cedad985c5f`
