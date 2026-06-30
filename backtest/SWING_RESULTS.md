# Swing-strategy edge search — results (TradingView Daily/H4)

Companion to `EDGE_SEARCH_PLAN.md` (read that first for the *why* and the
plan written before any of this was run) and `RESULTS.md` (the original M15
scalper study). Data: `backtest/fetch_tradingview.py`, real OHLCV pulled live
from TradingView's public feed — 33 instruments, Daily back to 2006-2007
(~19y) for FX/metals/energy/indices and 2017-2020 (~6-9y) for crypto; H4 back
to 2022-2024 (~3y) as an independent frequency cross-check. Engine and gate:
`backtest/swing_backtest.py` / `backtest/swing_experiment.py`.

**Headline: 0 of 22 candidates shipped, on either timeframe.** One lead
(`F4`, RSI(2) mean-reversion-within-trend) is flagged **observe-grade** —
the same non-claim the original M15 pullback entry got — because it is the
*only* family that ever beat the correct null. Everything else, including
some big-looking raw numbers, did not.

## 1. The key methodological finding: trend-following "edges" here are mostly long bias, not entry skill

The standard test for an entry rule is "is its expectancy > 0 / better than a
random subset of an already-good baseline" (that's what `experiment.py` did
for the M15 filters). For genuinely new entry *mechanisms* that claim is too
weak, because the exit machinery itself (ATR stop + chandelier trail, i.e.
cut losers fast / let winners run) is **convex** — it can show positive
expectancy even when entries are timed by a coin flip, as long as the
underlying assets have positive long-run drift. Over 2006/2007-2026 this
diverse basket *did* have strong long-run drift (post-GFC recovery, the
2020-2026 crypto and equity bull runs, multi-decade index uptrends).

So every candidate here is judged against a **matched null**: literally
random entry timing, run through the *identical* stop/trail/cost machinery,
same long/short mix, same approximate trade frequency. Result:

| Family | OOS exp (cost .02) | vs. matched-null mean | Verdict |
|---|---|---|---|
| F1 Donchian breakout (long-only, best variant) | +0.111 R | **null was +0.134 R — entries are worse than random** | NO-SHIP — pure long-bias, no timing skill |
| F2 EMA-trend + RSI-pullback (long-only, best variant) | +0.081 R | null +0.099 R — also worse than random | NO-SHIP — same pattern |
| F3 Volatility-squeeze breakout (long-only, best variant) | +0.039 R | null +0.138 R — much worse than random | NO-SHIP |
| **F4 RSI(2) mean-reversion-in-trend (both sides)** | **+0.063 to +0.071 R** | **null −0.037 to −0.057 R — beats random** | watch (best lead, still NO-SHIP on the formal gate) |
| F5 random control | −0.005 R | (is the null) | NO-SHIP (correctly rejected — sanity check passes) |

This is the single most useful result of the whole search: **"buy the
breakout / buy the dip" trend-following narratives that *sound* like skill
were, on this real diverse basket, statistically indistinguishable from (or
worse than) just holding a random long position with a good exit.** Anyone
backtesting a trend system on a 19-year, equity/crypto-heavy basket without a
matched-null check would have shipped F1 — it has a 15/25 positive-quarter
record and survives 2x cost stress (+0.091 R) and *looks* like a real edge
on every naive metric. The permutation-vs-matched-null test is what catches
it (p=0.475 — not remotely significant; the deflated Sharpe is 0.06).

## 2. The one lead that survives the matched-null test: F4 (RSI(2) mean-reversion-in-trend)

Mechanism: only take RSI(2) extreme reversals (≤5 / ≥95) **in the direction
back toward** the prevailing SMA(200) trend (buy oversold dips in an uptrend,
sell overbought rallies in a downtrend) — i.e. the daily-bar analogue of the
EA's own validated M15 insight (enter at a better price than the extension,
not at it).

On the full 33-instrument Daily OOS sample (2018-2026 average per symbol):

| Variant | OOS exp @.02 | @0 (no cost) | @.04 (2x stress) | perm_p vs null | Qpos | DSR |
|---|---|---|---|---|---|---|
| stop 2.0 ATR | +0.071 R | +0.091 R | +0.051 R | 0.125 | 18/25 | 0.08 |
| stop 2.5 ATR | +0.063 R | +0.079 R | +0.047 R | 0.150 | 18/25 | 0.16 |
| stop 3.0 ATR | +0.054 R | +0.068 R | +0.041 R | 0.175 | 18/25 | 0.20 |
| idx+energy universe, stop 2.0 | +0.116 R | +0.136 R | +0.096 R | 0.225 | 18/25 | **0.74** |

