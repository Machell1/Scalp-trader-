# Edge Discovery Plan — DerivScalper → TradingView

> **Canonical guardrails:** [`HANDOFF.md`](../HANDOFF.md). This doc tracks hypothesis
> iterations; do not ship changes that contradict HANDOFF validated facts.

## Thesis

Momentum **continuation** on M15 works only when entry geometry avoids chasing extension.
The validated lever is a **pullback LIMIT** (~0.6 ATR into the move) after a ≥2 ATR impulse,
with **3 ATR take-profit**, on **crypto + indices** only. FX majors are mean-reverting and lose.

This plan connects that research to **TradingView** (Pine Script strategy) and runs a
**closed-loop hypothesis engine** until something clears the ship gate or we document why not.

---

## Phase 1 — Baseline (known from prior study)

| Config | OOS exp @0.02 | Instruments + | Verdict |
|---|---|---|---|
| Chase STOP beyond extension | −0.047 R | 5/29 | loser |
| **Pullback LIMIT 0.6 ATR** | **+0.007 R** | **18/29** | watch (break-even after cost) |
| Pullback + crypto/index only | +0.038 R @0.02 | — | best pocket, cost-fragile |

**Ship gate (all must pass):**
1. Marginal OOS expectancy > 0 vs baseline
2. Filters: permutation-p < 0.05; geometry: dExp > 0 AND dTotR > 0
3. Walk-forward efficiency ≥ 0.30
4. Deflated Sharpe ≥ 0.95 (adjusted for # trials)
5. Effective N ≥ 250 trades, exp > MDE
6. Positive at 2× cost stress
7. ≥ 60% of OOS quarters positive

---

## Phase 2 — New hypotheses (this iteration)

Prior study tested 19 bolt-on filters — **all failed**. Entry geometry was the only lever.
This loop tests **combinations and refinements** not in the original grid:

### A. Entry geometry sweep
- Pullback offset: 0.4, 0.5, 0.7, 0.8 ATR (original tested 0.3, 0.6)
- Pending expiry: 2 vs 4 bars

### B. Geometry + regime combos (untested pairs)
- Pullback 0.6 + ADX ≥ 20
- Pullback 0.6 + H1 EMA50 alignment
- Pullback 0.6 + struct stop (impulse extreme)
- ~~Pullback + AVWAP~~ **removed** — failed OOS in all tests

### C. Universe restriction
- Crypto + index symbols only (matches EA whitelist)
- Long-only on crypto (trend bias)

### D. Signal tuning
- Momentum window 4 / 8 bars
- Impulse threshold 1.5 / 2.5 ATR
- TP 2.5 / 4.0 ATR with pullback 0.6

### E. Anti-thesis (sanity)
- Fade instead of continuation with pullback
- Market entry at signal (no pullback wait)

---

## Phase 3 — Execution loop

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ fetch data  │ ──► │ edge_loop.py │ ──► │ ship gate   │
│ (Yahoo/MT5) │     │  test grid   │     │ SHIP/WATCH  │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                    ┌────────────────────────────┘
                    ▼
         ┌──────────────────────┐
         │ TradingView Pine     │
         │ backtest + alerts    │
         │ (visual confirm)     │
         └──────────────────────┘
```

1. **Fetch** proxy M15/H1 data (`fetch_yahoo.py` on Linux; `fetch_diverse.py` on MT5)
2. **Run** `edge_loop.py` — ranks candidates, prints ship table
3. **Promote** any SHIP config → update Pine Script defaults + EA inputs
4. **Validate** on TradingView Strategy Tester (same symbol, M15, commission model)
5. **Loop** — add new hypotheses from failures until SHIP or exhaustion

---

## Phase 4 — TradingView deployment

1. Open TradingView → Pine Editor
2. Paste `tradingview/DerivScalperPullback.pine`
3. Add to chart: **M15**, symbol from whitelist (e.g. `BINANCE:BTCUSDT`, `TVC:NDX`)
4. Strategy Tester settings:
   - Commission: ~0.02% per side (or broker spread equivalent)
   - Initial capital: $10,000
   - Order size: % of equity, 0.5% risk
5. Enable alerts for live/paper: `alert()` on entry fill

**Symbol mapping (Deriv → TradingView):**

| Deriv | TradingView |
|---|---|
| BTCUSD | BINANCE:BTCUSDT or COINBASE:BTCUSD |
| ETHUSD | BINANCE:ETHUSDT |
| US Tech 100 | TVC:NDX or NASDAQ:NDX |
| US SP 500 | TVC:SPX or SP:SPX |
| Germany 40 | XETR:DAX or TVC:DAX |
| UK 100 | TVC:UKX |

---

## Success criteria

| Tier | Definition | Action |
|---|---|---|
| **SHIP** | Clears all 7 gates on diverse OOS data | Promote to Pine defaults + EA v1.2 |
| **WATCH** | Positive OOS exp, fails DSR or cost-stress | Demo/minimum size, monitor 90 days |
| **NO-SHIP** | Negative or not significant | Discard, log reason, next hypothesis |

---

## Honest expectations

- The pullback edge is **small** (~break-even after realistic cost on 29 instruments).
- Yahoo proxy data ≠ Deriv ticks; use MT5 `fetch_diverse.py` for final confirmation.
- TradingView bar-level backtest ≈ our Python harness; live will differ.
- **No strategy guarantees profit.** This is systematic research, not financial advice.

---

## Iteration results (2026-06-30)

### Yahoo H1 proxy (19 symbols, ~2y)
- Chase STOP baseline: **+0.148 R** OOS @0.02 cost — beats pullback on H1.
- Pullback 0.6: +0.045 R — worse than chase on this timeframe.
- **Conclusion:** Entry geometry is timeframe-dependent; M15 pullback edge does not transfer to H1.

### Yahoo M15 proxy (16 symbols, ~60d) — crypto+index only
| Candidate | OOS exp @0.02 | vs chase | Verdict |
|---|---|---|---|
| Chase STOP | +0.056 R | — | NO-SHIP |
| **Pullback 0.6 exp4 tp4 (SHIPPED)** | **+0.147 R** | **+0.092** | **WATCH** |
| Pullback 0.6 exp4 | +0.141 R | +0.085 | WATCH |
| Pullback + AVWAP | +0.035 R | −0.021 | removed |
| Fade direction | −0.128 R | — | NO-SHIP |

**Best WATCH:** pullback 0.6 ATR, 4-bar pending expiry, crypto+index universe.
Still fails full SHIP gate (only 1 OOS quarter in 60d Yahoo window; needs MT5 confirm).

### Promoted to TradingView + EA defaults (v1.2 — per HANDOFF.md)
- **AVWAP off by default** (`InpUseVwapGate=false`) — do not re-enable as default
- **Spread/ATR gate** (`InpMaxSpreadAtr`) + pruned whitelist — load-bearing
- Entry: Pullback 0.6 ATR, **3-bar** pending expiry, **TP 3.0 ATR**
- Universe: spread-gated crypto + indices majors only

> Yahoo-proxy "exp4/tp4" WATCH results were **not** promoted — they failed to clear on
> real Deriv cost and contradict HANDOFF validated TP=3.0.

### Next loop hypotheses
1. Pullback 0.6 exp4 + tp4.0 combo on Deriv M15 diverse basket
2. Session-specific windows for crypto (24h) vs indices (US open)
3. Partial TP at 1.5 ATR, runner to 3.0 ATR
4. Confirm exp4 on `fetch_diverse.py` real data when MT5 available

---

## TradingView corroboration (2026-06-30)

### BTCUSDT · Binance · M15 · v1.2 · Apr 30 – Jun 30 2026

| Metric | Frictionless (TV) | With fees (what matters) |
|---|---|---|
| Net P&L | +972 USDT (+9.73%) | **Re-run with commission 0.1%** |
| Profit factor | 1.165 | expect ~1.0–1.1 |
| Win rate | 44.74% (119/266) | ~42–46% |
| Max DD | 6.55% | similar order of magnitude |
| Verdict | Corroborates crypto pocket | edge likely **break-even to small +** |

Python proxy on same window (BTC M15 OOS, shipped config):

| Cost model | Exp/trade | Total R | Win% |
|---|---|---|---|
| Frictionless | +0.137 R | +14.4 | 49.5% |
| 0.02 ATR/side | +0.097 R | +10.2 | 45.7% |
| 0.04 (2× stress) | +0.057 R | +6.0 | 41.9% |
| 0.06 (heavy / ~taker) | +0.017 R | +1.8 | 41.9% |

**NDX (TVC:NDX) on same short window:** Python proxy negative (−0.10 R/trade @ realistic cost, N=24) — not enough M15 index bars in Yahoo; needs a longer TV run.

### Honest read
- TV frictionless +9.7% **matches** the research story: positive gross, cost-fragile.
- One symbol, ~2 months, Binance ≠ Deriv — corroboration only, not proof.
- **Next TV step:** re-run BTC with script defaults (0.1% commission, slippage 3), then `TVC:NDX` M15 with same fees.
