# Performance-supervisory layer above W2 — pre-registration (2026-07-11)

**User directive:** build a performance governor (symbol allocation, drawdown throttling,
execution vetoes, regime compatibility) leaving the W2 entry engine unchanged.
**House position:** sizing-layer changes move live money → MC-test the exact proposed
functions on historical W2 tapes BEFORE any EA change; ship only what improves the
challenge math. Ledger 125 → 129 (4 cells).

**Already live (no test needed):** hard halts (daily −4% + pending cancel, trailing 8%,
static 91% floor, all restart-proof), per-trade execution evidence CSV (slippage, MFE/MAE,
spread@entry), panel + decision log, risk-ledger reconstruction.

**T1 — graded drawdown throttle (2 cells).** The proposal's exact function
(mult = 1 / 0.75 / 0.5 / 0.25 / 0 at DD ≥ 0/2/3/4/5%), applied causally inside the
challenge replay, two anchorings: (a) DAILY (running day P&L; existing −4% halt retained),
(b) TOTAL (drawdown from running equity peak). Metric: no-time-limit both-phases
probability + bust + median days vs the flat-0.5% baseline, 10k sims, same trio tape.

**T2 — symbol performance allocator (2 cells).** The proposal's exact multiplier
(<30 trades → 1.0; exp ≤ 0 → 0.5; < 0.05 → 0.75; < 0.10 → 1.0; else 1.25) computed
CAUSALLY per trade from that symbol's trailing 30 W2 trades; variant (b) with Bayesian
shrinkage toward the pooled prior (+0.1117, effective n=50) as proposed. Each trade's
R is scaled by its multiplier, then the standard day-block MC. Same metrics.
Prior disclosed: performance-chasing hollowed expectancy in every prior study; the
bounded sizing form is untested — that is what this measures.

**T3 — execution-quality veto (design only, no cell).** PAUSED when rolling-10 stop
slippage ≥ 1.5× the forward-test baseline. CANNOT be backtested (no historical slippage
series); the live forward test is currently collecting the baseline distribution.
Ship path: log + display now, arm the veto once ≥30 live stops define the baseline.

**T4 — regime compatibility (exploratory, report-only).** W2 OOS expectancy bucketed by
ATR-percentile terciles, session, and range/ATR terciles on the trio tape. No gate; any
apparent regime dependence becomes a future pre-registered cell, not a live rule.

**Ship rule.** T1/T2 cells that IMPROVE both-phases without raising bust → v1.30
supervisory module (flag-gated, defaults matching the tested winner, panel-integrated,
user sign-off). Cells that fail → documented; EA unchanged. The entry engine is frozen
regardless (the proposal's own "major danger" clause, adopted verbatim).

---
## RESULTS (appended post-run 2026-07-11; protocol above hashed pre-run)

Trio W2 tape: 3,021 trades / 674 days / mean +0.1010R. Baseline flat 0.5%:
both-phases 75.6%, bust 14.9%, median 25 days (10k sims).

- **T1a daily-anchored throttle: 74.7%, bust 15.4% → FAIL** (worse both ways; the
  existing −3%/−4% daily halts already cover the tail; graded intraday cuts only
  slow same-day recovery).
- **T1b total-DD throttle: bust 0.0% but both-phases 26.0% (P1 41.5%) → FAIL.**
  Textbook illustration: throttling from 2% drawdown makes the account nearly
  unkillable and nearly unable to pass — survival ≠ passing. Bust is already
  capped at 14.9% by the shipped hard halts.
- **T2a raw rolling-30 allocator: 72.0%, bust 17.4% → FAIL.** Mult distribution:
  1,090 trades cut to 0.5× after cold streaks, 1,425 upsized to 1.25× after hot
  streaks — per-symbol 30-trade performance is NOISE; the downweighted trades
  mean-revert. Performance-chasing hurts in sizing form too (now 0-for-5 lifetime).
- **T2b Bayesian-shrunk allocator: 70.8%, bust 18.4% → FAIL** (shrinkage toward the
  +0.1117 prior pushes half the tape to 1.25× = leverage without signal).
- **T4 regime buckets (report-only):** expectancy monotone in volatility (low 0.056 /
  mid 0.109 / high 0.124) and session (LDN-NY 0.122 vs off 0.055). ALL buckets
  positive → exclusion rules would discard positive-EV trades; no cell proposed.

**VERDICT: no sizing adaptation ships. Flat 0.5% + the existing hard halts beat every
proposed variant. Adopted from the proposal: the slippage-veto DESIGN (T3, armed only
after ≥30 live stops define the baseline) and per-symbol rolling metrics as panel
observability at the next natural recompile. Entry engine frozen, per the proposal's
own overfitting clause.**
