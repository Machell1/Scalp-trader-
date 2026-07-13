# Session-conditioning + VWAP overlay + ORB-retest screen — pre-registration (2026-07-13)

**Source:** owner's second research paste (intraday 5m/15m pullback tailoring;
external AI deep-research; its results table is SELF-DECLARED illustrative
simulation and carries zero evidential weight here). Extracted testable levers
never measured on the corrected engine: (1) session-window conditioning of the
live v1.30 config, (2) session-VWAP-hold overlay, (3) ORB breakout-retest
entry family. M5 prescriptions out of scope (no canonical M5 data — stated).

**Engine/standard:** corrected live-parity enumeration (parity_engine
primitives, window=4), v1.30 geometry (bank 50% @ +1R, TP 2.0) as the base,
real per-symbol cost, touch fills for comparative deltas (absolute levels carry
the ~−0.03 fill-realism haircut per RETEST addendum). Trio primary; 10-symbol
holdout for any arm with trio OOS ≥ +0.03 delta. SCREEN under RETEST_SPEC
governance; ledger +4 screen cells noted (→ ~217).

**Cells:**
- **S-A calibration (no cell):** per-symbol cash-open time-of-day bin :=
  argmax of median true range across the 96 M15 bins (self-calibrating; no
  timezone assumptions). Sanity-print the implied local open times.
- **S-B bucket census (no cell — measurement):** v1.30-geometry trades split
  by signal-bar bucket: OPENING (open bin .. +5 bins = 90 min), CASH-REST
  (+6 .. +25), OFF-SESSION (all else). Per-bucket n/exp/OOS.
- **S-C1 cash-only filter:** entries allowed only in bins open..+25.
- **S-C2 opening-window filter:** entries only in bins open..+5.
- **S-C3 VWAP-hold overlay:** longs only when signal close > session VWAP
  (daily-anchored, equal-weight fallback where no volume column — stated);
  shorts mirrored. Full-day entries.
- **S-D ORB-retest family:** OR = first cash bar's H/L; skip if OR range >
  2.5×ATR14; breakout = close beyond OR within 8 bars; retest = within 6 bars
  of breakout, price touches the boundary and closes back in breakout
  direction; enter next bar open; stop = retest extreme ∓ 0.5×ATR; manage
  bank50@1R/TP2R; one trade per symbol-day; causal one-position enumeration.

**Filters are TRUE re-enumerations** (occupancy shifts), not post-hoc subsets;
S-B is the post-hoc census for attribution only. Decision rule: an arm is
alive if trio OOS improves ≥ +0.03 vs unfiltered v1.30 base AND holdout does
not contradict (sign-consistent); anything alive queues for gate + forward.
Prior: session effects are the best-evidenced claim in the paste (open/close
volume-volatility concentration is real in cash equities) but Deriv CFD hours
and M15 granularity may dilute it; ORB-retest priors mixed. Results below.

---
## RESULTS (appended post-run 2026-07-13; protocol hashed pre-run: c2154d5d...)

- **S-A calibration sane:** US30/US100 cash-open = 13:30 server (09:30 ET);
  JP225 = 00:00 server (Tokyo). Self-calibration works.
- **Base reproduces exactly** (n=3757, +0.0609, MC 93.6%/2.9% touch-fill).

| arm | n | exp | OOS exp | vs base OOS (+0.0635) | verdict |
|---|---|---|---|---|---|
| S-C1 cash-session only | 1688 | +0.0747 | +0.0286 | **−0.035** | NULL |
| S-C2 opening 90min only | 959 | +0.0728 | +0.0006 | **−0.063** | NULL |
| S-C3 VWAP-hold overlay | 3520 | +0.0552 | +0.0697 | +0.006 (<+0.03) | NULL (noise) |
| S-D ORB-retest | 531 | −0.0217 | −0.0925 | — | NULL |

**All four arms fail the pre-registered bar. Notable inversion of the paste's
thesis:** in the OOS window the v1.30 edge is carried substantially by
off/late-session trades (S-B census: JP225 cash-rest −0.08 vs off +0.05; both
session filters DEGRADE OOS while flattering the full sample). Session
restriction removes trades without improving quality on this venue/timeframe.
The bucket census is retained as monitoring texture, not a lever. Ledger +4
screens (→ ~217). No arm queues for gate.
