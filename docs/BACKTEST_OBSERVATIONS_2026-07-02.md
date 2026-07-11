# Backtest results & observations — 2026-07-02 (Fable 5 gate on the Cursor helper studies)

**Command structure recap:** Fable 5 (external, Opus-directed session) owns the validation gate.
The Cursor cloud agents (Fable 5 helper on Task A; Composer 2.5 + GPT-5.5 on the parallel branches +
Task B) delivered candidate **study scripts**; none touched the EA. This document is Fable 5's gated
verdict after running every study on **real Deriv M15 data** and adversarially verifying the one survivor.

**Bottom line: nothing ships to the live EA. v1.23 is unchanged and remains correct.**

---

## 1. Safety gates (ran first, both PASS)

The Task A harness additions (`scalper_confluence.py`: `scaleout_r/frac/be`, `pyr_add_r/frac`,
`tp_rv_split/lo/hi`) are additive and default OFF.

- **`baseline_repro_test.py` — BYTE-EXACT.** All-OFF `simulate_symbol_c` reproduces the reference
  `scalper_backtest.simulate_symbol` for chase-ladder / v1.2 ladder / v1.23 pure-bracket at cost 0.0 & 0.02,
  on real data: **maxdiff 0.00e+00** (34,394 baseline trades on the bracket config).
- **`harness_invariants_test.py` — ALL PASS.** Feature-neutral settings reproduce baseline exactly;
  active features never change the entry set (paired test stays valid); downside bounds hold.

So every number below comes from a harness whose OFF-path *is* the live engine.

## 2. Study verdicts — 5 of 6 REJECT, 1 WATCH

12 spread-gated majors, real per-instrument Deriv cost, stitched quarterly OOS. Baseline v1.23 pure
bracket OOS: N=11272, exp **+0.0778R**, avgWin 1.72R, ≥2R 16.6%.

| Study | Cells SHIP (raw gate) | Fable 5 verdict | Reason |
|---|---|---|---|
| `pyramid_add` | 0/3 | **REJECT** | BE-move truncation kills more tail than the add captures (paired t −3.6…−4.0) |
| `asymmetric_tp` | 0/3 | **REJECT** | falsification control (crypto TP3/index TP4) improves *equally* → generic TP noise, not a crypto tail |
| `stop_buffer` | 0/3 | **REJECT** | wider stops monotonically hurt (dExp −0.006 → −0.023) |
| `bracket_tp` | 0/3 | **REJECT** | TP-widening is a coin flip (paired t ≈ 0) |
| `adaptive_tp` | 0/4 | **REJECT** | conditioning beats flat-TP4 control by +0.0005 (noise); flat TP4 itself is noise |
| `partial_scaleout` | 2/4 | **WATCH** | passed the *raw* gate but fails correlation-robust significance (see §3) |

## 3. The one survivor — partial scale-out 50%/33% @+1.5R — WATCH, do not ship

Raw study result: scale 50%@+1.5R dExp +0.0093, pooled pair_t **+2.89**, WFE 1.74, exp2x +0.0434,
Sym+ 12/12, DSR 1.00 → the raw gate said SHIP. A 7-agent adversarial workflow disqualified it:

- **Independent from-scratch re-implementation** (a fresh simulator forbidden from reading the scale-out
  branch) reproduced dExp +0.0093 and matched the harness on **105,190 per-trade comparisons at
  maxdiff 0.00e+00**, no look-ahead. **The math is clean — this is not a code bug.**
- **It fails every honest significance test.** N_eff=2.64 (mean pairwise r=0.53), so the pooled t=+2.89
  haircuts to **+1.36 (p=0.18)**. Day-clustered block-bootstrap 95% CI on the mean delta =
  **[−0.00002, +0.0198] — includes zero.** 10/12 symbols positive but **zero individually significant**.
- **It shrinks wins** (avgWin 1.72R→1.26R, ≥2R 16.6%→14.7%) — opposite of the "larger wins" objective.

