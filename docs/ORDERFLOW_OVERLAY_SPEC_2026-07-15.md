# Order-flow confirmation overlay on v1.31 — Stage A pre-registration (2026-07-15)

## Decision question

Does gating v1.31 entries on a tick-rule order-flow confirmation state improve
the H1 book, measured first as a per-trade causal screen (Stage A), and only if
that passes, as the registered paired account-MC admission test (Stage B)?

Origin of the hypothesis: the owner proposed using the OrderFlowRosatoEA
(Carmine Rosato masterclass mechanization, `Pokemon/orderflow-ea/`) as a signal
confirmation layer for the deployed v1.31. Priors are adverse and are recorded
here before results: the order-flow EA's own signals tested null standalone on
13 months of FTMO ticks (day-clustered t=1.36 n.s.; timing at the 5th
percentile vs matched random entries on US500), and the only prior
confirmation-layer experiment in this program (the M5/M15 monitor) failed its
event-study controls and was removed. This study either overturns those priors
with a positive pre-registered result or closes the proposal as a recorded null.

## Frozen inputs

* Repo engine at commit `61f42c9` (origin/main). `python backtest/verify_data.py`
  must print `verified 46 OK, 0 missing, 0 mismatched` before the run.
* Tape symbols and geometry: exactly the registered v1.30/v1.31 H1 book via
  `parity_engine.prep_symbol`, `run_h1_timeframe_screen.run_cell` geometry
  (momentum lookback 6, 2 ATR threshold, Wilder ATR(14), W2 wick >= 0.30,
  limit 0.6 ATR, 3-bar pending window, `resolve_v130` exits, stop-first
  ordering), costs from `run_h1_universe_screen.load_symbol` with the frozen
  broker metadata (SHA256 `ba1f3cde...`). **E2 double-cost R values are the
  study currency**, matching the admission frame; E1 reported for context.
* Conditioned symbols: `US_Tech_100` -> US100.cash and `Wall_Street_30` ->
  US30.cash only (the two v1.31 symbols with tick coverage). JP225.cash and
  USDJPY trades are out of scope and untouched by the overlay.
* Order-flow source data (outside-repo, frozen by hash): FTMO-Demo INFO ticks
  (bid/ask changes), account 1513946641, terminal build 5836, pulled
  2026-07-15 via the forward-crawl in `Pokemon/orderflow-ea/bt_fetch.py`:
  - `US100_cash_ticks.parquet` (544,651,318 bytes) SHA256
    `3ea00484508af85b73a7fc123ee8d03c6fa0ad52fb3288680ee12c0699dfa733`
  - `US30_cash_ticks.parquet` (264,454,834 bytes) SHA256
    `f83d41f2600f9b061bf8992519621cd003e958ee411aa2403eca10f24b8ba1a2`
  Coverage: 2025-06-09 -> 2026-07-15 UTC. Files are too large for the repo;
  regeneration is scripted and the hashes above are binding.
* Tick-rule bar engine constants (copied verbatim into the runner from the
  order-flow EA port): 1-minute bars, futures-grid bucketing fp=0.25
  (US100.cash) / 1.0 (US30.cash), direction threshold 0.4 x fp, zero-delta
  minutes dropped, avg|delta| = rolling 30 completed bars (minimum 5, else
  undefined), "strong" = 1.5 x avg|delta|.

## Conditioned set (causal, declared before any outcome join)

* A tape trade is **conditioned** iff its signal decision time
  `t_dec = signal H1 bar epoch + 3600s` (the bar close at which v1.31 places
  the pending) satisfies all of:
  1. `t_dec` is within [09:30, 11:30] America/New_York (DST-correct) — in
     practice the 10:00 and 11:00 ET H1 closes;
  2. the session's ticks exist with first tick <= 09:30 ET and coverage through
     `t_dec` with no gap > 10 minutes in [09:30 ET, t_dec];
  3. the symbol is one of the two conditioned symbols.
* All other trades are **pass-through**: identical in control and overlay arms.
* Order-flow state uses ONLY ticks with timestamp <= `t_dec` (causal). Session
  anchors: NY 09:30 open per zoneinfo; the session delta accumulates from the
  first tick at/after 09:30 ET.

## Arms (two, fixed; no sweeps)

* **Arm P (primary) — session-delta agreement.** Confirm iff
  `sign(session cumulative tick-rule delta at t_dec) == trade direction`,
  where delta is summed from the 09:30 ET open to `t_dec`. Zero net delta
  counts as veto.
* **Arm S (secondary) — opposing-aggression veto.** Veto iff the last
  COMPLETED 1-minute bar before `t_dec` has `dir x delta <= -1.5 x avg|delta|`
  (aggressive flow against the trade at decision time); confirm otherwise.
  If avg|delta| is undefined at `t_dec`, the trade is confirmed (no veto
  without a baseline).

Arm P is the admission-relevant hypothesis. Arm S can at most generate a
follow-up pre-registration on fresh data; it cannot admit anything (fixed
multiplicity rule).

## Stage A statistics and gates

Per arm, on conditioned trades' E2 R values:

* Report n_conditioned, n_confirmed, n_vetoed, mean R of each group, and the
  gap `G = meanR(confirmed) - meanR(vetoed)`.
* **Permutation null:** 10,000 within-symbol permutations of the veto flags
  across conditioned trades (veto counts preserved per symbol), seed
  13020260715. One-sided p = share of permuted G >= observed G.
* Secondary split: same table on the OOS-flagged subset (tape last 30%).

**Stage A passes only if ALL hold for Arm P:**

1. `n_conditioned >= 40` and `n_vetoed >= 10` (power floor; if unmet the
   verdict is INSUFFICIENT SAMPLE, not pass, regardless of point estimates);
2. `meanR(vetoed) < 0` (the gate must remove losing trades, not winners);
3. permutation p <= 0.05 for G;
4. overlay expectancy on conditioned trades (= meanR(confirmed)) exceeds the
   control expectancy on conditioned trades (= meanR(all conditioned)).

## Stage B (conditional; runs only on a Stage A pass)

Wire the Arm P veto into the registered H1 account tape for the two
conditioned symbols (vetoed trades removed; all other events unchanged) and run
the registered paired account engine: same seed/protocol as the USDJPY
admission (20,000-path screen, 100,000-path confirmation), C0 control at 0.30%
uniform risk + USDJPY 0.05% sleeve. Admission gates identical to the USDJPY
study: paired one-sided 95% lower delta above zero, hard-halt no more than the
control plus 0 pp, timeout no higher than control, and the amended absolute
gate at 78.887% both-phases.

## Outcome handling

Any result — pass, fail, or insufficient sample — is committed as
`docs/ORDERFLOW_OVERLAY_RESULTS_2026-07-15.md` with the full JSON artifact.
A Stage A fail closes the proposal: the deployed v1.31 is not modified, and no
re-parameterized variant of this overlay may be tested without a new
pre-registration on data not used here.

No parameter in this spec was chosen after observing any outcome join; the
only data inspected before freezing were trade timestamps' existence and tick
coverage (outcome-blind).
