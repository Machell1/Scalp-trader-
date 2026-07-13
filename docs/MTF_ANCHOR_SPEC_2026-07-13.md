# Sliding-anchor MTF entry (M15/M5 clocks, H1-scale signal) — pre-registration (2026-07-13)

## Motivation (owner directive)

The owner asked for a more reliable entry that lets the EA trade more assets and
be as effective on M15 and M5 as it is on H1, without losing the edge. The
evidence base says: (a) the H1 screen survived every gate (pooled OOS +0.208R,
2x-cost +0.188R, all trio symbols positive — `docs/codex/H1_TIMEFRAME_SCREEN_
REPORT_2026-07-13.md`); (b) NATIVE M15 with the same geometry is ~zero-edge at
real cost (live-parity census, W2_PARITY_SPEC) and every standalone lower-TF
entry family screened has failed (ENTRY_FAMILIES, MARKET_VWAP, STRUCTURE_TICK_
VWAP); (c) the H1 account MC's dominant failure is TIMEOUT (~20% of paths — the
strategy is signal-starved), which is also what blocks universe expansion
(candidates fail paired gates on thin, noisy tapes).

**Hypothesis (one mechanism, pre-stated):** the H1 edge lives in the H1-SCALE
pattern (6-hour 2-ATR impulse, contested W2 bar, 0.6-ATR pullback), not in the
hour-aligned bar grid. Therefore evaluating the UNCHANGED H1-scale signal on a
sliding lower-TF clock — at every M15 (later M5) close, aggregate the trailing
bars into a synthetic H1 series and apply the frozen rules in anchor-ATR units —
should (1) recover signals that complete off the hour grid (up to 4x/12x denser
evaluation against the timeout problem), (2) time entries/exits with finer
granularity, and (3) keep the cost mathematics at H1 scale (cost per side is
measured against the ANCHOR ATR, which is what made H1 survivable where native
M15 was not). This is explicitly NOT a lower-timeframe port of the strategy
(dead end, documented); the signal definition, all thresholds, and the risk
denominator remain H1-scale.

**Prior stated:** genuinely uncertain. The phase-offset controls may reveal the
H1 result is partly hour-alignment luck (that would be a headline negative
finding about the live config, reported as such). Off-phase signals overlap the
same physical impulses, so their marginal quality may be lower; occupancy
(one seat per symbol) already throttles re-entry. Expected trade count 1.5–3x
the H1 cell; the gates below decide.

## Frozen protocol

* `python backtest/verify_data.py` must print `verified 46 OK, 0 missing,
  0 mismatched` immediately before any cell. Manifest-pinned M15 CSVs only;
  no API refresh for the M15 cells.
* Runner: `backtest/run_mtf_anchor_screen.py` (this commit). Its enumeration
  is golden-verified by `backtest/test_mtf_anchor_screen.py`:
  phase-0 aggregation == `run_h1_timeframe_screen.aggregate_h1` exactly;
  cell A delegates verbatim to the registered `run_h1_timeframe_screen.run_cell`;
  `run_fine` at factor 1 reproduces the sequential reference trade-for-trade.
* Geometry frozen at the registered H1-screen values, all in anchor-ATR units:
  momentum lookback 6 anchor bars, threshold 2.0 ATR, candle-direction
  alignment, Wilder ATR(14) on the anchor series, W2 adverse wick >= 0.30,
  limit at signal close -/+ 0.6 ATR, pending window 3 anchor bars, SL 1.0 ATR,
  bank 50% at +1R, TP 2.0 ATR, 8-anchor-bar hold, stop-first pessimistic
  intrabar ordering, cost charged once on full size. **No parameter sweep.**
* Anchor bars: trailing aggregation of `factor` contiguous working bars
  (factor 4 for M15, 12 for M5); incomplete/discontiguous windows are
  discarded. Phase p = the aggregation offset by p working bars; every
  complete window end belongs to exactly one phase (asserted).
* Fine-grain execution (`run_fine`): signal evaluated at the open of working
  bar sig+1 from the anchor window ending at sig; single seat per symbol;
  pending rests working bars sig+1..sig+3*factor, unfilled frees the seat for
  signal bars >= sig+3*factor+1; exits resolved per working bar (stop-first);
  after an exit at working bar x, signal bars <= x are blocked (live
  `g_noSignalUpTo` semantics). `--live-window` runs the +1-bar Bars()
  off-by-one sensitivity column.
* Cost: per-side ATR fraction from the phase-0 H1 aggregation
  (`real_cost_per_side`), identical across cells of a symbol; E1 measured,
  E2 doubles it. OOS = chronological final 30%.
* Cells per symbol (registered above the hash, no post-hoc additions):
  A (phase-0/H1 grain, golden control), B_1..B_3 (phase-offset controls,
  H1 grain), C1 (phase-0 signals, fine execution), C2 (sliding, all phases,
  shared seat; cohort columns aligned vs off-phase). Universes: trio primary;
  the 10-symbol holdout generalization column (`--universe holdout`).
* M5 cell: requires `backtest/fetch_m5.py` data pinned into the manifest
  first; then the same runner with `--factor 12`. Not runnable before that
  pin; charged separately.

## Decision rules (pre-registered)

1. **Consistency anchor:** cell A on the trio must reproduce the recorded H1
   screen numbers exactly. Failure = pipeline broken, stop.
2. **Alignment robustness (B):** if pooled trio OOS at E1 is <= 0 for two or
   more of the three offset phases, the H1 edge is declared PHASE-FRAGILE:
   the sliding candidate is dead AND the finding is escalated to the owner as
   a caveat on the live H1 config. This arm can only kill, never ship.
3. **Execution granularity (C1):** pooled trio OOS must be > 0 at E1 and E2
   and not more than 0.05R below cell A's pooled OOS at E1. Worse = the fine
   execution package is rejected regardless of C2.
4. **Candidate (C2), ALL required:** pooled trio OOS > 0 at E1 AND E2; every
   trio symbol OOS > 0 at E1; off-phase cohort OOS n >= 50 and expectancy > 0
   at E1 (the added trades must carry their own weight — insufficient n =
   "insufficient evidence, no ship" regardless of sign); pooled OOS total R
   at E1 >= cell A's (more trades must not dilute the account-level take);
   >= 60% of complete OOS quarters positive at E1; holdout-10 pooled OOS not
   materially negative (> −0.01R) at E1.
5. **Nothing ships from this screen.** A pass buys ONLY a separately
   pre-registered FTMO account-level MC (H1_FTMO_ACCOUNT pattern: same seed
   discipline, C0 control reproduction, paired gates) and then owner sign-off
   + forward validation. The EA's `InpUseAnchorAggV132` flag stays OFF until
   all of that clears. DSR at the current ~213-cell ledger is reported for
   the record; the decision-grade frame remains forward.
6. Failures are reported cell-by-cell, including — especially — the controls.

Ledger charge proposed: 4 pre-declared trio cells (B batch counts as one
robustness cell, C1, C2, holdout column) + the M5 repeat when its data is
pinned. Screens noted at the batch level per house convention.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `0922f66f55bbff5b2b9530370926fa5ad60e2905c0c8952ba8bd276ba9cf0bf2`

*Results append below this line after the runs; the runs require the
manifest-pinned data present only in the owner's environment.*
