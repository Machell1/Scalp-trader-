# TradingView Setup — Deriv Scalper Pullback

## Quick start

1. Open [TradingView](https://www.tradingview.com) → **Pine Editor** (bottom panel).
2. Copy the full contents of [`DerivScalperPullback.pine`](DerivScalperPullback.pine).
3. Click **Add to chart**.
4. Set chart to **15-minute** timeframe.
5. Pick a symbol from the validated universe (see below).

## Recommended symbols

| Asset | TradingView symbol |
|---|---|
| Bitcoin | `BINANCE:BTCUSDT` or `COINBASE:BTCUSD` |
| Ethereum | `BINANCE:ETHUSDT` |
| Solana | `BINANCE:SOLUSDT` |
| Nasdaq 100 | `TVC:NDX` or `NASDAQ:NDX` |
| S&P 500 | `TVC:SPX` or `SP:SPX` |
| DAX | `XETR:DAX` or `TVC:DAX` |

**Avoid** FX majors (EURUSD, GBPUSD) on this strategy — backtests show they lose on continuation logic.

## Strategy Tester settings

| Setting | Value | Notes |
|---|---|---|
| Timeframe | 15m | Required |
| Commission | **0.1% per order** | **Script default** — Binance spot taker ballpark |
| Slippage | **3 ticks** | Script default |
| Initial capital | $10,000 | Match your account |
| Order size | % of equity | Tune to risk |

> **Always test with fees on.** A frictionless BTC run (Apr–Jun 2026) showed +9.73% / PF 1.17 / 266 trades — that corroborates the crypto pocket at zero cost, but the edge collapses toward break-even once realistic fees are applied (see `docs/EDGE_PLAN.md` § TradingView corroboration).

To compare frictionless vs realistic in TradingView: Strategy Tester → **Properties** → set Commission to `0` vs `0.1`.

## Default inputs (research-backed)

| Input | Default | Why |
|---|---|---|
| Entry mode | Pullback Limit | Only geometry change that flipped OOS sign on Deriv M15 |
| Pullback distance | 0.6 ATR | Validated on 29-instrument basket |
| Pending expiry | 4 bars | Best on M15 crypto+index proxy |
| Take profit | 4.0 ATR | Shipped combo with pullback exp4 |
| Asset filter | Crypto+Index only | FX loses; crypto+index is the cleanest pocket |

## Alerts

1. Right-click chart → **Add alert**.
2. Condition: strategy name → **Pullback long signal** or **Pullback short signal**.
3. Connect to webhook, email, or mobile for paper/live monitoring.

## Limitations

- TradingView bar-level backtest ≠ Deriv tick data. Confirm on demo before live.
- Yahoo proxy backtests (see `backtest/edge_loop.py`) are for research loops only.
- No configuration has cleared the full **SHIP** gate yet — treat as **observe / minimum size**.

See [`docs/EDGE_PLAN.md`](../docs/EDGE_PLAN.md) for the full hypothesis grid and ship criteria.
