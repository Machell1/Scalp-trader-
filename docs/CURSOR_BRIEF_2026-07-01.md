# Cursor Improvement Brief — DerivScalperEA (2026-07-01, post-v1.21 deploy)

**Read `HANDOFF.md` first** (validated facts + the anti-overfit bar). This brief is the delta
since the last handoff: what shipped, what changed in your v1.21 after review, new evidence
that bounds the strategy, and the updated prioritized backlog.

---

## 1. Current deployed state (live, real money)

- **EA:** v1.21 bar-close exit engine — your branch `cursor/bar-close-exit-engine-0c97`
  **+ review-fix commit `014a9fa`** — merged to `main` (`c90e722`, then `b496c23`).
- **Running live** on the Deriv real account (magic 770077), single instance, chart BTCUSD,
  `ManageOnBarClose=yes`, **all 12 spread-gated majors** scanning, AutoTrading on.
- Verified via terminal Experts log: `DerivScalperEA v1.21 ready ... Scanning 12 symbols`.
- Day-1 (old per-tick engine) results: +$5.41, +0.96R over 15 trades — details in
  `docs/LIVE_TRADE_ANALYSIS_2026-07-01.md`. **Those trades are NOT evidence about the
  validated strategy** (wrong exit engine); post-v1.21 trades are.

## 2. What changed in your v1.21 after adversarial review — do not regress these

A 3-agent review (fidelity / MQL5 correctness / regression) confirmed your implementation was
structurally faithful, but flagged one **blocker** + majors, all fixed in `014a9fa`:

1. **`ApplyDesiredSL()` (the blocker fix).** Your bar-close modify was one-shot and unguarded:
   if the computed SL was at-or-through the market (post-close spike / session-reopen gap) the
   entire modify — **lock included** — was silently skipped and never retried (re-arm required
   the *next* close ≥ +0.25 ATR again), so a harness-locked ~0R trade could ride to −1R.
   Semantics now: desired SL is stored in `PositionMgmtState.desiredSL` and applied via
   `ApplyDesiredSL` — **at/through market ⇒ PositionClose** (the harness's stop was already hit
   this bar), within stops/freeze distance ⇒ clamp just outside, **rejection ⇒ retry every
   heartbeat** (ratchet is idempotent). Live proof this matters: the old engine logged
   **9× `[invalid stops]`** on one trade at 09:18 on 07-01.
2. **Frozen signal-ATR persists across reloads** via terminal globals `DSv121_atr_<posId>`
   (set in `RegisterPositionState`, deleted in `PruneClosedPositionStates`). Your in-memory-only
   version silently degraded to current ATR after any reload.
3. **Reload bar-count off-by-one:** `bt <= entryBar` → `bt < entryBar` (time exit fired one bar
   late after mid-trade reloads).
4. **`iTime()==0` guards** in bar-close, per-tick, and scan paths (history desync would corrupt
   bar clocks / double-count → premature time exit).
5. **Scan-clock consumption at capacity:** clocks now advance even when `MaxConcurrent` blocks
   the scan (your version scanned mid-bar when a slot freed — recreating the anchor artifact).
   Unseeded clocks (symbol had no data at init) seed without scanning.
6. **`RetryFailedAtrHandles()`** (commit `b496c23`): `AddSymbol` no longer silently drops a
   symbol whose `iATR` fails at terminal startup (observed live: France 40 lost for a session,
   err 4805); the heartbeat retries until the handle recovers.

If you refactor management code, preserve these exact semantics — they are what makes the live
EA the *validated* engine.

## 3. New evidence since the last brief (bounds, not busywork)

- **Timeframe-locality (new, important):** the strategy has **no edge on daily bars.**
  TradingView runs of the exact v1.2 Pine config: NDX 1D 1985–2026 (41y) frictionless
  **PF 0.988, −0.9%** (coin flip; −18.6% with 0.1% fees); SPX 1D 1871–2026 (155y) frictionless
  **PF 0.843, −19.4%**. A 2-ATR-in-6-bars impulse mean-reverts at the daily horizon.
  ⇒ **Do not propose higher-timeframe ports or "run it on dailies" features.** The edge is
  intraday (M15) momentum microstructure on tight-spread crypto/index CFDs. Period.
- **Venue/fee boundary (reconfirmed):** NDX M15 on TradingView at 0.1%/order + slippage:
  PF 0.103. Nothing new — % -of-notional fees kill a 1-ATR-stop scalper; Deriv's tight
  spread on majors is the habitat.
- **Live cost/fill assumptions continue to hold** (day-1 forensics): spread paid median
  0.0083 ATR/side, fills at-or-better than limit, stop overshoot ≤ 0.014R.

## 4. Backlog (prioritized, with acceptance criteria)

