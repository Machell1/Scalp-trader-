# TradingView Setup — DerivScalper Pullback v1.2

> **Read [`HANDOFF.md`](../HANDOFF.md) before changing defaults.** The validated config is
> pullback 0.6 ATR, expiry 3 bars, TP 3.0 ATR, no AVWAP. Yahoo/frictionless TV runs are
> corroboration only — `backtest/deriv_realcost.py` on Deriv M15 is the source of truth.

## Quick start

1. Open TradingView → **Pine Editor**
2. Copy [`DerivScalperPullback.pine`](DerivScalperPullback.pine)
3. **Add to chart** on **M15**
4. Symbol: `BINANCE:BTCUSDT` (crypto pocket) or `TVC:NDX` (index pocket)

## Strategy Tester — fees matter

| Venue | Commission setting | Why |
|---|---|---|
| **Deriv** (what the EA uses) | **0%** — spread is in the price | Script default; edge measured at real Deriv spread via `deriv_realcost.py` |
| **Binance spot** | **~0.1% per order** + slippage | Edge dies here (~0.23 ATR/side on BTC); frictionless +9.7% is not live P&L |

Properties tab → set commission/slippage **before** trusting the equity curve.

## Validated defaults (do not change without harness)

| Input | Value |
|---|---|
| Momentum | 2 ATR over 6 bars |
| Entry | Pullback LIMIT 0.6 ATR |
| Pending expiry | 3 bars |
| Stop / TP | 1.0 / 3.0 ATR |
| AVWAP | Off (not in Pine; off in EA) |

## Symbol mapping (Deriv → TradingView)

| Deriv | TradingView |
|---|---|
| BTCUSD | `BINANCE:BTCUSDT` |
| ETHUSD | `BINANCE:ETHUSDT` |
| US Tech 100 | `TVC:NDX` |
| US SP 500 | `TVC:SPX` |
| Germany 40 | `TVC:DAX` |

Avoid FX majors — they lose on this logic. Avoid wide-spread names (LTC, BCH) per `HANDOFF.md`.

## Alerts

Add alert → strategy → long/short signal condition.
