# Scalp-trader — MomentumPullbackEA (FTMO build)

Multi-symbol H1 momentum **pullback** EA + the Python research harness that designed,
gated, and continuously audits it. Formerly DerivScalperEA; the live deployment is now
the FTMO $100k evaluation track.

> ⚖️ **AI contributors (Codex, Cursor, all others): [`CODEX_CONSTITUTION.md`](CODEX_CONSTITUTION.md)
> is binding — branch law, data integrity, anti-overfit law, live-system prohibition.**
>
> 🛠️ **Modifying anything (human or AI agent — including Cursor)? The rules below are
> binding.** Every claim in this repo carries a pre-registered, SHA256-hashed spec in
> `docs/` with results appended under the hash. Read `HANDOFF.md` + the dated
> `docs/*_SPEC_*.md` files before proposing changes.

## LIVE STATE (2026-07-13) — do not regress

- **EA:** `mql5/MomentumPullbackEA.mq5` **v1.32**, H1 default, magic **771025**. The host
  chart is irrelevant because the EA scans each symbol from its 5-second timer.
- **Universe (earned per-symbol through gates):** `US30.cash, US100.cash, JP225.cash,
  USDJPY`; clusters `US30.cash|US100.cash;JP225.cash;USDJPY`. USDJPY is independently
  capped at 0.05% risk. Crypto is COST-DEAD on FTMO (measured commission ≈3.25 bps/side);
  gold failed six independent methods — do not re-add.
- **Entry engine (FROZEN — this is the strategy):** momentum 6 bars ≥ 2.0 ATR (Wilder 14,
  self-computed, Python-parity 0.00000), pullback LIMIT 0.6 ATR, expiry 3 bars
  (bar-counted), **W2 candle filter: signal bar must carry an adverse-side wick ≥ 0.30 ATR**
  (contested impulses continue; clean climax bars are the WORST trades — 58k-trade result).
- **Exits:** SL 1.0 ATR, bank 50% at +1R, remainder TP 2.0 ATR, 8-bar time exit.
- **Risk:** 0.30% for the confirmed index trio and 0.05% for USDJPY. Guards: daily
  −4% halt (cancels pendings), trailing 8% + static 91% floor (restart-proof ledger),
  max 8 fills/day, 1/cluster, freshness + news guards, panel.
- **v1.32 portability rails:** configured broker suffixes resolve only when unambiguous;
  signal OHLC and live spread gates fail closed. Symbols deliberately added beyond the
  confirmed quartet are capped at 0.05% probe risk and one shared cluster seat by default.

M5 is not validated because this repository has no canonical M5 tape. M15 is the original
research timeframe, but it does not match H1 account results. Shorter timeframe work must
be treated as a separate research cell: preserve the H1 defaults in production, use real
costs, and pass the same OOS, 2×-cost, breadth, DSR, and coupled-account gates before any
new entry logic or asset becomes a live default.

## Rules for changes (Cursor: these are hard constraints)

1. **The entry/exit engine and W2 filter are frozen.** Adaptation lives in research,
   not live logic. Performance-chasing is 0-for-5 here (entry AND sizing forms).
2. **Nothing ships without the gate:** pre-registered hashed spec → stitched-quarter OOS
   at real per-instrument cost → beats matched random/placebo controls → ≥8/12 symbol
   stability → DSR ≥ 0.95 at the CURRENT trial ledger (129) → 2× cost stress → challenge
   MC not worse → flag-gated input, default OFF → user sign-off.
3. **Dead ends (do not re-propose without new data):** VP-shielded stops & order-flow
   cuts (killed at gate), weighted confluence scoring (0-for-4; the ≥85 rule = −0.31R),
   wick-rejection/pin-bar/sweep/wick-pressure standalone entries, EMA/ADX/session/volume
   filters, BE-lock/trail/scale-out/conditional holds, graded DD throttles, per-symbol
   performance allocators, crypto-on-FTMO, gold anywhere.
4. **FTMO compliance is load-bearing:** order comment stays `MomPullback` (broker-visible;
   never "scalper"/other-broker names); risk fixed per trade; one-sided-betting guarded by
   clusters; never trade during the forward test from external tools (a Codex close already
   contaminated one datapoint).
5. **Canonical workspace = this repo.** The live terminal copy is deployed FROM here
   (patch script → compile 0/0 → graceful restart → verify init line + panel). Chart-saved
   inputs persist BY NAME across recompiles — renaming an input is the only way a new
   default applies. Hard kills lose chart-input edits; always close the terminal gracefully.
6. **Data honesty:** FTMO history ≈ 9 months (directional only — never gate-grade);
   gate-grade = 2.5y real Deriv M15 in `backtest/data/`. Epoch conversions must use
   `(dt - Timestamp(0)) // Timedelta(seconds=1)` (two datetime bugs shipped otherwise).

## What changed in v1.1 (the validated improvement)

The original EA entered with a **STOP order placed just beyond price after a ≥2 ATR
move** — i.e. it bought/sold at *maximum extension*, where continuation is weakest and
mean-reversion strongest, then defended it with a 1 ATR stop that sits *inside* the
normal retrace band. On real Deriv M15 data that entry was a net loser out-of-sample.

v1.1 replaces it with a **PULLBACK entry**: after the same momentum impulse, place a
**LIMIT order ~0.6 ATR back toward price** and enter on the retrace, so the fill is
better and the stop sits behind the pullback floor.

