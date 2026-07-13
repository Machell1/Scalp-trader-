# Six-fill intraday sleeve — pre-registration

## Decision question

Can a separately risk-budgeted, live-parity intraday sleeve produce at least
six actual filled positions per FTMO trading day without weakening the
deployed v1.31 H1 portfolio's edge or falling below the owner's 78.887% E2
stress-pass floor?

This is a frequency study, not a quota. A cell may not manufacture a sixth
trade after its registered signal rules fail. The deployed v1.31 H1 strategy,
terminal configuration, and risk ledger remain untouched during the study.

## Provenance and frozen inputs

1. Run `python backtest/verify_data.py` before the study. The only passing
   output is `verified 46 OK, 0 missing, 0 mismatched`.
2. Use only the manifest-pinned CSVs in `backtest/data/`. No terminal/API bar
   refresh is permitted.
3. Use the 33 exact FTMO twins and frozen broker metadata already registered
   by `H1_UNIVERSE_ADMISSION_SPEC_2026-07-13.md`. Source-folder priority,
   FTMO symbol mapping, commissions, spread floors, and clusters are unchanged.
4. E1 uses the registered all-in per-side cost. E2 doubles the entire per-side
   cost. Every fill pays two sides. Report every cell and every failure.

## Two predeclared cells

Both cells aggregate only complete contiguous pairs of M15 bars into causal
UTC M30 bars: first open, maximum high, minimum low, last close, summed volume,
and maximum source spread. Incomplete pairs are discarded. Both use Wilder
ATR(14), six-bar continuation momentum of at least 2 ATR, aligned signal
candle, and the W2 adverse-wick requirement of at least 0.30 ATR.

* **P30 — pending:** limit at signal close minus 0.60 signal ATR in the trade
  direction; fill during the next three M30 bars; otherwise cancel at the open
  of bar four. A working pending occupies its symbol, cluster, and global seat.
* **M30 — market:** enter at the next M30 open. The same signal may be used only
  once, and all live occupancy and day gates apply.

Both cells use the v1.30/v1.31 exit geometry unchanged: signal-bar ATR frozen,
1 ATR stop, 50% partial at +1R, remaining target +2R, stop-first ordering, and
eight M30 bars maximum hold. One position per symbol, one seat per registered
cluster, two seats globally, eight fills per Europe/Prague EA day, and four
final-loss day stop remain binding. Scan priority is the frozen order: current
v1.31 symbols first (`US30.cash`, `US100.cash`, `JP225.cash`, `USDJPY`), then
remaining FTMO symbols alphabetically.

## Causal symbol-selection rule

For each source independently, chronological bars are split 50% calibration,
20% confirmation, and 30% final OOS. A symbol enters a cell's frozen portfolio
only if, under E2 and single-symbol live occupancy:

1. calibration expectancy is positive with at least 50 fills;
2. confirmation expectancy is positive with at least 20 fills; and
3. at least half of the complete calibration-plus-confirmation calendar
   quarters have positive expectancy.

Selection uses no final-OOS outcome. After selection, the entire portfolio is
replayed once with cluster/global/day coupling. No symbol may be removed after
its final-OOS result is visible. Empty or insufficient selections fail.

## Final-OOS gates

A cell survives only if every gate below passes on the coupled final 30%:

1. **Frequency:** mean actual entries per eligible Monday-Friday EA trading day
   is at least 6.000. Report mean, median, p10, p90, maximum, zero-fill days,
   and the proportion of days with at least six fills. The denominator is every
   Monday-Friday Europe/Prague date from the latest selected-symbol OOS start
   through the earliest selected-symbol data end; a weekday with no fill still
   counts. Entries rejected by occupancy, cluster, global, daily-fill, or
   loss-streak gates do not count.
2. **Edge:** E2 pooled expectancy is positive, its one-sided 95% stationary
   block-bootstrap lower confidence bound is above zero, at least 60% of
   selected symbols are positive, and at least 60% of complete pooled OOS
   quarters are positive. Use 20-trading-day blocks, seed 13020260713, and
   10,000 bootstrap draws.
3. **Cost robustness:** E1 and E2 pooled expectancy are both positive. Report
   trade count, expectancy, win rate, profit factor, and average holding bars.
4. **No edge dilution:** when the sleeve is combined with the frozen v1.31 H1
   tape using its own predeclared risk, the E2 account result must retain a
   one-sided 95% Wilson lower both-phase pass probability of at least 78.887%,
   hard halt no greater than 1.000%, and timeout no higher than 14.156%.

Only a cell clearing gates 1–3 advances to account Monte Carlo. For that test,
the H1 risks stay 0.30% for the index trio and 0.05% for USDJPY. The new sleeve
is screened at dynamic risk 0.01%, 0.02%, and 0.03%; choose the highest risk
that passes all account gates, with no post-result interpolation. Use the
registered 100,000-path sequential Challenge/Verification engine, common path
IDs, 20-day moving blocks, and seed 13020260711.

## Kill and promotion rules

Any cell below six fills/day is a frequency failure even if profitable. Any
cell with non-positive E2 expectancy or confidence lower bound is an edge
failure even if frequent. Any account result below the 78.887% Wilson floor,
above 1% hard halt, or above 14.156% timeout is killed. Failed ideas are
reported and not deployed.

A survivor earns a separate implementation proposal and forward-shadow test;
it does not authorize an EA or terminal change. Ledger charge: two new entry
cells (P30 and M30), plus at most three predeclared account-risk cells for each
survivor.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `5748232e24bd8d78bb4349704a4ac9ab7f4c80d4e35a75902146103a1acb22fe`
