# H1-signal / lower-timeframe reclaim entry — pre-registration

## Question

Can lower-timeframe execution improve the reliability and cross-asset breadth of
the confirmed H1 W2 strategy without redefining the signal on noisy M15/M5 bars?

## Rationale

The unchanged six-bar signal measures six hours on H1, 90 minutes on M15, and
30 minutes on M5. Those are different hypotheses. The existing results show
positive H1 OOS expectancy but approximately flat corrected-engine M15
expectancy. Therefore H1 remains the signal and risk unit. The lower timeframe
is used only to observe the pullback and require evidence that continuation has
resumed before entry.

## Frozen protocol

* Source is repository market data only. No API refresh is permitted. M15 cells
  use the frozen `derivM15_spreadgated` files. M5 is enabled by the runner but
  remains `NOT RUN` until canonical M5 files and a manifest exist.
* Aggregate only complete, contiguous execution bars into UTC H1 bars. H1 OHLC,
  volume, and spread use first open, extrema, last close, sum, and maximum,
  respectively. A signal becomes actionable only after its H1 bar has closed.
* Signal geometry remains unchanged: six H1 bars, 2.0 Wilder-ATR(14) momentum,
  aligned signal candle, W2 adverse wick at least 0.30 H1 ATR, both directions.
* The candidate level remains the edge-bearing H1 close minus direction times
  0.60 H1 ATR. It is watched for three subsequent H1 bars.
* Control `C0_TOUCH`: enter at the candidate level on the first lower-timeframe
  bar that touches it.
* Candidate `C1_RECLAIM`: after the level is touched, enter at the close of the
  first lower-timeframe candle that (a) closes back through the level in the
  signal direction and (b) has a body aligned with that direction. A touch and
  reclaim may occur on the same candle. Entry is rejected if its adverse
  displacement from the level exceeds 0.25 H1 ATR; this is a fixed anti-chase
  safety bound, not a tuning grid. The modeled market fill is the reclaim close.
* Entry and all stop/target/partial geometry use the frozen signal H1 ATR:
  SL 1.0 ATR, bank 50% at +1R, remaining TP 2.0 ATR, maximum hold eight hours.
  Lower-timeframe bars resolve the path with stop-before-partial-before-TP
  ordering. Two-sided measured spread cost is deducted.
* Enumeration is causal and one-symbol-at-a-time. An unfilled candidate occupies
  its three-H1-bar window. The exit bar is not eligible as a new signal bar.
* Report full and chronological 70/30 OOS results at measured and 2x cost for
  each symbol and pooled: opportunities, fills, fill rate, expectancy, win rate,
  profit factor, and median entry displacement from the H1 level.
* Primary frame is the confirmed FTMO trio. Breadth frame is every readable
  symbol in `derivM15_spreadgated`; no symbol may be silently omitted.

## Promotion and kill rules

This is a paired screen, not authorization to change the EA. `C1_RECLAIM` may
advance only if all conditions hold:

1. Trio pooled OOS expectancy is positive and no worse than `C0_TOUCH`.
2. Trio pooled OOS lower-timeframe entry displacement does not consume more
   than 0.25R by construction and expectancy remains positive at 2x cost.
3. At least two of the three trio symbols are OOS-positive.
4. Breadth OOS expectancy is positive and at least 60% of symbols are positive.
5. The fill count is at least 60% of control; reliability cannot be manufactured
   by deleting nearly all trades.

Failure of any condition kills the candidate. Passing permits a separately
specified coupled-account Monte Carlo and M5 confirmation; it does not enable
live logic. Any later EA implementation must be input-gated and default OFF.

The frozen H1 production path, symbol whitelist, risk sleeves, exits, and
portfolio rails must remain byte-for-byte behaviorally unchanged.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `429fccd776d0c83e61a8da36eeeee22b8850a3e21592309507b0e5d43680a548`
