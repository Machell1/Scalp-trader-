# A1 marginal-signal reduced-risk sleeve — pre-registration (2026-07-20)

**Owner directive:** improve v1.36-A1 to take more trades while improving win
rate and increasing win size. **Honest scope statement:** the three asks trade
off; this study targets the one open, evidence-backed lever. Dead axes NOT
re-run: exit/win-size variants (IMPROVE-100 X-family + 3 prior eras, 0
admissions), full-weight marginal re-admission (Kimi cells, placebo-failed),
confirmation filters (4× "more confirmation selects worse trades").

**Hypothesis [pre-registered]:** the 2.0–3.0 ATR "marginal" impulse trades that
A1 discards carry positive-but-not-superior expectancy (Kimi-era control data:
OOS ≈ +0.17R). Re-admitting them AT REDUCED RISK (sleeve) adds trade count and
completion speed to the A1 book without materially raising halt risk or
surrendering A1's pass odds — the USDJPY-sleeve template (+8.21pp, the
program's only lifetime sizing admission) applied to a signal-quality tier
instead of a symbol.

**Mechanization:** the C1 tape (momentum_atr_mult=2.0, the audited joint
enumeration whose seat/occupancy semantics are exactly what a tiered-risk live
EA would produce) with per-trade tiering: impulse ≥ 3.0 → base risk (0.30%
trio / 0.05% USDJPY); impulse ∈ [2.0, 3.0) → sleeve risk s ∈ {0.05%, 0.10%,
0.15%} (3 cells). Implementation: relabel marginal trade_ids' symbol to
"SYM#M" in the C1 event tape (cluster unchanged — seat semantics preserved);
extend risk_fraction_by_symbol with #M keys. Impulse per trade recomputed from
the signal bar embedded in trade_id, using the audited prep pipeline.

**Evaluation (era standard):** paired MC vs the A1 control on common bootstrap
paths — seed 13020260711, 20-day blocks, 20k screen → 100k confirmation on
survivors; gates verbatim from the A1 head-to-head standard: hard-halt ≤
0.003700; conservative one-sided paired lower bound (candidate − A1 both-phase
pass) > 0; plus this study's speed claim: candidate timeout ≤ A1 AND successful
median days < A1. Stage-0 stratum census (marginal n, exp, OOS, per-symbol,
win-size profile) reported first regardless. Ledger: 300 → 303 (3 cells).
Passing ≠ deployment: owner promotion + EA change (per-trade risk tiering =
v1.37 proposal) + forward validation remain separate.

*Results appended below the hash after runs.*

---
## RESULTS (appended post-run 2026-07-20; protocol hashed pre-run: 8f454013...)

**Stage-0 census (tape-exact: C1 counts 450/282/437/515 and A1 2,819 events
reproduce the pinned head-to-head):** A+ stratum n=287 exp +0.1259 (E2) win
61.7% OOS +0.0567; MARGINAL n=700 exp +0.0312 win 57.9% **OOS +0.1474 — the
discarded stratum outperforms A+ out-of-sample.** Impulse bands NON-monotone:
(2.25,2.5] best (+0.1028, 61.1%); (2.5,3.0) worst (−0.02..−0.06) — the 3.0
boundary is not a quality gradient; part of A1's in-sample margin is band
structure.

**Stage-1 20k paired screen (control A1 reproduces pinned numbers: both
90.965% / hard 0.040% / timeout 8.995% / 979d):**
| sleeve | both | timeout | medDays | paired lower | gates | verdict |
|---|---|---|---|---|---|---|
| 0.05% | 90.520% | 9.480% | 948 | −0.0122 | paired N, timeout N | **no** |
| 0.10% | 88.450% | 11.550% | 796 | −0.0332 | paired N, timeout N | **no** |
| 0.15% | 87.470% | 12.520% | 682 | −0.0431 | paired N, timeout N | **no** |

**VERDICT: NO ADMISSION (0/3). Ledger 300 → 303.** The sleeve buys speed
monotonically (979→682 median days) but pays pass odds at every size, and
raises timeouts (the marginals' variance pushes borderline paths past the
horizon). **Decisive dominance finding: every sleeve mix is strictly dominated
by uniform C1 itself (88.902% / 499d beats 88.45%/796d and 87.47%/682d on both
axes).** Combined with Kimi's full-weight re-admission failures and
IMPROVE-100's 0/100: the tiered middle ground between C1 and A1 does not
exist. The efficient frontier is exactly two points — **A1 (slow, 91.0%) and
C1 (fast, 88.9%, 2.5× the trades)** — and choosing between them is an owner
decision about time-vs-odds, not a research question. Win-size and win-rate
axes remain closed (exit book, 4× confirmation-filter finding).
