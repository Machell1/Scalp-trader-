# Video M1 US100 Data-Freeze Amendment — 2026-07-13

## Reason and scope

The original immutable freezer protocol
`VIDEO_M1_FREEZE_SPEC_2026-07-13.md` was executed once without any strategy
logic. Its fixed 99,999-bar request returned 98,807 bars, so its required
completeness gate failed and it published no data or manifest. This amendment
does not change a trading rule or use outcomes. It defines a new, narrower,
fixed-count retrieval based solely on that recorded availability result.

## Fixed retrieval

- Source, venue checks, symbol, terminal read-only restrictions, permitted MT5
  calls, and closed endpoint remain exactly those in the original protocol.
- The retrieval is now `copy_rates_from('US100.cash', TIMEFRAME_M1,
  2026-07-10T23:59:00Z, 98807)`.
- Exactly 98,807 returned bars are required. A smaller or larger result is a
  failure, publishes no data, and is not retried with a changed count.
- Output directory: `backtest/data/ftmoM1_us100_video_20260713/`.
- Permitted regular output files are now `US100_cash_M1_98807.npy`,
  `US100_cash_M1_98807.csv`, `METADATA.json`, `INTEGRITY.json`, and
  `MANIFEST.sha256`. The matching tracked file is
  `backtest/ftmo_m1_us100_video_20260713.manifest.sha256`.

## Same outcome-blind safeguards

The freezer must import no strategy/backtest module and calculate no signal,
trade, return, expectancy, win rate, drawdown, or pass probability. It must
retain the original protocol's UTC ordering, finite OHLC, OHLC-invariant,
non-negative spread/tick-volume, NPY/CSV round-trip, and SHA256 manifest
requirements. It must not write to the terminal, alter Market Watch, place or
manage an order, read trading history, change terminal/chart settings, or
start/restart/close the terminal.

This dataset is limited to the terminal history available under the original
fixed endpoint. It cannot, by itself, support a multi-quarter gate-grade FTMO
pass-rate claim. Any later use must identify it as an exploratory short-history
study and preserve the original failed 99,999-bar protocol and failure.

## Run sequence

1. Commit and push this amendment and its corresponding outcome-blind freezer
   update before terminal access.
2. Execute the freezer once, then execute `--verify` once.
3. Commit and push only the external SHA256 manifest if verification succeeds.
4. Write and hash a separate strategy protocol before any strategy execution.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `0dc3fd9521abfe00b7425c02191520bbf7440346267bd2a0b95a24f497a38e9c`
