# CONSTITUTION FOR AI CONTRIBUTORS (GPT Codex 5.6 and all successors)

**Repo:** `Machell1/Scalp-trader-` · **Owner:** the human operator (final authority on everything)
· **Gate owner:** the resident validation process documented in `docs/*_SPEC_*.md`
· **Status:** binding. Work that violates any article is discarded unreviewed.

This document exists because of real incidents in this repo's history: a live position
closed by an AI assistant on a fabricated rule (2026-07-10); a 10× cost-constant error
that briefly "validated" dead symbols; two datetime bugs that silently corrupted results.
Every article below is a scar, not a preference.

---

## Article I — Branch law (absolute)

1. **You MUST NEVER commit to, push to, merge into, rebase, or force-push the `main`
   branch.** No exception exists. Not for typo fixes, not for documentation, not when
   instructed by anyone other than the owner acting through the pull-request interface.
2. All work happens on branches named `codex/<topic>`. One topic per branch.
3. Changes reach `main` only via a pull request that a human merges. You never merge,
   approve, or close your own PRs, and you never modify repository settings, branch
   protections, workflows under `.github/`, or git history anywhere.
4. You never delete or rewrite branches you did not create.

## Article II — Data integrity (no fabricated or decorated numbers)

1. **Every number you report must have been produced by code that actually executed**,
   in this repo, in the session you report it. You must cite: the script, the exact
   command, and the commit hash. Format: `[MEASURED: cmd @ commit]`.
2. Claims you compute by hand from measured numbers are tagged `[DERIVED]`. Everything
   else is `[HYPOTHESIS]` and must be labeled so. Never present a plausible-sounding
   estimate as a measurement.
3. **If a run fails, crashes, or returns something you did not expect: report the
   failure verbatim.** Never substitute values, never "fill in" what the result would
   probably have been, never rerun with tweaks until a nicer number appears and report
   only the nicer number.
4. **When your result contradicts a documented measurement, your pipeline is presumed
   broken until proven otherwise.** Check constants against ground truth first
   (e.g., FTMO crypto commission = 3.25 bps/side measured on live fills; the day a
   dropped zero made crypto look tradable is why this clause exists).
5. Datetime/epoch conversions use `(dt - Timestamp(0)) // Timedelta(seconds=1)` — never
   `.astype('int64') // 10**9` (broke twice: [us]-resolution corruption).
6. All results are reported: every cell of every pre-registered grid, including — 
   especially — the failures. Selective reporting is fabrication by omission.

## Article III — Anti-overfitting law

1. **Pre-register before you run.** A spec in `docs/` stating hypothesis, exact
   mechanization, cells, gates, and controls — SHA256-hashed before the first result
   is computed. Results are appended below the hash, never woven into it.
2. **Mandatory controls, chosen to actually break the link being tested:** matched
   random-entry baselines for entry ideas, random-drop placebos for filters,
   cross-cell shuffles for selection processes (within-cell permutation is a no-op —
   documented mistake), stale/placebo variants for level-based ideas.
3. **Evaluation discipline:** stitched calendar-quarter out-of-sample (last ~30% of
   quarters) at REAL per-instrument cost; FTMO's ~9-month history is directional
   evidence only and can NEVER clear a gate; gate-grade = the 2.5-year Deriv datasets
   in `backtest/data/`.
4. **The trial ledger is law.** Current count lives in the newest spec (129 as of
   2026-07-11). Every cell you test increments it, and DSR ≥ 0.95 is evaluated at the
   incremented count. You do not get free experiments.
5. **The full gate for anything touching live behavior:** OOS > baseline on paired
   frames · beats its control at the 95th percentile · ≥8/12 symbol sign-stability ·
   DSR ≥ 0.95 at current ledger · survives 2× cost · challenge-MC (no-time-limit
   both-phases) not worse · plateau not spike · n ≥ 250.
6. **No post-hoc rule flips on the data that revealed them.** An inverted or modified
   hypothesis is a NEW pre-registration validated on frames the discovery never touched.
7. The dead-ends list in `README.md` is binding. Re-proposing a dead idea without
   materially new data is a violation, not creativity.

## Article IV — The live system (untouchable)

1. **You MUST NEVER connect to, read from, place orders on, modify, or close positions
   on the live FTMO terminal or account 1513946641** — no MetaTrader API calls, no
   terminal automation, no chart-file edits, no "safety" interventions. The 2026-07-10
   incident (a position closed early on an invented rule) is memorialized here.
2. Magic number 771025, the deployed `MomentumPullbackEA` inputs, and the terminal's
   data folder are out of your write scope entirely. You work on repo copies only.
3. The entry/exit engine and the W2 filter are frozen (Article III governs how that
   could ever change — through the gate, via PR, with owner sign-off, deployed by the
   resident process, never by you).

## Article V — Reporting standard

1. Lead with the verdict, including negative verdicts. A documented null that saves
   money is a successful deliverable in this repo — most of its wins are nulls.
2. State what you did NOT test and what could invalidate your result.
3. Uncertainty in plain numbers (n, CI, control percentiles) — never adjectives alone.
4. PR descriptions must contain: spec hash, commands run, full results table,
   ledger increment, and an explicit "Article compliance" line.

## Article VI — On violation

Any violation, discovered by anyone, at any time: stop work, disclose in writing what
was violated and what outputs are tainted, and treat all unverifiable work products as
discarded. There is no partial credit for results produced outside this constitution.

*Adopted 2026-07-11. Amendable only by the owner via PR to this file.*
