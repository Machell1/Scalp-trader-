# v1.30 coupled FTMO risk-policy study — pre-registration

**Status:** protocol only; no outcome, expectancy, win-rate, or pass-probability
cell has been run. Metadata-only inventory was permitted before registration.

**Branch:** `codex/v130-risk-policy`
**Base:** `5914de6325c40302d2b44c5c9b7c1f24f4b4b5c3`
**Live baseline:** MomentumPullbackEA v1.30, magic 771025, deployed and initialized
2026-07-11 23:06:25 terminal-local time.

## 1. Question and decision

Can a fixed, phase-specific risk schedule raise the standard FTMO 2-Step
Challenge probability above 88% without changing v1.30's symbols, signals,
entry logic, pending behavior, exit geometry, transaction-cost model, or trade
frequency?

The current 66.129425% number is a diagnostic comparator, not the control for
this study. Its per-symbol tapes are uncoupled, whole-trade R is assigned to the
signal day, only active UTC days are sampled IID, balance risk is treated as a
fixed percentage of initial capital, Phase 1 and Phase 2 are simulated
independently, and the nominal no-time-limit run stops after 365 sampled active
days. This study first replaces that model with a coupled event/account control.

**Null:** no pre-registered policy clears the full >88% gate after exact-live
coupling, observed-spread execution, EA/FTMO rails, cost stress, and blind FTMO
confirmation.

**Mechanism:** for positive expectancy, account drift scales approximately with
risk fraction `f`, while variance scales approximately with `f²`. Lower fixed
risk should improve upper-before-lower barrier odds at the cost of more time.
Phase 2 has half the target but the same maximum-loss boundary, so halving its
risk preserves target distance in nominal R while increasing its loss buffer.
This changes account-level path geometry only; it cannot improve trade win rate
or per-trade R expectancy.

## 2. Frozen strategy and execution invariants

Every policy uses the same:

- whitelist and scan order: US30.cash, US100.cash, JP225.cash;
- clusters: US30+US100 share one seat; JP225 has its own seat;
- maximum one position/pending per symbol, one per cluster, two globally;
- M15, Wilder ATR(14), six-bar momentum at 2.0 ATR, continuation direction;
- W2 adverse wick pre-entry threshold `>= 0.30 ATR`;
- pullback limit at signal close minus/plus `0.60 ATR`;
- live four-bar pending occupancy, with management/free events before scans;
- stop at 1.0 frozen signal ATR, 50% partial at +1.0R, remainder TP at 2.0
  frozen signal ATR, and eight-bar hold;
- stop-first same-bar pessimism, then partial, then target;
- eight fills/day and four-consecutive-loss day stop;
- entry, partial, final-exit, cooldown, and occupancy semantics of v1.30;
- transaction cost charged once on original size.

No entry gate, symbol, target, stop, partial fraction, hold, scan order, pending
window, cost, or fill rule may be changed after hashing. A risk policy may alter
only the percentage of current balance put at risk per new position by FTMO
phase.

## 3. Data and sealing

### 3.1 Development-only data — contaminated

- all 46 SHA256-pinned canonical Deriv CSVs;
- the newest 30,000 FTMO M15 bars per trio symbol, already requested by tracked
  parity/retest code;
- the former ten-symbol retest holdout, which has already been consumed.

These frames may be used for implementation debugging, fidelity controls, and
the development screen. They cannot confer final confirmation status.

### 3.2 Outcome-blind FTMO history discovered by lineage audit

Tracked repository FTMO studies requested at most the newest 30,000 bars. A
metadata-only terminal query found 69,999 older bars per symbol. No price outcome
or strategy statistic from these bars was inspected before this protocol.

| symbol | sealed final holdout: 39,999 bars | locked confirmation: 30,000 bars | already mined: 30,000 bars |
|---|---|---|---|
| US30.cash | 2022-04-13 23:15–2023-12-22 09:15 UTC | 2023-12-22 09:30–2025-04-02 20:45 UTC | 2025-04-02 21:00–2026-07-10 23:45 UTC |
| US100.cash | 2022-04-14 01:30–2023-12-22 10:30 UTC | 2023-12-22 10:45–2025-04-02 22:00 UTC | 2025-04-02 22:15–2026-07-10 23:45 UTC |
| JP225.cash | 2022-04-13 16:00–2023-12-22 15:30 UTC | 2023-12-22 15:45–2025-04-02 23:00 UTC | 2025-04-02 23:15–2026-07-10 23:45 UTC |

