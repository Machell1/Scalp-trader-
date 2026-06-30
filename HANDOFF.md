# HANDOFF — read before changing DerivScalperEA

This brief exists so an agent/dev improving the bot does **not** silently undo a
validated decision or ship an overfit "improvement." Everything below is backed by
real-data backtests in `backtest/` (see `backtest/RESULTS.md` for numbers).

## TL;DR status (be honest about this in any summary)

The strategy is a momentum-**continuation pullback scalper**. After ~2.4 years of real
Deriv M15 testing across 29 instruments + a real-spread cost study, the honest status is:

- **Small, cost-fragile edge that is positive net of *real Deriv* cost on the
  spread-gated 12 majors** — walk-forward gate (§6 `RESULTS.md`): **+0.049 R/trade OOS,
  t +4.76 (+2.23 breadth-haircut), PF 1.12, N=11,790; WFE 1.55; 3/3 OOS quarters; 11/12
  symbols positive.**
- It is **NOT a scale-up money-maker.** At **2× cost stress OOS exp ≈ +0.005 R**
  (break-even). Dies on high-fee venues (Binance 0.1% taker) and wide-spread names.
- Grade: **SHIP at small size** on Deriv spread-gated majors with live spread gate —
  first config to clear the walk-forward + DSR bar. Demo forward-test spread/ATR before
  real capital. Do not market it as more.

## VALIDATED FACTS — do not "improve" these away

1. **Entry geometry IS the edge.** Entering on a **pullback LIMIT ~0.6 ATR back toward
   price** (not a STOP chasing beyond an extended move) is the single change that flipped
   OOS performance positive (5/29 → 18/29 instruments). Reverting to a breakout/stop entry
   destroys the edge. `ENTRY_STOP_BREAKOUT` is kept only as a documented legacy option.
2. **TP = 3.0 ATR.** Widening from 1.5 → 3.0 was independently validated ("let winners
   run"). Don't shrink it.
3. **No AVWAP.** The Anchored-VWAP discount/premium gate produced in-sample sparkle and
   **ZERO out-of-sample edge** (textbook overfit). It is OFF by default (`InpUseVwapGate=false`).
   Do not re-enable it as a default or present it as edge.
4. **The spread/ATR gate is load-bearing, not optional.** The edge survives only where
   round-trip spread is small vs the 1-ATR stop. `InpMaxSpreadAtr` (0.05/side) and the
   pruned `InpSymbolWhitelist` (majors only) are what make the bot viable. Removing either
   re-admits the loser instruments (LTC/BCH/Mid Cap 400/Australia 200/Hong Kong 50) and
   turns the pooled result negative.
5. **It is cost-fragile by construction.** The 1-ATR stop means fees/spread are a large
   fraction of per-trade risk. Any change that increases turnover or trades wider-spread
   instruments must be re-checked against real cost, not frictionless.

## HARD GUARDRAILS for any change (the anti-overfit bar)

A change ships only if it **survives out-of-sample at REAL cost**, judged with the existing
harness. Specifically, a new filter/parameter must:

- Improve the **marginal** OOS expectancy vs the current config (not vs zero).
- Beat a **same-N random subset** of baseline trades (permutation test) — i.e. prove it
  *selects* good trades, not just removes random ones. (This is how AVWAP was killed; see
  `backtest/experiment.py`.)
- Hold up on a **walk-forward / Deflated-Sharpe** check (DSR ≥ 0.95 deflated for the
  number of things tried).
- Survive **2× cost stress** and keep a **powered** sample (don't decimate N).
- Not flip sign across instruments or sub-periods.

Do **not**: add confluence filters by intuition without this gate; tune thresholds to make
a curve look good in-sample; pull/test on Yahoo (use real Deriv M15 via
`backtest/fetch_diverse.py`); claim an edge from a frictionless or single-symbol run.

## PRIORITIZED BACKLOG (with acceptance criteria)

1. ~~**Walk-forward + DSR on the spread-gated universe**~~ **DONE (SHIP @ small size).**
   Runner: `backtest/walkforward_dsr.py` + `fetch_spreadgated.py`. Result in `RESULTS.md` §6.
   DSR hurdle fixed to principled `1/(T-1)` null (commit `79d66b2`). *Next:* demo forward-test
   with live spread logging (backlog #2).
2. **Per-instrument live spread logging** so live spread/ATR can be compared to the
   backtest assumption (catch drift / news widening). *Accept:* EA logs spread/ATR per
   skipped+taken trade; no behavior change.
3. **Maker-vs-taker / fill realism for the pullback LIMIT.** The backtest assumes the
   limit fills at its price; model partial/no-fill and a maker rebate. *Accept:* edge sign
   unchanged under pessimistic fill (non-filling impulses counted as missed winners).
4. **Session/liquidity gate** (only if it passes the bar) — restrict to each instrument's
   liquid hours. *Accept:* marginal OOS improvement + permutation p<0.05; otherwise drop.
5. **Sizing / portfolio heat** review — 0.5%/trade × up to 3 concurrent correlated majors
   can stack; consider correlation-aware concurrency. *Accept:* lower drawdown at equal
   expectancy on the gated set.

Lower priority / likely dead ends (already tested, do not re-propose as novel): ADX gate,
HTF EMA alignment, efficiency-ratio/body filters, volatility-regime band, tick-volume
confirmation — all failed the bar. See `backtest/RESULTS.md` §2.

## Repo map

- `mql5/DerivScalperEA.mq5` — the live EA (v1.2). Multi-symbol; scans its whitelist.
- `tradingview/DerivScalperPullback.pine` — single-symbol Pine port (visual/backtest).
- `backtest/scalper_backtest.py` — faithful bar-level simulator (the source of truth).
- `backtest/scalper_confluence.py` — confluence/geometry extensions (reproduces baseline).
- `backtest/experiment.py` — marginal-contribution + permutation + DSR + ship-gate runner.
- `backtest/validate_diverse.py` — 29-instrument diverse validation.
- `backtest/walkforward_dsr.py` — **backlog #1:** walk-forward + DSR on spread-gated 12 majors
- `backtest/fetch_spreadgated.py` — pull spread-gated universe for walkforward_dsr
- `backtest/RESULTS.md` — all numbers and the reasoning.

## Process notes

- The EA places orders only on the account it's attached to; **demo / min-size first**,
  and the operator decides whether to run it. Don't add anything that auto-scales size or
  trades without the user enabling it.
- Compile `mql5/DerivScalperEA.mq5` in MetaEditor and confirm a clean (0-error) build
  before any live attach — CI does not compile MQL5.
