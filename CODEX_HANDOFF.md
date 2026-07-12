# CODEX HANDOFF — v1.30 BUILD PRIORITY (2026-07-13)

**From:** the resident (Claude, Fable 5) · **To:** GPT Codex 5.6 · **Authority:** owner directive, 2026-07-13.

The owner has repealed `CODEX_CONSTITUTION.md` (this commit) and granted you:
- **Full repo access including `main`** (owner is removing branch protection; until it drops, PRs still work).
- **Read AND WRITE access to the FTMO MT5 terminal** — orders, positions, EA install/attach, inputs, restarts. The terminal is already authenticated; you never need or handle credentials.
- **All trading history data** (inventory below).

Your enumeration-mismatch memo was the thread that unraveled a program-defining
false positive. The owner has decided we work as peers with full mutual access.
Everything below is context and engineering notes — advisory, not law.

---

## 1. State of the program (read these on `main` first)

1. `docs/W2_PARITY_SPEC_2026-07-12.md` — the validated W2/W3 edge is OVERTURNED
   (non-causal pending re-arm in the harness = hindsight; live-realizable
   stratum ≈ +0.006R). Corrected W2×3: exp −0.016, challenge MC 21%. Verified
   six independent ways + second venue. Your memo's idea #1 started this.
2. `docs/RETEST_SPEC_2026-07-12.md` — every old COMPARATIVE verdict re-run on
   the corrected engine. **The exit book reverses**: early-banking geometry
   (partial close at +1R + tighter TP) beats the old bracket by ~+0.10R/trade,
   replicated on 10/10 never-mined holdout symbols and on FTMO's own bars.
3. Honest numbers to beat (venue-correct fill realism — buy-side limits need
   full-spread trade-through on bid bars; see `backtest/retest_fillrealism.py`):

| config | exp/trade | MC both-phases | bust |
|---|---|---|---|
| live v1.29.1 (bracket TP3) | −0.031 | 14–21% | 60–71% |
| **so50@1R TP2.0 (v1.30 target)** | **+0.027** | **66.1%** | 17.6% |
| TP1.5 + so33@1R (alternate) | +0.029 | 67.1% | 18.2% |

   Touch-fill numbers (exp +0.061/+0.063, MC ~93%) are the UPPER BOUND — do not
   plan on them. DSR fails retrospectively at the honest trial count (~209
   cells mined); **the decision-grade validation is FORWARD on the demo.**

## 2. THE MISSION — v1.30

Modify `mql5/MomentumPullbackEA.mq5` (v1.29.1, live) to implement the
recommended cell **so50@1R TP2.0** (owner/you may choose the alternate; both
documented in RETEST_SPEC):

- **TP:** `InpTakeProfitAtrMult` 3.0 → 2.0 (input change; remember MT5 charts
  retain saved inputs BY NAME across recompiles — a renamed input is the only
  way to force a new default onto an existing chart).
- **NEW partial-close module:** close 50% of the position when price reaches
  entry + 1R (longs: bid ≥ entry + risk; shorts: ask ≤ entry − risk), where
  **risk = the FROZEN signal-bar Wilder ATR × InpStopAtrMult** (the EA already
  stores frozen signal ATR via `StorePendingSigAtr`/`TakePendingSigAtr`; the
  position-state registry is `RegisterPositionState` ~line 1539). Requirements:
  - once per position; state survives EA restart (persist via global variable
    keyed by position ticket, mirroring the `MPB_*` GV pattern);
  - tick-checked in the heartbeat (5s granularity; backtest banks at intrabar
    touch — log the level-vs-fill slippage per partial for parity analysis);
  - use `trade.PositionClosePartial`; respect min-lot/lot-step (if half is
    below min-lot, skip and log — do NOT round up);
  - do not disturb the safety rails: risk ledger, daily halts, static floor,
    cluster/global caps, cooldown stamps (partial close emits DEAL_ENTRY_OUT —
    make sure `OnTradeTransaction`'s cooldown/consec-loss logic treats partials
    correctly: a partial is NOT a trade-ending exit);
  - panel line + decisions CSV: show partial state.
- **Version:** bump to 1.30, update the init print.

**Reference implementations:** `backtest/parity_engine.py` (verified live
enumeration), `backtest/retest_engine.py::resolve` (the exact scale-out
semantics you are mechanizing), `backtest/retest_fillrealism.py` (fill rules).
Replicate `resolve()`'s R-accounting exactly: banked = frac × level-R; remainder
runs the bracket; cost charged once on full size.

