# Volatility-regime sync (sizing vs confluence) — pre-registration (2026-07-11, night)

**User directive:** "the EA sync itself to the volatility as confidence or confluence,
whichever works." Both mechanizations tested; the challenge MC decides "which works."

**Empirical basis (why this regime variable earned a cell):** SUPERVISOR_SPEC T4
(exploratory, report-only) found W2 expectancy monotone in ATR-percentile terciles:
low +0.056 / mid +0.109 / high +0.124R — reserved there as a future pre-registered
cell. Distinct from the failed sizing ideas: entropy = uninformed variation (variance
drag); allocators = conditioning on outcome noise; this conditions on a measured,
causal regime state correlated with edge. Also stated: the engine's GEOMETRY is
already vol-synced (ATR-scaled stops/targets/offsets, fixed $ risk) — only regime-
conditioned risk amount and regime admission are untested.

**Regime variable (causal):** per symbol, ATR(14) percentile rank over the trailing
2000 bars at the SIGNAL bar (min 200 bars warmup). Terciles at fixed cuts 1/3, 2/3.

**Arms (3 cells; ledger 129→132):**
- **V1a sizing, conservative:** risk mult {low: 0.50, mid: 0.75, high: 1.00} × 0.3%.
- **V1b sizing, balanced:** mult {0.60, 0.90, 1.20} × 0.3% (≈ preserves average risk
  at trade-time tercile occupancy).
- **V2 confluence:** drop low-tercile signals entirely (trade mid+high at flat 0.3%).

**Gates (ALL required for the winning arm to ship):**
1. **OOS monotonicity check first (kill-point):** on stitched OOS quarters of the trio
   tape, tercile expectancy ordering low<mid<high must hold directionally (Spearman of
   tercile rank vs mean R positive in ≥60% of OOS quarters). T4 was full-tape
   exploratory; if the pattern is an in-sample artifact, all arms die here.
2. Challenge MC (no-time-limit both-phases, 0.3% base, 8k sims): arm > flat baseline
   AND bust ≤ baseline.
3. **Placebo control:** 20 random-relabeling draws (tercile labels shuffled within
   symbol, preserving marginal frequencies → identical multiplier/drop distribution):
   arm must beat the placebo 95th percentile on both-phases. (This is the control that
   separates "regime information" from the mechanical effect of the multiplier mix —
   the corrected-control lesson from the WFO study.)
4. Per-symbol: no symbol's OOS contribution flips sign under the arm.
**Ship rule:** winning arm = input-only change is NOT possible (regime multiplier needs
EA code) → v1.30 flag-gated module, panel-shadow first, owner sign-off. No winner →
documented null; the monotonicity finding remains observational.

**Prior stated:** baseline 88.4% both-phases is a high ceiling; sizing down positive-EV
low-vol trades trades total R for variance — net effect genuinely uncertain. The honest
outcome may be "the EA is already optimally vol-synced through its geometry."
