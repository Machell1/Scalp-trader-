# Candle-Anatomy Filter Study — pre-registration (2026-07-10, post-v1.28)

**Origin.** Fishbone/5-whys of the 2026-07-10 losses: the US30 loss entered a sell-limit
into a V-reversal whose M1 anatomy was a sweep-and-rip; the open mechanism question was
whether SIGNAL-BAR candle anatomy (wick/tail structure) distinguishes terminal flushes
from genuine continuations. User directive: "candle stick pattern and wick tail
calculation must be calculated and considered as addition to the EA."

**Prior (stated before results).** Entry filters on this EA are 0-for-N (AVWAP, ADX,
trend-EMA, volume, checklist scoring — all no OOS edge); the wick-based liquidation-sweep
entry died 2026-07-09 (fill-realism artifact). This study exists because the mechanism is
the fishbone's only untested lever and the test is cheap — not because the prior is good.
An EA change ships ONLY on a full gate pass. No result ⇒ no EA change, panel unchanged.

**Data/engine.** Cached 12-symbol spread-gated real Deriv M15 (`backtest/data/derivM15_spreadgated/`),
audited `scalper_backtest.simulate_symbol` with the deployed v1.27 params (Wilder ATR —
now exactly the live estimator), cost 0.03/side. Engine extended with an additive
`signals_out` kwarg returning (signal_bar i, entry_bar, r) per filled trade; join on
integer bar indexes (NO datetime conversions — VPOF lesson).

**Features (signal bar i, all info available at bar close; side-adjusted).**
For side s (+1 buy continuation, −1 sell continuation), with range = h−l:
1. `adv_wick_atr` — adverse-side wick / ATR: s>0 → (h−max(o,c)); s<0 → (min(o,c)−l). The
   "rejection tail" against the continuation thesis.
2. `adv_wick_frac` — same wick / range.
3. `clv_dir` — side-adjusted close location: s>0 → (c−l)/range; s<0 → (h−c)/range.
   High = closed hard in the move's direction.
4. `body_frac` — |c−o| / range.
5. `range_atr` — range / ATR (climax bar size).
6. `tail3_atr` — sum of adverse-side wicks over signal bar + 2 prior, / ATR (flush cluster).

**S1 information gate (kill point).** Per-feature Spearman IC vs per-trade R, computed on
the OOS window only (last 30%, matching every prior study), pooled + per symbol.
Control: 200 within-symbol permutations of the feature column → null IC envelope.
PASS requires ≥1 feature with pooled OOS |IC| > 97.5th pct of its null AND the same sign
in ≥8/12 symbols. Fail ⇒ program ends, verdict logged, nothing touches the EA.

**S2 filter arms (only if S1 passes; pre-registered grid, 6 cells).** Drop the signal when:
A1 `adv_wick_atr` > 0.30 · A2 > 0.50 · B1 `clv_dir` < 0.30 · B2 < 0.20 ·
C1 `tail3_atr` > 0.75 · C2 > 1.20.
Gate per cell: OOS expectancy ≥ baseline on PAIRED per-signal comparison; must beat a
RANDOM-DROP placebo (same drop fraction, 200 draws, ≥95th pct); no sign-flip across
symbols/stitched quarters; DSR ≥ 0.95 at cumulative trial count (68 prior + 8 VPOF + 6).
2× cost stress. Both-sides and per-side reported (3 recent losses were sells = n=3
observation, NOT a hypothesis; per-side asymmetry is reported, never cherry-picked).

**Ship rule.** Pass ⇒ v1.29 adds the ONE winning rule behind `InpCandleFilter` (default
false), shadow-logged on the panel first. Anything else ⇒ documented null, program over.