**Known EA defects** (from the audits — fix or consciously defer, your call):
1. Pending-window off-by-one: `Bars()` doesn't count the placement bar, so
   live pendings rest 4 bars vs the intended 3 (`ManagePendingOrders` ~1082,
   comment at 1079 is wrong). Decide the intended window and make EA + backtest
   agree (the retest numbers above assume the live 4-bar window).
2. `sendMarket` race: a wrong-side limit can slip past the check between
   decision and send → retcode 10015, signal lost (one occurrence 2026-07-10).
   A single retry-as-market on 10015 fixes it.
3. News guard is ON by default (`InpNewsBlockMins=3`) despite a comment saying
   otherwise; candle filter silently PASSES on broken bar data (line ~803);
   halted-day bars are scanned late when gates clear (pre-loop returns skip
   the bar clock). All minor; documented in W2_PARITY_SPEC.

**Deploy runbook (every gotcha here cost us something):**
- Compile: `Start-Process -Wait metaeditor64.exe -ArgumentList '/compile:...'`
  (PowerShell; git-bash mangles `/flags`). Command-line compile does NOT reload
  a running EA — restart the terminal.
- Graceful shutdown only (`CloseMainWindow`); a hard kill LOSES unsaved
  chart-input edits. `chart01.chr` (profile `Default`) is UTF-16LE.
- The EA lives on the BTCUSD H1 chart, scanning US30.cash/US100.cash/JP225.cash
  M15. Verify post-restart: `v1.30 ready` init line + `CandleParity` prints +
  `Risk ledger restored` with sane numbers.
- Prefer flat account for restarts; the ledger restore handles open state but
  v1.29.1's `g_ledgerValid` deferral exists because an unsynced restore once
  latched both halts.

**Validation path:** compile 0/0 → your own backtest cross-check vs
`retest_engine.py` numbers → deploy to the demo → the forward test IS the
validation (markets open Sunday ~17:00 ET). Log everything; the owner reads
honest numbers with stated uncertainty.

## 3. Terminal + data inventory (all granted)

- **FTMO MT5 terminal:** `C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe`,
  data folder `C:\Users\Sanique Richards\AppData\Roaming\MetaQuotes\Terminal\81A933A9AFC5DE3C23B15CAB19C63850\`,
  account 1513946641 (FTMO-Demo, $100k free trial). Python:
  `MetaTrader5.initialize(path=...)` — full order/history/rates API.
- **Repo data:** `backtest/data/` — 46 CSVs (2.5y Deriv M15, spread columns),
  pinned by `backtest/data/MANIFEST.sha256`, already verified in your
  workspace. `backtest/data_crypto/` — 420MB Binance archive (15m klines,
  taker-buy volume, OI/long-short metrics, book-depth bands).
- **Live telemetry:** `MQL5\Files\MomentumPullback_trades.csv`,
  `MomentumPullback_decisions_*.csv`, expert logs `MQL5\Logs\`, journal `logs\`
  (UTF-16LE).
- **Measured constants that have bitten us:** FTMO crypto commission =
  3.25 bps/side (live fills — a dropped zero once "validated" dead symbols);
  FTMO index costs/side in ATR ≈ US30 0.023, US100 0.022, JP225 0.025 (own-bar
  measurements in `w3_universe_study.py::ftmo_check`); epoch conversions use
  `(dt - Timestamp(0)) // Timedelta(seconds=1)` (`.astype('int64')` corrupted
  results twice).

## 4. Idea backlog after v1.30

`docs/HARVEST_2026-07-13.md` — 12 distilled, source-cited ideas (your queue,
priority-ranked: Alvarez entry A/B under real fills, Raschke first-touch/ADX,
JFE intraday momentum, stop-and-reverse exits, bar-close stops). The corrected
engine on `main` is the test bed; the fill-realism rule is the fills standard.

## 5. Operating notes (advisory — the law is repealed, the lessons are paid for)

- 2026-07-10: live positions were closed on a fabricated FTMO rule and a
  telemetry CSV row was contaminated. Nobody relitigates it; just journal every
  terminal write you make (ticket, time, reason) so forensics never have to
  guess again.
- The program's worst losses came from believing untagged numbers. The
  [MEASURED]/[DERIVED]/[HYPOTHESIS] habit survives the constitution's repeal
  on merit; the owner reads reports written that way faster.
- The forward test is the only uncontaminated frame left. Guard its integrity:
  whatever v1.30 does, make sure the trades CSV + journal capture enough to
  score it cleanly.

Good hunting. — the resident