**P0 — Acceptance check of v1.21 (open; blocked only on trade accumulation).**
After ≥10–15 post-deploy trades: run `backtest/live_trade_report.py`, verify the exit mix is
*possible* under `simulate_symbol_c`: **zero moved-stop exits with zero elapsed M15 bar-closes**,
TP exits now occur, scratch swarm gone. If violated → engine bug, halt and diagnose.
(No trades yet as of this brief — quiet session hours.)

**P1 — Fill realism study (old #3), now unblocked by the SIGNAL/SKIP logs.**
The harness assumes the pullback LIMIT fills at its price whenever touched; day-1 data showed
75% fill rate vs ~59% modeled and frequent price improvement (conservative), but N=20.
With the new logs, reconcile weekly: signals vs placements vs fills vs harness-predicted fills
on the same bars. *Accept:* harness fill model shown conservative or corrected; edge sign
unchanged under pessimistic fill.

**P2 — Session-gate study on the pullback config (old #4).**
Day-1 hint: thin-hours bucket −1.97R vs +2.82R elsewhere (N tiny, descriptive). Test a
pre-registered session window on HISTORICAL data through the full gate
(`experiment.py`: marginal vs baseline + permutation + WFE + DSR + 2× cost). The old session
test failed on the *chase* entry; it has never been run on the pullback config. *Accept:* per
HANDOFF hard guardrails; otherwise drop.

**P3 — Correlation-aware concurrency (old #5).**
0.5%/trade × 3 concurrent correlated majors stacks ~1.5% heat; day-1 saw 4 same-direction
Tech-100 entries in 70 min. Consider per-cluster caps (crypto / US indices / EU indices).
*Accept:* lower portfolio drawdown at equal pooled expectancy on the spread-gated set.

**P4 — Hygiene / small fixes (from the review, deferred as minors):**
- `LogSkip` prints `moveAtr` (positive = falling) while `SIGNAL` prints impulse (negative =
  falling) — align sign conventions before anyone audits the impulse gate from logs.
- Log volume: "no impulse" SKIP ≈ 1,100 lines/day; add a verbosity input (keep gate-skips,
  make no-impulse optional).
- `g_pendingSigAtr` broker-side-expiry leak (bounded; prune in a periodic sweep).
- Multi-bar backfill after connection outage increments `barsClosed` once, not per bar
  (late time exit); consider counting via `iBarShift(entryBarTime)` instead of ++.
- If the whitelist changes across a reload, an open position with `SymbolIndex()<0` gets
  time-exit but no lock/trail — resolve state by symbol string, not index.
- `live_trade_report.py`: M1 MAE/MFE window leaks ~2 min of post-exit path (truncate at exit
  time; replace the flat `min(mae,1.05)` clip); `order_calc_profit` uses current FX rates for
  historical DE40/UK100 R (fine for forensics, note it).
- Two benign warning-43 casts (`long`→`datetime` at ~:521/:626) — add explicit casts.
- **Verify ATR definition parity:** harness uses Wilder ATR; confirm MT5 `iATR` smoothing
  matches (if it differs, every ATR-scaled quantity is subtly off — measure the delta on real
  data before changing anything).

**Do-not-do list (unchanged + extended):** AVWAP as default, breakout entry as default, TP<3,
removing the spread gate/whitelist, FX majors, high-fee venues, **daily/HTF ports (new)**,
any filter that doesn't clear the HANDOFF gate.

## 5. Process notes (deploy runbook — this cost us a silent stale deploy)

1. Edit `mql5/DerivScalperEA.mq5` in the repo → compile repo copy (0 errors) → commit/push.
2. Copy to `<terminal-data>\MQL5\Experts\` → compile there.
3. **A command-line MetaEditor compile does NOT hot-reload a chart-attached EA.** You MUST
   restart the terminal (graceful `CloseMainWindow` → relaunch; pendings/SL/TP are server-side,
   AutoTrading state persists) or manually remove/re-attach the EA.
4. Verify in `<terminal-data>\MQL5\Logs\<date>.log`: the `v1.xx ready ... Scanning 12 symbols`
   init line, **and** that SKIP/SIGNAL lines carry exactly ONE chart tag (single instance).
5. Never mark a deploy done without step 4 — the init line is the only proof the new build runs.

## 6. Repo map delta

- `docs/LIVE_TRADE_ANALYSIS_2026-07-01.md` — day-1 forensics (old engine) + P0 spec.
- `backtest/live_trade_report.py` — forensics extractor (R in account currency via
  `order_calc_profit`); `backtest/live_trades.json` — day-1 raw data.
- `mql5/DerivScalperEA.mq5` — v1.21 + review fixes (`ApplyDesiredSL`, ATR persistence,
  clock guards, `RetryFailedAtrHandles`).
- HANDOFF backlog #0 (exit-engine fidelity) and #2 (spread logging) are **done**.
