# Inverse candle-anatomy filter — full-gate pre-registration (2026-07-10, evening)

**Hypothesis under test** (arising from the morning study, which PASSED the information
gate with inverted sign): momentum-pullback signals whose SIGNAL BAR is *contested*
(large adverse-side wick / non-climactic body) out-earn *clean climax* signal bars;
therefore dropping clean-climax signals (equivalently: favoring wicky ones) improves
the strategy. Contamination disclosure: the sign was discovered on the 70/30 bar-split
OOS of the same 12 symbols. This gate therefore uses (a) a DIFFERENT evaluation frame —
the house calendar-quarter stitched walk-forward at REAL per-instrument spread cost
(`walkforward_dsr.py` machinery), (b) placebo and stability controls, and (c) a
direction-only corroboration on NEVER-USED data (FTMO US30.cash/US100.cash M15).

**Engine/config.** `scalper_confluence.simulate_symbol_c`, pure-bracket deployed config
(limit 0.6 ATR, expiry 3, SL 1.0, TP 3.0, hold 8, lock/trail OFF=99, block_overlap),
Wilder ATR, per-instrument real cost = 0.5·median(spread)/median(ATR) from the spread
CSVs. Features exactly as `candle_anatomy_study.candle_features` (imported, not re-coded).

**Pre-registered cells (6; locked before any result of THIS study is computed):**
- W1 keep only `adv_wick_atr` ≥ 0.20 · W2 ≥ 0.30 · W3 ≥ 0.50
- K1 drop `body_frac` ≥ 0.80 · K2 drop ≥ 0.70
- K3 drop clean-climax combo (`adv_wick_atr` < 0.20 AND `body_frac` ≥ 0.70)

**Per-cell PASS requires ALL of** (stitched OOS quarters, real cost):
1. filtered OOS expectancy > baseline OOS expectancy (same trade tape, paired frame)
2. filtered OOS expectancy > 95th pct of a 200-draw RANDOM-DROP placebo (same drop count)
3. ≥60% of OOS quarters: filtered quarter-mean ≥ baseline quarter-mean
4. ≥8/12 symbols with OOS (filtered − baseline) ≥ 0
5. DSR ≥ 0.95 via `psr(filtered_oos, dsr_hurdle(n_trials=94, n_obs=n))` — 94 = 68 prior
   + 8 VPOF + 6 candle-protective + 6 these cells + 6 morning-study S2 cells
6. 2× cost: filtered OOS exp > 0 AND > baseline 2×-cost OOS exp
7. filtered OOS n ≥ 250 (powered)

**Corroboration (reported, not gating):** FTMO-terminal US30.cash + US100.cash M15
(~9 months, never used in any candle analysis): wicky (adv_wick_atr ≥ 0.30) vs clean
expectancy split at FTMO's own measured cost — direction agreement is supportive
evidence; disagreement is a red flag noted in the verdict.

**Ship rule.** ≥1 cell passes all 7 → propose v1.29 `InpCandleFilter` (default OFF,
panel-shadow first, user sign-off required). Otherwise: documented null, program over,
EA untouched. Sizing variants (upsize wicky) are explicitly OUT of scope here.
