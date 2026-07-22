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