Asset-class breakdown (stop 2.5, OOS, cost .02) — unlike the M15 study, **no
class is negative**: CRYPTO +0.030 R, METAL +0.030 R, FX +0.044 R, ENERGY
+0.123 R, INDEX +0.093 R. Restricting to the strongest classes
(index+energy) raises the deflated Sharpe the most (0.74, the highest of any
cell tried) but the permutation p-value actually *worsens* (0.225) because
the narrower 12-symbol universe has far higher null variance — a smaller
basket makes the test noisier, not more convincing.

**Why this is "watch", not "ship":** every cell's permutation p stays above
the 0.05 bar (best: 0.125, both-sided stop-2.0 cell) and every cell's
Deflated Sharpe stays below the 0.95 bar (best: 0.82, the idx+energy
stop-2.5 cell — but that cell's own permutation p is worse at 0.225, because
DSR and the permutation test are sensitive to different things: DSR cares
about the Sharpe relative to the search-wide null, permutation cares about
this cell's distance from its own matched-exit null). No single cell clears
both simultaneously. It survives 2x cost stress and has a genuinely
broad-based, non-FX-excluded asset profile, which is *more* encouraging than
the M15 pullback entry's profile — but it has not been shown to beat chance
at the rigor this repo's own gate demands.

**It also does not replicate on H4** (the independent-frequency check the
plan called for): on ~3 years of H4 bars the same parameters are flat-to-
negative (exp ≈ −0.004 to +0.022 R, perm_p 0.275-0.625). This is most likely
because RSI(2) thresholds calibrated for daily mean reversion don't transfer
to a 4-hour bar's noise profile without re-tuning — but re-tuning H4
separately would be a *second* search on the same H4 data, which is exactly
the kind of multiple-comparisons risk this gate exists to catch. We did not
do that. The honest read: **the Daily-only result has not been confirmed
independently** and should be weighted accordingly.

## 3. Full search ledger (22 cells, both timeframes)

Every cell actually run, in the order tried (see `swing_experiment.py`
`CANDIDATES` for exact parameters) — reproduce with:

```bash
cd backtest
pip install -r requirements.txt
pip install --no-cache-dir "git+https://github.com/rongardF/tvdatafeed.git"
python fetch_tradingview.py        # pulls real data straight from TradingView, no account needed
python swing_experiment.py D1      # Daily — primary research timeframe
python swing_experiment.py H4      # H4 — independent frequency cross-check
```

- **F1 Donchian breakout + ATR chandelier trail** (4 variants: N20/N55,
  Turtle-exit, long-only): all NO-SHIP. Long-only is the strongest *raw*
  number in the whole study (+0.111 R) and the worst by deflated Sharpe
  (0.06) — textbook long-bias mirage.
- **F2 EMA-trend + RSI-pullback entry** (5 variants): all NO-SHIP. Same
  long-bias pattern as F1 once long-only-filtered.
- **F3 volatility-squeeze breakout** (3 variants): all NO-SHIP, including
  two genuinely negative cells even before isolating long-only.
- **F4 RSI(2) mean-reversion-in-trend** (8 variants across stop distance,
  trend-filter length, RSI threshold, long-only, universe restriction): the
  only family with any cell beating its matched null; best is "watch" tier
  as above; the long-only-filtered cut is *worse* than both-sided, implying
  the short side is where the genuine value (if any) actually lives.
- **F5 random control** (1 cell): correctly NO-SHIP, DSR 0.00 — confirms the
  pipeline isn't rubber-stamping noise.

DSR hurdle rose from 0.118 (13 cells, round 1) to 0.187 (22 cells, round 3)
as the search grew — by design, more trials searched ⇒ a higher bar to ship,
which is exactly why nothing late in the search "snuck through."

## 4. Bottom line

No candidate in this search — five distinct, literature-grounded strategy
families, parameter swept, asset-class restricted, and cross-checked on a
second timeframe — clears this repo's ship gate. That is the honest answer
to "is there a real edge here," consistent with the original M15 study's own
finding (0/19 confluence filters shipped). The one candidate worth
continuing to monitor, **not trading on**, is F4 (RSI(2) mean-reversion
within a SMA(200) trend, Daily bars, both sides, stop 2.0-2.5 ATR): it is the
only mechanism in the whole search that beats a fair random-timing null, it
survives 2x cost stress, and it has no excluded asset class — but its
deflated Sharpe (≤0.82) and permutation p-value (≥0.125) both fall short of
the bar, and it failed to replicate on H4. A reference Pine Script for
*monitoring this on TradingView's own charts* (no claim of edge — same
"OBSERVE" framing as the live EA) is in `pinescript/RSI2TrendWatch.pine`.
