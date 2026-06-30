# Scalp-trader — DerivScalperEA

A multi-symbol momentum **pullback** scalper for Deriv MT5, plus the Python research
harness used to design and (honestly) stress-test it.

> ⚠️ **Status: OBSERVE / MINIMUM-SIZE EXPERIMENT — not a proven money-maker.**
> The entry change in v1.1 is the only thing in an extensive backtest study that
> improved out-of-sample performance across many real instruments, but even it is a
> *small, cost-fragile* edge: roughly break-even after realistic spread, negative at
> 2× cost, and it does **not** clear a deflated-Sharpe / walk-forward ship gate.
> Run it on **demo or minimum size with low-spread execution**. No EA can guarantee
> profit. See [`backtest/RESULTS.md`](backtest/RESULTS.md) for the full evidence.

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
| `deriv_recheck.py` | Re-checks shipped configs on real Deriv M15 indices |
| `chart_*.py` | Result charts (see `docs/`) |

```bash
cd backtest
pip install -r requirements.txt
python fetch_diverse.py        # needs the MT5 terminal open + logged in
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

Systematic hypothesis testing beyond the original 19-candidate grid:

```bash
cd backtest
pip install numpy pandas matplotlib yfinance   # no MT5 needed on Linux
python fetch_yahoo.py                          # proxy data
python edge_loop.py --tf yahooM15              # M15 proxy (short history)
python edge_loop.py --tf yahooH1               # H1 proxy (longer history)
python edge_loop.py --tf derivM15_diverse      # real Deriv data (needs MT5)
```

See `docs/EDGE_PLAN.md` for hypotheses, ship gates, and latest iteration results.


## License / disclaimer

For research and educational use. Trading leveraged products carries substantial risk of
loss. Nothing here is financial advice. Use at your own risk.