Before any cell, one exporter must freeze all 99,999 bars/symbol in a new
gitignored folder using stable UTF-8/LF CSV plus the raw NumPy structured array.
It must record retrieval UTC, server (not credentials), terminal/API versions,
symbol point/tick/contract/volume properties, exact split boundaries, row counts,
strict epoch uniqueness/order, OHLC invariants, nonnegative spread, and a gap
report. No gaps may be filled. A SHA256 manifest outside the ignored folder is
committed. All outcome code must load only the frozen files.

The confirmation frame is opened once, and only if the primary passes every
development gate. The sealed final holdout is opened once, and only if the
unchanged primary passes confirmation. Any policy/threshold/gate change after a
frame is opened consumes that frame; it cannot be called holdout again.

Repository history cannot exclude untracked/manual research. Historical
gate-grade status therefore remains conditional on owner attestation that the
older dates were not used outside tracked repo lineage.

### 3.3 Prospective forward frame

Forward begins at the final v1.30 init boundary: 2026-07-11 23:06:25
terminal-local / 2026-07-12 07:06:29 server decision-log time. Pre-v1.30 trade
CSV rows are excluded in full. Forward telemetry must preserve decisions,
orders, fills, partial slippage, final exits, and terminal journal evidence.
Historical confirmation cannot validate actual partial fills, slippage,
restart recovery, or terminal operation; prospective forward remains the final
live-execution gate.

## 4. Coupled execution engine

`parity_engine.run_live` will receive default-off execution/lifecycle hooks and
an optional event sink. With hooks absent, all 46 golden-regression files and
existing parity outputs must remain byte/trade identical.

The v1.30 hook must emit deterministic signal rejection, pending placement,
pending cancellation, entry fill, partial fill, and final-exit events. Each row
contains trade id, symbol, epoch/bar, side, modeled price, R/cashflow component,
state before/after, and global/cluster occupancy. A partial does not free a seat,
increment fills/day, stamp cooldown, or update the loss streak. Final aggregate
R alone updates the streak.

Execution columns:

- `D0_TOUCH`: old bid-bar touch, diagnostic only;
- `F1_PER_BAR`: primary observed-spread rule. Long buy limits require
  `bid_low + observed_spread <= limit`; short sell limits use bid touch. Short
  partial/TP buy limits require `bid_low + observed_spread <= level`;
- `F2_STRICT_ASK`: mandatory sensitivity adding ask-side short protective-stop
  triggering; no column may rescue a failure in `F1_PER_BAR`;
- `F2_STRICT_ASK_2X`: mandatory double-cost stress, with all touch semantics
  identical to F2.

The registered signal-ATR-scaled median-spread model is reported as a comparator,
not an eligibility column. Five-second heartbeat miss/slippage cannot be inferred
from M15 and remains a forward-test item.

## 5. Fidelity gates before policy cells

No policy cell may run until all pass:

1. `python backtest/verify_data.py` reports exactly `verified 46 OK, 0 missing,
   0 mismatched`.
2. Default-off parity regression is trade-for-trade identical on all 46 files.
3. Uncoupled v1.30 touch hook equals `retest_engine.run_cell` per symbol in trade
   id, bars, and R to `1e-12`.
4. Uncoupled asymmetric hook equals `v130_crosscheck` per symbol in trade id,
   bars, and R to `1e-12`.
5. Synthetic cases cover four-bar fill/cancel, expiry-before-scan, W2 equality,
   cluster/global seats, day caps, partial seat retention, final-only streak,
   same-bar stop-first, partial-then-TP, partial-then-stop, short ask fills, and
   time exit.
6. Every coupled event replay satisfies symbol <=1, cluster <=1, global <=2,
   one partial maximum, fill-window provenance, and exact R-component sums.
