# Free crypto microstructure probe — pre-registration (2026-07-11, evening)

**Question:** does REAL market microstructure data (aggressor-signed flow, open interest,
book depth) carry information about the live engine's trade outcomes — information the
tick-volume proxies provably lacked? This executes the documented VPOF reopening
condition ("do not re-propose without genuinely new data") at $0 using Binance's public
futures archive, on the one validated symbol both venues share: BTCUSD (Deriv tape,
gate-grade 2.5y; Binance BTCUSDT perp data, same period).

**Data (verified to exist 2026-07-11; schemas inspected):**
- `futures/um/monthly/klines/BTCUSDT/15m` — incl. `taker_buy_volume` → signed delta.
- `futures/um/daily/metrics/BTCUSDT` — 5-min open interest, top-trader L/S, taker L/S.
- `futures/um/daily/bookDepth/BTCUSDT` — ±1..5% band depth/notional snapshots (~1/min).
- NOT available free: liquidation archives (Binance discontinued) — stated limitation.
Storage: `backtest/data_crypto/` (gitignored; manifest-pinned once frozen).

**Alignment procedure (pre-registered; lookahead is the #1 risk):** cross-correlate
Binance 15m log-returns vs Deriv BTCUSD M15 log-returns at lags −4..+4 bars; require an
unambiguous single peak; apply that offset. Features use only data whose source
timestamp ≤ the (offset-corrected) Deriv signal-bar close. If the peak is ambiguous,
STOP and report.

**Features (10, locked; z-scores use trailing 96 bars; side-adjusted where directional):**
F1 `delta_frac` (2·takerBuy−vol)/vol at signal bar ·side | F2 `delta_z` ·side |
F3 `cvd6` Σ signed delta over the 6-bar impulse window / Σ vol ·side |
F4 `absorb_z` z of vol/(range/ATR) at signal bar (unsigned) |
F5 `oi_chg_1h` %ΔOI over prior 1h (unsigned) | F6 `taker_ls` ·side | F7 `top_ls` ·side |
F8 `depth_imb1` (bid−ask notional at ±1%)/(sum) ·side | F9 `depth_imb5` same ±5% ·side |
F10 `depth_chg` %Δ(±1% total notional) vs 1h earlier (unsigned).

**Outcome + frame:** per-trade R of the W2-filtered Deriv BTC trades (live engine,
`w2_trades` machinery, real Deriv cost). Gate computed on the stitched-quarter OOS
window (last ~30% of quarters) ONLY; IS reported for context, never gated on.

**S1.5-analog information gate (per feature; screen, kill-point):**
1. OOS Spearman |IC| beyond the 97.5th pct of a 200-permutation null;
2. quarter-stability: same-sign IC contribution in ≥60% of OOS quarters;
3. FRESH beats STALE: the same feature lagged 24h must lose ≥50% of its |IC|
   (separates timing information from persistent-regime correlation);
4. n ≥ 200 OOS trades with valid feature values (depth features: evaluated on the
   window where bookDepth exists; window reported).
Any feature passing all four → the probe ADVANCES (next pre-registration: S2
counterfactual arms). Zero passes → the "cleaner data" thesis dies at $0 for this
data tier; only true L3/MBO (paid) would remain untested.

**Ledger:** this is an exploratory kill-screen (10 feature cells, single symbol);
confirmatory charges begin only at S2. Noted at ledger 129 + screen.

**Honesty constraints:** single symbol (BTC) and single venue-pair — a pass here is a
reason to spend ~$125 on CME depth for the index pair, never a transfer guarantee;
crypto microstructure ≠ futures microstructure. Nothing in this probe touches the live
EA, the FTMO terminal, or the trio configuration.

---
## RESULTS (appended post-run 2026-07-11; protocol hashed pre-run)

- **Alignment: PASSED cleanly** — lag 0 bars, corr 0.9998 (runner-up 0.0165). Venues
  are bar-synchronized; no lookahead pathway existed. Pipeline bug (heterogeneous
  depth-band columns) reported verbatim, fixed, rerun.
- **Gate: ALL 10 FEATURES FAIL.** n=361 OOS W2 trades. OOS ICs −0.065..+0.023, every
  one inside its 200-permutation null envelope (thresholds 0.10–0.14); none passes
  freshness-vs-stale. Real aggressor-signed flow, real open interest, real top-trader
  positioning, and real book-depth imbalance carry NO measurable information about
  the engine's per-trade outcomes at the M15 horizon.
- **Interpretation:** the horizon-mismatch warning proved out empirically — the VPOF
  kill was not (only) a proxy-data problem; even genuine microstructure state at bar
  resolution is uninformative for a 15-minute/2-hour-hold momentum system. Detection
  limits stated honestly: at n=361 only |IC| ≳ 0.10 could clear — but an edge smaller
  than that is not actionable for this engine anyway.
- **VERDICT: the "cleaner data" thesis is dead at $0 for this tier.** Do NOT spend on
  CME depth for the index pair on the strength of microstructure-context hopes; the
  remaining untested tier (true tick-level L3 at sub-minute horizons) would require a
  different STRATEGY, not a better-fed version of this one. Program closed.