WATCH (not REJECT) only because the harness math is provably clean; revisit *only* with a fuller
`scaleout_r` grid (1.0/1.25/1.75 showing a smooth response), several individually-significant uncorrelated
symbols, and a regime-diverse multi-fold OOS where the scale-out **delta** (not the quarter's raw mean R)
stays positive under a cluster-robust test. None hold today.

## 4. METHODOLOGY BUG found in the SHIP gate (fix before the next study round)

The study gate at `partial_scaleout_study.py:149` (and the sibling studies) tests the **raw pooled paired
t** (`pair_t > 1.96`) on ~17k **correlated** per-signal deltas — treating 17k trades as 17k independent
bets. The studies even *print* the N_eff haircut (×0.47) in their own header but never apply it to the gate.
That is exactly how a correlation-inflated false positive (scale-out) reached a SHIP verdict.

**Fix shipped in this repo:** `experiment.cluster_robust_paired(deltas, times, n_eff, n_sym)` returns the
N_eff-haircut t **and** a day-clustered block-bootstrap 95% CI. **Future study gates must replace the raw
`pair_t > 1.96` test with `cluster_robust_paired(...)["excludes_zero"]`** (day-clustered CI excludes 0) as
the decision-grade significance gate. Reference driver: `cluster_robust_gatecheck.py`.

## 5. Re-check under the corrected standard — what actually holds

`cluster_robust_gatecheck.py` on real data (N_eff=2.64):

```
A) LIVE v1.23 pure bracket  vs  v1.2 ladder     dExp +0.0227  raw t +3.19  haircut t +1.50  CI [-0.0004,+0.0456]  includes 0
B) scale-out 50%@+1.5R      vs  v1.23 bracket    dExp +0.0101  raw t +2.89  haircut t +1.36  CI [-0.00002,+0.0198] includes 0
C) LIVE v1.23 EXPECTANCY    vs  0 (does it earn?) exp +0.0778  raw t +5.58  haircut t +2.62  CI [+0.0357,+0.1189]  EXCLUDES 0
```

**The decisive split:**
- **(C) The strategy's expectancy is REAL and correlation-robust** — the pullback-entry + momentum-
  continuation + bracket system earns money OOS net of real cost; the day-clustered CI excludes zero.
  **The live EA is sound.**
- **(A, B) The choice *between exit variants* is below this dataset's resolution.** Ladder-vs-bracket and
  scale-out are statistically indistinguishable at ±0.02R with only ~2.6 effective independent bets over
  a single ~9-month OOS window.

**Consequences:**
- Live EA: **untouched.** v1.23 keeps its validated real edge.
- Pure-bracket over the old ladder: keep it, justified on **parsimony** (simpler, fewer params, bigger
  point-estimate wins, better 2×-cost robustness) — *not* as a statistically-proven improvement of the
  difference. (Prior "+54% improvement" framing was overstated; the improvement is real as a point
  estimate but not cluster-robust significant.)
- The real bottleneck is **data**: resolving marginal exit edges needs more instruments / longer history
  (more effective bets). This is the plan's "hard data limit" made concrete.

## 6. Task B tooling (Composer/GPT branches) — reviewed, low-risk

`weekly_backlog_report.py`, `hold16_promotion_check.py` (correctly never auto-promotes — "Fable 5 still
owns the gate"), and the `atr_parity.py` JSON output are clean and non-strategy. Mergeable when convenient;
`atr_parity` needs the live MT5 terminal to run. No live impact.

## 7. What the Cursor helpers should do next (if anything)

1. **Adopt the corrected gate** (`cluster_robust_paired`) in every study before proposing new candidates —
   the raw-pooled-t gate is retired.
2. **Do not re-propose** any of the six rejected ideas, nor the dead-ends already logged in RESULTS §7.
3. The productive frontier is **more effective bets**, not more exit tweaks: pull a larger, less-correlated
   Deriv M15 universe (FX + metals + more crypto/indices) via `fetch_spreadgated.py` so the next round can
   actually *resolve* a ±0.01R effect instead of leaving it inside the noise floor.