7. Two identical runs produce identical normalized event/trade bytes and SHA256.

Any fidelity difference stops the study and is reported without policy results.

## 6. FTMO account-path simulator

Product is standard FTMO Challenge 2-Step: Phase 1 target +10%, Phase 2 target
+5%, 5% maximum daily loss, 10% static maximum loss, and minimum four trading
days per phase. There is no commercial time limit; the numerical simulation
ceiling is 3,650 calendar days/phase and every unresolved path counts as failure.
A 7,300-day extension is diagnostic only and cannot rescue eligibility.

The simulator must:

- use current-balance risk at entry and FTMO symbol volume min/step/max and
  tick-value/tick-size metadata;
- use Europe/Prague FTMO day boundaries and retain zero-trade calendar days;
- apply entry cost, partial cashflow, final cashflow, and open-position equity;
- apply the EA's 4% daily halt, 8% peak-equity hard halt, 9% static hard halt,
  eight-fill cap, and four-loss day stop;
- count any permanent EA hard halt before target as failure/unresolved, not
  survival;
- run Phase 1 then Phase 2 on one common block-bootstrap stream, resetting the
  account/ledger at transition but not selecting a friendlier regime;
- use common random numbers across policies;
- use 20-calendar-day moving blocks as primary and IID calendar days only as a
  sensitivity;
- use 100,000 deterministic paths for final estimates (seed 13020260711), with
  one-sided 95% Wilson bounds, paired policy-control deltas, median and P90
  calendar days, rule-breach, hard-halt, and timeout rates;
- report leave-one-calendar-quarter-out and per-symbol attribution;
- report a conservative two-stop open-equity envelope and 2x-stop gap envelope
  if exact tick-level floating equity is unavailable.

## 7. Pre-registered policies and ledger

| id | Phase 1 risk/current balance | Phase 2 risk/current balance | role |
|---|---:|---:|---|
| D0 | legacy 0.30% | legacy 0.30% | reproduce old simplified comparators; fidelity control, no charge |
| C0 | 0.30% | 0.30% | exact coupled/account control; no hypothesis charge |
| R1 | 0.20% | 0.20% | flat-risk attribution control; +1 |
| **R2** | **0.20%** | **0.10%** | **sole promotion candidate**; both targets are 50 nominal R; +1 |
| R3 | 0.25% | 0.125% | faster 40R sensitivity; cannot be promoted if R2 fails; +1 |

No drawdown throttle, hot-hand sizing, volatility sizing, random sizing, or
target-chasing band is permitted in this study.

Current retrospective ledger hurdle is approximately 209. Maximum charge is
`209 -> 214`: R1/R2/R3 development cells (+3), unchanged R2 locked confirmation
(+1), and unchanged R2 final sealed holdout (+1). Controls do not test an edge
hypothesis. Only cells actually run are charged; every run is still reported.

## 8. Gates and sequencing

R2 advances from development only if all are true:

1. Coupled F1 and F2 expectancy is positive, remains positive at F2 2x cost,
   last-four-quarter pooled expectancy is positive, and no symbol's contribution
   is negative enough to make the pooled result dependent on one symbol.
2. The one-sided 95% lower bound for both-phase pass probability is strictly
   greater than 88% under F1, F2, F2 2x cost, moving-block bootstrap, and the
   conservative open-equity envelope.
3. The paired one-sided 95% lower bound for `R2 - C0` pass probability is >0.
4. R2's rule-breach upper bound is no worse than C0; timeout <=1%; P90 completion
   <=1,825 calendar days.
5. Pre-account-state trade ids, entry/exit prices, R outcomes, expectancy, and
   win rate are identical across C0/R1/R2/R3. Risk sizing may not manufacture
   trade edge or frequency.

If R2 fails, R3 is reported as sensitivity only; neither confirmation nor
holdout is opened and no policy ships. If R2 passes, only C0 and unchanged R2
are run on locked confirmation. Confirmation requires the same >88% lower-bound,
positive-delta, cost, breach, timeout, time, symbol, and block gates. Only then
is sealed holdout opened once, with the identical test and no edits.

