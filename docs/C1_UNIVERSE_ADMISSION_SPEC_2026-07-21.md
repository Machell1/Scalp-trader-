# C1 universe admission, M15-execution grain — pre-registration (2026-07-21)

**Owner directive:** "go ahead on #1" — complete the universe-admission study
that PR #53 stopped, under the CURRENT deployed book (v1.33-C1r3, momentum
2.0), with the parity blocker fixed. Candidates: **FRA40.cash, AUS200.cash**
at a universal 0.050% sleeve risk.

**Priors disclosed:** the 2026-07-13 H1-grain admission REJECTED both
candidates at Stage B (added trades worsened paired outcomes / hard halts).
The genuinely new element retained from the A1-era design is the
**M15-execution grain** (finer fill/mark realism on the H1-scale signal).
The A1-era attempt never reached candidate discovery — it stopped at its own
E1/E2 structural-parity gate on the CONTROL.

**Blocker root cause + fix (registered here):** in the M15-grain execution
model, SHORT time-exits added the spread into the exit PRICE
(`exit_price += _spread(...)`). Because spread scales with the E1/E2 cost
multiplier, the E1 and E2 tapes differed STRUCTURALLY — the parity gate
correctly fired. It was also an economics bug: the full round-trip cost is
already charged at entry (−2.0 × cost), so shorts were double-charged on time
exits. Fix: the exit price stays structural (bid close); no spread added.
This makes E1/E2 differ only in registered cost fields, as the gate demands,
and removes the short-side overcharge.

**Protocol (inherited from the A1-era registration, adapted):** control =
C1 book (momentum 2.0) built by the same M15-grain machinery; discovery /
validation split, matched C1-opportunity placebos, DSR at the incremented
ledger, and the 9-gate Stage-B admission standard verbatim (97.5% paired
lower > 0; McNemar ≤ 0.025; Wilson lower ≥ 0.88; hard ≤ 0.3700%; paired
hard upper ≤ 0.05%; timeout & median days no worse; zero firm breach; ≥97%
lifecycle retention overall with ≥95% per symbol and strictly more fills;
min-lot substitutions ≤ control). E1/E2 structural parity must PASS on the
fixed builder before any outcome is computed. Stop rule: any regression or
parity failure halts the study with the failure recorded — no in-flight
repairs.

**Ledger: 315 → 317** (two candidate cells). Admission of a passer is an
input-only whitelist/cluster/risk-map change to the live EA — deployed only
on a separate owner promotion instruction with the full config echo.

*Results appended below the hash after runs.*

---
## PRE-OUTCOME AMENDMENT (2026-07-21, before any result computed)
1. **Code base:** the harness ports from branch revision 3ac108a ("correct M15
   placement and structural gates"), which contains the structural-parity gate
   and actual-next-open placement — not the earlier b288a06 revision.
2. **Placebo design (C1-era):** the A1-era placebo (C1-opportunity pool of the
   candidate) degenerates when the study threshold IS C1. Registered
   replacement: the placebo pool = the BASE-UNIVERSE (US30/US100/JP225/USDJPY)
   C1 trades, matched by side x quarter to the candidate symbol's observed
   trades — the candidate must beat already-admitted flow at the 97.5th
   percentile, same statistic machinery otherwise.
3. **Ledger constants:** start floor 315, maximum end 317, DSR trials 317
   (supersedes the inherited A1-era 300/305/305).
4. **Execution regime:** the study runs from a dedicated LF worktree
   (core.autocrlf=false) so byte-equality provenance constants are blob-exact.

---
## RESULTS (appended post-run 2026-07-22)

**The integrity gates passed for the first time in this study's two-era
history**: M15_CONTROL_DETERMINISM PASS (e1 4f4bcb7a / e2 a67f4c71, 708
control fills); E1/E2 structural parity green on the fixed builder. The
two-era blocker decomposed into (1) a real short-TIME-exit double-charge and
(2) float-ULP noise (3e-16) in non-entry gross-R components, now compared at
1e-9. Both fixes committed with the evidence trail.

| candidate | disc n | valid n | valid E2 | DSR@317 | placebo p | verdict |
|---|---|---|---|---|---|---|
| FRA40.cash | 172 | 82 | +0.0148 | 0.0028 | 0.729 | **FAIL** (discovery exp non-positive E1+E2; placebo not beaten) |
| AUS200.cash | 154 | 63 | -0.1896 | 0.0000 | 0.990 | **FAIL** (negative everywhere) |

**FINAL: NO_SYMBOL_SURVIVED_DISCOVERY.** The M15-execution grain does NOT
rescue either candidate - consistent with, and now stronger than, the
2026-07-13 H1-grain rejection. Neither symbol's flow beats matched draws from
the already-admitted book (placebo p 0.73 / 0.99). Ledger 315 -> 317 as
registered. Path #1 (more trades from the validated edge via FRA40/AUS200)
is CLOSED with a clean negative; the complementary-flow question moves to
the ranked alternatives (per-book-gates kernel project; new H1-native family
discovery).