On a **diverse, low-correlation 29-instrument Deriv M15 basket** (FX, metals, energy,
crypto, global indices; mean correlation 0.15, ~5.7 effective independent bets) the
pullback entry took the strategy from **5/29 to 18/29 instruments positive** out-of-sample
— the only change in the whole study to flip the sign. The take-profit was also widened
to **3.0 ATR** ("let winners run"), which was independently validated.

### Where the edge lives (and doesn't)
Continuation only works on **trending assets**. Out-of-sample expectancy by asset class
(pullback entry, realistic cost):

| Asset class | OOS expectancy | Verdict |
|---|---|---|
| CRYPTO | +0.042 R | works |
| INDEX (global/US) | +0.034 R | works |
| ENERGY | +0.015 R | weak |
| METAL | +0.007 R | marginal |
| **FX majors/crosses** | **−0.028 R** | **loses — excluded** |

So the EA's **default universe is restricted to crypto + indices** (`InpSymbolWhitelist`).
Clear that input to scan all non-synthetics.

## EA (mql5/DerivScalperEA.mq5)

- **Signal:** ≥2 ATR move over 6 bars + same-direction candle → continuation.
- **Entry:** `InpEntryMode` = `ENTRY_LIMIT_PULLBACK` (default, validated) or
  `ENTRY_STOP_BREAKOUT` (legacy). Pullback distance = `InpPullbackAtr` (0.6 ATR).
- **Exits:** 1 ATR stop, 3 ATR take-profit, break-even lock at +0.25 ATR, 0.5 ATR trail,
  8-bar time exit.
- **Risk rails:** 0.5%/trade, ≤3 concurrent, ≤20/day, 3% daily-loss halt, 15% drawdown
  halt, 4-consecutive-loss pause, spread filter.

**Install:** copy `mql5/DerivScalperEA.mq5` into `MQL5/Experts/`, compile in MetaEditor,
attach to any M15 chart. The EA scans its own symbol list — the chart symbol only drives
the bar clock. **Demo / minimum size first.**

> This EA places orders on whatever account it is attached to. The author of this repo
> does not place trades on your behalf; you choose when (and whether) to run it.

## Backtest harness (backtest/)

Real-data, anti-overfitting research framework. Results are in R-multiples (instrument-
agnostic); costs are modelled as a fraction of ATR and always swept.

| File | Purpose |
|---|---|
| `scalper_backtest.py` | Faithful bar-level simulation of the EA logic |
| `scalper_confluence.py` | Adds the candidate confluences + pullback geometry (reproduces the baseline exactly) |
| `experiment.py` | Marginal-contribution runner: permutation test, breadth haircut, WFE, DSR, cost-stress, ship gate |
| `validate_diverse.py` | Confirms the pullback lead on the diverse 29-instrument basket |
| `fetch_diverse.py` | Pulls real Deriv M15 data via the local `MetaTrader5` package |
| `deriv_realcost.py` | **Real Deriv spread → ATR cost**; spread-gate evidence (source of truth) |
| `walkforward_dsr.py` | **Backlog #1:** walk-forward + DSR on 12 spread-gated majors |
| `fetch_spreadgated.py` | Pull spread-gated universe CSVs (MT5 required) |
| `deriv_recheck.py` | Re-checks shipped configs on real Deriv M15 indices |
| `chart_*.py` | Result charts (see `docs/`) |

```bash
cd backtest
pip install -r requirements.txt
python fetch_diverse.py        # needs the MT5 terminal open + logged in
python fetch_spreadgated.py    # 12 spread-gated majors for walk-forward gate
python walkforward_dsr.py      # backlog #1: walk-forward + DSR at real spread cost
python validate_diverse.py     # the headline pullback confirmation
python experiment.py           # full 19-candidate ship-gate on the index basket
```

Market data (`backtest/data/`) is **not** committed — regenerate it with `fetch_diverse.py`.

## Honest limitations

- The edge is **small and cost-fragile**; it needs tight spreads and dies at 2× cost.
- It fails the formal ship gate (deflated Sharpe ≈ 0, sign-unstable across quarters), so
  it is an **experiment to monitor**, not a validated live system.
- Backtests use bar (OHLC) data with pessimistic intrabar assumptions; pending-order
  trailing is not modelled. Live results will differ.

## TradingView (tradingview/)

Pine Script port of the EA for visual backtesting and alerts on TradingView.

1. Copy `tradingview/DerivScalperPullback.pine` into the Pine Editor.
2. Chart: **M15**, symbol from crypto/index whitelist (e.g. `BINANCE:BTCUSDT`, `TVC:NDX`).
3. See `tradingview/README.md` for symbol mapping and Strategy Tester settings.

## Edge discovery loop (backtest/edge_loop.py)

Exploratory grid only — **must not ship without** `experiment.py` / `deriv_realcost.py` on
real Deriv M15. Yahoo runs are for quick screening, not validation (see `HANDOFF.md`).

```bash
cd backtest
pip install -r requirements.txt
python fetch_diverse.py                        # real Deriv data (MT5 required)
python deriv_realcost.py                       # real spread cost study
python edge_loop.py --tf derivM15_diverse      # hypothesis grid on real data
```

See `docs/EDGE_PLAN.md` for hypotheses, ship gates, and latest iteration results.


## License / disclaimer

For research and educational use. Trading leveraged products carries substantial risk of
loss. Nothing here is financial advice. Use at your own risk.
