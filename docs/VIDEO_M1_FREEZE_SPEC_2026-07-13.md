# Video M1 US100 Data-Freeze Protocol — 2026-07-13

## Purpose

Create one immutable, outcome-blind snapshot of the already-running FTMO Demo
terminal's `US100.cash` M1 bars.  This is a data-provenance operation only. It
does not define, score, tune, or compare any trading rule.

## Fixed source and scope

- Terminal executable: `C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe`.
- Venue checks: server must be `FTMO-Demo`; company must be `FTMO Global Markets Ltd`.
- Instrument and timeframe: `US100.cash`, M1.
- Requested immutable endpoint: `2026-07-10T23:59:00Z` (a closed time before
  this protocol).  Retrieval is `copy_rates_from(symbol, TIMEFRAME_M1, endpoint,
  99999)`, so it is a fixed count ending at the registered endpoint rather than
  a drifting current-bar offset.
- The terminal must already be running. The freezer refuses to initialize if
  `terminal64.exe` is not already present; it must not launch, restart, close,
  reconfigure, install into, or write to the terminal.
- Permitted MT5 calls are `initialize`, `account_info`, `terminal_info`,
  `version`, `copy_rates_from`, `symbol_info`, `last_error`, and `shutdown`.
  No `symbol_select`, order, position, deal, history, chart, configuration, or
  terminal-file write calls are permitted.

## Outcome-blind integrity requirements

The freezer imports no strategy or backtest module and must not calculate a
signal, entry, exit, return, expectancy, win rate, drawdown, or pass rate.
It writes the raw structured array and a row-identical CSV. Before publication
it must require 99,999 rows, strictly increasing unique epochs, valid finite
OHLC invariants, non-negative spread and tick-volume fields, and lossless NPY
and CSV round-trips. It records all observed gap lengths instead of treating
market closures as a data repair task.

The immutable output directory is
`backtest/data/ftmoM1_us100_video_20260713/`, which stays ignored by Git. Its
only permitted regular files are `US100_cash_M1_99999.npy`,
`US100_cash_M1_99999.csv`, `METADATA.json`, `INTEGRITY.json`, and
`MANIFEST.sha256`. The byte-identical manifest is also written to tracked
`backtest/ftmo_m1_us100_video_20260713.manifest.sha256`; it is the only
committable representation of the frozen data.

If terminal access, venue validation, retrieval, validation, serialization, or
manifest verification fails, the freezer must publish nothing and report the
failure verbatim. A short M1 history is insufficient for a gate-grade
multi-quarter claim; any later strategy report must state the available sample
and cannot claim an FTMO pass probability from this snapshot alone.

## Run sequence

1. Commit and push this protocol and the outcome-blind freezer before terminal
   access.
2. Run `python backtest/freeze_video_m1_us100.py` once.
3. Run `python backtest/freeze_video_m1_us100.py --verify` and commit/push the
   resulting external manifest only if verification succeeds.
4. Only after the data freeze is sealed may a separate, hashed strategy
   protocol be written. No strategy execution is authorized by this protocol.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `df8e0cb677e696eb6a10bc9bd42aab68ebb5f10bb39639bb6095fb87b1bd57e1`
