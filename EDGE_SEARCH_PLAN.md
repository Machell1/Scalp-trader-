# Edge search plan — TradingView-sourced multi-asset swing strategies

This document is the plan, written **before** any candidate below was run. The
goal: connect to TradingView for real data, then search for a genuine,
cost-resilient trading edge using the same anti-overfitting statistical gate
already built in this repo (`backtest/experiment.py`), and report the result
honestly whether or not anything ships.

## 1. Why pivot away from M15 scalping

The existing `DerivScalperEA` research (see `backtest/RESULTS.md`) already ran
an extensive study on M15 momentum scalps and found only one small,
cost-fragile improvement (pullback entry) that fails the formal ship gate
(deflated Sharpe ≈ 0, dies at 2x cost, sign-unstable across quarters). Two
structural reasons that study struggled to find a *robust* edge:

1. **High frequency = high cost drag.** M15 scalps hold for ~8 bars; the
   round-trip cost (spread + slippage) is a large fraction of the typical
   move, so any real signal has to be large to survive 2x cost-stress.
2. **Short history = weak statistics.** The MT5 feed only had ~2024-2026 of
   M15 bars for the diverse basket, so "quarter sign-stability" was checked
   over a handful of quarters — not enough to separate luck from skill.

TradingView's free (no-login) historical feed caps any request at 5000 bars
**regardless of timeframe**, which means switching to **Daily** bars buys
~19 years of real history (2006/2007–2026) across FX, metals, energy, and
global indices, and 6-9 years for crypto. Lower frequency also amortizes
transaction costs over much bigger moves. Both factors point the same way:
**search for a swing/trend edge on Daily (and a higher-frequency H4 cross-
check), not another M15 scalp variant.**

## 2. Data plan

- Source: TradingView's public websocket feed via the unofficial `tvdatafeed`
  client (`pip install git+https://github.com/rongardF/tvdatafeed.git`), used
  **without** a TradingView account ("nologin" mode — explicitly supported,
  rate-limited to public/delayed-ish data but real OHLCV).
- Basket: 33 instruments, same diversity philosophy as the original 29-symbol
  Deriv basket — FX majors (7) + crosses (4), metals (4), energy (3), crypto
  (6), global indices (6) + US indices (3). See `backtest/fetch_tradingview.py`.
- Timeframes: **Daily** (primary research TF, ~19y/~5000 bars for most
  instruments) and **H4** (secondary, ~3y/5000 bars, faster-frequency
  cross-check that the same logic isn't a Daily-only artifact).
- Stored at `backtest/data/tv_D1/*.csv` and `backtest/data/tv_H4/*.csv`
  (gitignored, regenerate with `python fetch_tradingview.py`).

## 3. Candidate strategy families (planned before testing)

Each family is a genuinely different trading mechanism from the M15 scalper,
chosen because it has *some* independent prior (academic or classic
systematic-trading literature) rather than being curve-fit to this dataset.
A **negative control** (random entry) is included to verify the statistical
pipeline doesn't rubber-stamp noise — same role the tick-volume control
played in `experiment.py`.

| # | Family | Mechanism | Prior |
|---|---|---|---|
| F1 | Donchian channel breakout + ATR trail | Long on N-bar high breakout, short on N-bar low breakout, chandelier ATR trailing stop, no fixed TP ("let winners run") | Classic time-series-momentum / "Turtle" trend-following; Moskowitz–Ooi–Pedersen (2012) found this robust across decades and asset classes |
| F2 | EMA trend filter + RSI pullback entry | Trade only with EMA(fast)/EMA(slow) trend; enter on a shallow RSI dip-and-recover within the trend (buy the dip in an uptrend) | Trend + pullback is the daily-bar analogue of the EA's own validated M15 insight (entering at better prices than at-extension) |
| F3 | Volatility-squeeze breakout | Bollinger-band-width percentile compresses (squeeze) then price breaks the band — momentum ignition out of low volatility | Classic vol-contraction/expansion pattern (Bollinger; "squeeze" setups) |
| F4 | RSI(2) mean reversion | Buy extreme oversold RSI(2), exit at RSI recovery to mid — counter-trend, fixed small target | Connors-style short-term mean reversion; documented edge on US equity indices, tested here for breadth across asset classes |
| F5 (control) | Random entry | Same exit/risk machinery, uniformly random entries at the same approximate trade frequency as F1 | Negative control — must fail the ship gate, or the pipeline is broken |

## 4. Statistical gate (reuse, don't dilute)

Every candidate is judged the same way `experiment.py` judges confluence
filters:

- 70/30 in-sample/out-of-sample split per symbol; **only OOS numbers count**.
- Cost sweep: 0, 0.02, 0.04 ATR/side (0.02 ≈ "realistic", 0.04 ≈ "2x stress").
- Walk-forward efficiency (OOS expectancy / IS expectancy).
- Correlation-breadth haircut (effective independent symbols via eigenvalue
  participation ratio, not raw symbol count).
- Permutation test against a random-subset/random-entry null.
- Deflated Sharpe Ratio (Bailey & López de Prado) across **all** cells tried
  in the whole search — this number gets stricter the more candidates we try,
  by design, to punish exactly the kind of search this plan runs.
- Per-quarter sign stability (needs ≥60% of calendar quarters positive OOS).
- A minimum-detectable-effect power floor.

**Ship gate = ALL of:** positive OOS marginal edge, passes its
permutation/geometry check, WFE ≥ 0.3, DSR ≥ 0.95, enough effective trades to
clear the power floor, survives 2x cost stress, and ≥60% of quarters
positive. Anything short of that is reported as "watch" or "no-ship" — same
honesty bar as `RESULTS.md`.

## 5. Execution loop

1. Implement F1–F5 in a shared, parametrized swing-backtest engine
   (`backtest/swing_backtest.py`), reusing the existing R-multiple /
   ATR-cost conventions so results are directly comparable to the M15 study.
2. Run the full gate (`backtest/swing_experiment.py`) on Daily data across the
   33-instrument basket; inspect by asset class (the M15 study found the edge
   lives in crypto+indices and dies in FX — check whether that pattern
   repeats or is M15-specific).
3. For every family that shows *any* positive OOS signal, sweep 2-4 parameter
   variants (the "try new ideas" loop) before giving up on it — e.g. Donchian
   N ∈ {20, 55}, EMA pairs, squeeze threshold — exactly mirroring how the
   pullback-offset sweep (#1 off0.3 vs off0.6) worked in `experiment.py`.
4. Cross-check any surviving candidate on H4 (different frequency, shorter
   but independent history) and on the asset-class breakdown, to rule out a
   single-regime or single-instrument artifact.
5. Stop when either (a) a candidate clears the full ship gate, or (b) the
   planned family list + their parameter variants are exhausted. Report
   honestly either way in `backtest/SWING_RESULTS.md`, update the top-level
   README, and — only if something genuinely ships — produce a TradingView
   Pine Script strategy so it can be run/alerted directly inside TradingView.

This plan deliberately does **not** promise a positive result. Per the
existing repo's own track record (0/19 confluence filters shipped; only one
geometry change partially worked), the honest prior is that most of F1-F4
will fail the gate too. The value of the loop is in trying genuinely
different, literature-grounded mechanisms and reporting the truth, not in
forcing a "yes."