Historical passage is labeled `HISTORICALLY GATE-ELIGIBLE`, not live-validated.
EA risk inputs are not changed until historical passage, owner attestation, a
reviewed PR, and a clean flat-account deployment check. Prospective promotion
requires at least 250 post-v1.30 completed trades spanning two calendar quarters,
at least 50 trades/symbol, unchanged telemetry, and the same pre-registered
lower-bound >88% calculation. Until then, the objective remains unproven.

## 9. Kill and reporting rules

- Coupled C0 or R2 expectancy <=0 under F1/F2, or <=0 at 2x cost: kill.
- Any mandatory >88% lower-bound failure: kill; point estimates do not override.
- Any fill/coupling/regression mismatch: stop before results.
- Any post-hoc risk, threshold, block length, time ceiling, symbol, fill, or gate
  change consumes the opened frame and requires a new registration.
- Every control, policy, fill column, quarter, symbol, failure, hard halt, breach,
  timeout, and failed command is reported.
- No claim that sizing increases trade win rate; it cannot.

## 10. Deliverables

- frozen-data exporter, split metadata, integrity report, and SHA256 manifest;
- default-off coupled v1.30 event hooks with full legacy regression;
- deterministic FTMO account-path simulator and tests;
- results appended below this protocol hash, with all numbers tagged by command
  and commit;
- branch PR to main; no live input change from research alone.

---
**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `8f2043af550df082e493a3d295f305d014c4083115b96bfbdfe61855f860e30a`

---
## RESULTS

Not run at registration. Results may be appended here only; the protocol above
the recorded hash is immutable.

### Locked implementation conventions (before any policy cell)

The following deterministic conventions resolve implementation details that the
hashed protocol did not numerically define. They were recorded before opening
any development policy outcome, confirmation, or holdout cell.

- FTMO daily floor is Prague-midnight balance minus 5% of phase initial
  balance. Equality is conservatively classified as a breach.
- A phase passes only while flat, with closed balance at/above target and at
  least four distinct Prague entry days. Phase 2 starts on the next Prague
  calendar day and continues the same bootstrap stream without a redraw.
- Registered original-volume transaction cost is debited at entry. Partial and
  final rows contain gross price cashflows and must reconcile to theoretical R.
- The paired R2-minus-C0 gate uses the unconditional matched-path delta
  `p(R2-only pass) - p(C0-only pass)`. Its one-sided 95% lower bound is the
  Bonferroni difference between a 97.5% one-sided exact Clopper-Pearson lower
  bound for the R2-only multinomial cell and the corresponding exact upper
  bound for the C0-only cell.
- Primary moving blocks are 20 complete Prague calendar days and may start only
  where both midnight boundaries are flat across working pendings and open
  positions. Orphans, overlaps, or ambiguous stitched ordering are fatal
  fidelity errors.
- Median and P90 completion days use successful both-phase paths; failures,
  hard halts, breaches, and timeouts are reported separately.
- The symbol-dependence gate requires nonnegative expectancy for every symbol
  and positive pooled expectancy after deleting each symbol.
- "Last four quarters" means the last four complete calendar quarters. Fewer
  than four complete quarters is a failure.
- The conservative two-stop open-equity envelope is eligibility-binding. The
  2x-stop gap envelope is reported as the mandatory diagnostic stress.
- FTMO limits and minimum days reset at Europe/Prague midnight. The deployed EA
  uses broker `TimeCurrent()` and therefore resets its fills, streak, and 4%
  day halt on Europe/Helsinki broker days (one hour earlier); both clocks are
  modeled independently.
- Favorable and adverse bar marks are replayed while positions are open. The EA
  peak is updated from favorable marked equity before the binding stop envelope
  is applied to floor/drawdown tests.
- A policy-neutral tape is eligibility-valid only if every path reports zero
  policy-dependent skipped entries and zero theoretical-versus-rounded outcome
  sign mismatches. Any nonzero divergence kills the study rather than assuming
  missed opportunities.
- The policy-independent tape retains the theoretical 50% partial. Account
  replay applies actual lot-step partial rounding; when a partial is invalid,
  the full rounded position remains for the final price cashflow.

No policy result had been run when these conventions were appended.
