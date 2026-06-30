# TradingView-to-backtest edge plan

This plan is intentionally conservative: find a repeatable edge, or say no edge.
The current repository evidence shows only an observe-grade pullback edge, so new
ideas must improve robustness rather than only improving one chart.

## 1. Planned strategy families

Run the ideas in `edge_loop.py` before looking at results:

1. **Baseline chase stop**: continuation stop entry with 3 ATR take-profit.
2. **Pullback geometry**: continuation after a >=2 ATR impulse, but enter on a
   limit pullback of 0.4, 0.6, or 0.8 ATR with 2-4 bar expiry.
3. **Edge-pocket universe**: repeat the pullback tests only on the previously
   strongest asset classes, crypto and indices.
4. **Small add-on filters**: ADX, EMA slope, efficiency ratio, candle body, and
   volatility-regime filters applied only after the pullback geometry lead.

Do not add extra variants after seeing a near miss unless they are documented
here first and the full trial count is kept in the deflated-Sharpe hurdle.

## 2. TradingView connection workflow

There is no authenticated TradingView API in this cloud machine. Use TradingView
as the data/visual Strategy Tester front-end:

1. Open `tradingview/DerivScalperEdgeLab.pine` in TradingView Pine Editor.
2. Add it to a 15-minute chart for each symbol under test.
3. In Strategy Tester, set realistic commission/slippage for the venue.
4. Export bar data as CSV where possible, or use the broker/MT5 fetcher already
   in this repo.
5. Save files under `backtest/data/<dataset>/<SYMBOL>.csv` with columns:
   `time,open,high,low,close,volume`.
6. Run:

```bash
python3 backtest/edge_loop.py --tf <dataset>
```

## 3. Pass/fail gate for a real edge

An idea is only marked `SHIP` when all of these are true on out-of-sample data:

- At least 3 symbols and at least 250 OOS trades.
- Positive expectancy at realistic cost (`0.02 ATR` per side).
- Positive expectancy under 2x cost stress (`0.04 ATR` per side).
- Walk-forward efficiency >= 0.30.
- Breadth-haircut t-stat >= 1.96.
- Deflated Sharpe probability >= 0.95 across every tested idea.
- At least 60% of OOS calendar quarters positive.
- Effective-trade count clears the minimum detectable effect hurdle.

`WATCH` means a lead is interesting but not validated. `NO-SHIP` means no edge
under this protocol.

## 4. Execution discipline

- Prefer breadth over a perfect single-symbol equity curve.
- Keep costs visible and sweep them every run.
- Treat TradingView Strategy Tester output as exploratory until the same idea
  survives the local multi-symbol OOS loop.
- If no idea clears `SHIP`, keep the EA at demo/minimum size or do not trade it.
