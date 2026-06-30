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

- **Signal:** ≥2 ATR move over 6 bars + same-direction candle → continuation, gated by a
  session-anchored VWAP discount/premium rule.
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
| `strategies.py` | 6 structurally-distinct signal generators + one shared exit/cost/fill engine |
| `crypto_research.py` | Crypto ship-gate edge hunt across all 6 families (DSR, breadth, cost-stress) |
| `crypto_validate_lead.py` | Deep-dive on the extreme-momentum lead (IS/OOS, per-year, cost curve) |
| `fetch_crypto.py` | Pulls real M15 crypto from public `data.binance.vision` dumps — **no terminal** |
| `chart_*.py` | Result charts (see `docs/`) |

```bash
cd backtest
pip install -r requirements.txt

# Deriv arm (needs the MT5 terminal open + logged in):
python fetch_diverse.py        # real Deriv M15 data
python validate_diverse.py     # the headline pullback confirmation
python experiment.py           # full 19-candidate ship-gate on the index basket

# Crypto arm (reproducible; no terminal/credentials needed):
python fetch_crypto.py         # ~190k M15 bars x 16 pairs -> data/cryptoM15/
python crypto_research.py      # 6-family ship-gate edge hunt with honest crypto costs
python crypto_validate_lead.py # extreme-momentum deep-dive + cost-curve chart
```

Market data (`backtest/data/`) is **not** committed — regenerate it with the fetchers above.

### Reproducible crypto feed & the extreme-momentum finding

The Deriv/TradingView feeds need a logged-in desktop terminal, so for an independently
checkable run the crypto arm pulls real Binance M15 from public dumps. The honest result:
median M15 ATR is only ~0.5% of price, so realistic crypto fees (3–6 bp) translate to a
*large* ATR-fraction cost that kills every common-frequency strategy. The **one** family
that stays net-positive at 3–6 bp is **extreme-momentum continuation** — a rare **≥4 ATR**
impulse entered on a ~1.0 ATR pullback. Its gross edge is positive in-sample, out-of-sample
and in *every* year 2021→2026 (t≈8–9), but it is still **observe-grade**: cost-fragile (a
net loser in low-vol 2023) and under-powered on one correlated asset class (N_eff≈3).
EA preset: `InpMomentumAtrMult=4.0, InpPullbackAtr=1.0`. Full evidence + cost curve in
[`backtest/RESULTS.md`](backtest/RESULTS.md) §5.

## Honest limitations

- The edge is **small and cost-fragile**; it needs tight spreads and dies at 2× cost.
- It fails the formal ship gate (deflated Sharpe ≈ 0, sign-unstable across quarters), so
  it is an **experiment to monitor**, not a validated live system.
- Backtests use bar (OHLC) data with pessimistic intrabar assumptions; pending-order
  trailing is not modelled. Live results will differ.

## License / disclaimer

For research and educational use. Trading leveraged products carries substantial risk of
loss. Nothing here is financial advice. Use at your own risk.
