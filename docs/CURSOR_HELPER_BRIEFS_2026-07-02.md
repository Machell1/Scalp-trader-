# Cursor helper brief — 2026-07-02 (Composer 2.5 + GPT-5.5)

**Command structure:** Fable 5 (external, driving this task) is the director and owns the
validation gate. You two (Composer 2.5, GPT-5.5) are implementation helpers. **Nothing you
produce reaches the live EA until Fable 5 runs it through the harness gate.** Read `HANDOFF.md`
and `backtest/RESULTS.md` (esp. §7) before doing anything.

## Live state (real money, do not regress)
- EA **v1.23** live on Deriv real acct: PURE BRACKET exits (SL 1 ATR / TP 3 ATR / 8-bar time
  exit, no lock/trail — `InpUseLockTrail=false`), pullback-LIMIT entry 0.6 ATR, TP 3, momentum
  2 ATR/6 bar, spread/ATR gate 0.05, 12 spread-gated majors. All validated. Do not touch.

## What Fable 5 backtested tonight (real Deriv M15, 12 majors, real per-instrument cost) — the results/observations you were asked to build on
1. **Exit-ladder study → SHIPPED v1.23.** The BE-lock+trail ladder was truncating winners.
   Pure bracket: OOS exp +0.050→**+0.078R**, avg win 1.02→**1.72R**, ≥+2R 7.5→16.6%, 2×-cost
   margin +0.007→**+0.034 (5×)**. Verified by exact independent replication. `exit_ladder_study.py`.
2. **`hold 8→16` (unconditional):** VALIDATED (+0.0774R, avg win 2.24R, ≥+2R 22.4%, 12/12
   symbols) but **GATED** — promote only after ~30–50 live pure-bracket trades track the backtest.
3. **Cancel-pending-on-setup-violation:** **REJECTED.** `pending_invalidation_study.py` — the
   deep-V fills a "runaway cancel" would remove are the system's BEST trades (removed-exp +0.06
   to +0.26R, CIs exclude 0). Do NOT re-propose runaway cancels.
4. **Profit-conditional time exit (extend winners to 16, cut losers at 8):** **REJECTED.**
   `cond_hold_study.py` — no expectancy gain over baseline (paired t ≈ 0), and the simpler
   unconditional hold16 dominates. Do NOT re-propose conditional holds.

Also dead ends (do not re-propose as novel): AVWAP, ADX, HTF-EMA, efficiency-ratio/body,
vol-regime band, session gate on the chase entry, tick-volume, trailing "profit protection",
any higher-timeframe port (no daily edge — RESULTS §7 addendum).

## Your tasks (deliver as ONE PR each to a `cursor/*` branch; NO EA behavior change)
**A. New candidate STUDIES (not EA edits).** Propose 3–5 *new* pre-registered hypotheses that
could raise win size or expectancy WITHOUT the failure modes above. For each, add one
self-contained study script modeled on `exit_ladder_study.py`: real per-instrument Deriv cost,
stitched-OOS quarters, PAIRED per-signal t-stat, DSR deflated for the cumulative trial count
(now 68), 2× cost stress, win-size metrics. Do NOT tune to pass; report honest verdicts. Ideas
worth pre-registering (pick, don't just take): partial-scale-out at +1.5R with runner to TP;
ATR-adaptive TP (TP = f(vol regime)); a single pyramiding add at +1R with stop-to-BE (needs
scale-in support in `simulate_symbol_c` — additive, off by default, MUST reproduce baseline
byte-exact); asymmetric TP for crypto vs indices. **Do not modify the EA in task A.**

**B. Backlog tooling (no strategy change).** (1) Make `fill_realism.py` + the acceptance check
in `live_trade_report.py` a single weekly report entrypoint. (2) Encode the hold16 promotion
trigger (≥30–50 live pure-bracket trades tracking backtest) as a check in HANDOFF + a helper.
(3) Run `atr_parity.py` and report the Wilder-vs-MT5-iATR delta with a recommendation.

## Hard rules (from HANDOFF)
- A change ships only if it beats the current config OUT-OF-SAMPLE at REAL cost, passes the
  paired/permutation test, walk-forward + DSR ≥ 0.95, 2× cost stress, stays powered, and doesn't
  flip sign across symbols/quarters. Frictionless/single-symbol/Yahoo results are not evidence.
- Any touch to `scalper_backtest.py` / `scalper_confluence.py` must keep the baseline-reproduction
  test byte-exact (maxdiff 0.00e+00). New harness params default OFF.
- Deploy runbook (Fable 5 handles deploys): compile → review → terminal restart → verify the
  `vX.YZ ready ... Exits=... Scanning 12 symbols` init line. You do not deploy to the terminal.

Push your branch; Fable 5 will gate every study before anything reaches the EA.
