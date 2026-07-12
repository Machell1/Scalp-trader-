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

### Development edge-gate result

The registered development edge command was run once against the newest
30,000-bar frozen slice for each of the three FTMO symbols:

```text
verified FTMO blind freeze 9 OK, 0 missing, 0 mismatched, 0 extra
verified FTMO blind freeze 9 OK, 0 missing, 0 mismatched, 0 extra
EXECUTION mode=D0_TOUCH n=1544 exp=+0.0580007762 win=0.4158031088 event_sha256=aa7064cc2509cf1c7cdb158dae57feedc2e584098c72b5bf01b2b9a3bbda4a13
EXECUTION mode=F1_PER_BAR n=1504 exp=+0.0175799036 win=0.4029255319 event_sha256=6f0025dffec7011edf9a3a2701df7775a26b34b51cbae9d6efc3c557c24bd849
EXECUTION mode=F2_STRICT_ASK n=1497 exp=+0.0025410956 win=0.3961255845 event_sha256=6cd7b86866592927bd22475465feff138324c2487d8219a6a022e73b08b111a0
EXECUTION mode=F2_STRICT_ASK_2X n=1497 exp=-0.0445521560 win=0.3941215765 event_sha256=c34e15c96c7c2413dae8c77809c6f7bdbcc14b43b1007487e52f81e526d6d79e
RESULT_FILE=C:\Users\Sanique Richards\Downloads\codex-scalp\backtest\v130_mined_edge_results.json
VERDICT=KILLED_AT_EDGE_GATE
```

[MEASURED: `python backtest/run_v130_risk_study.py --development-edge` @
`18b04c7a8613fcfdee952d2ceb7cddbed54eccd4`]

The mandatory F2 strict-ask 2x-cost pooled expectancy was
`-0.0445521560R`; its last-four-complete-quarter expectancy was
`-0.0461761448R`; and JP225.cash, US100.cash, and US30.cash were each
negative. The registered edge gate therefore killed the risk-policy study
before C0/R1/R2/R3 Monte Carlo. Paths run: 0 of 100,000. Ledger: 209 -> 209;
charge 0. This runner did not access confirmation or holdout. [MEASURED:
development edge command @
`18b04c7a8613fcfdee952d2ceb7cddbed54eccd4`]

The exhaustive symbol, quarter, deletion, coupling-census, fidelity, failure,
and terminal-write tables are recorded in
`docs/V130_RISK_POLICY_RESULTS_2026-07-12.md`; the machine-readable artifact is
`backtest/v130_mined_edge_results.json`. The one-line disposition is:

**V1.30 RISK-SIZING IDEA DISPOSED -- EDGE LOST UNDER MANDATORY F2 2X COST;
>88% FTMO CHALLENGE PASS EXPECTANCY NOT DEMONSTRATED.**

#### Exhaustive development measurements

Unless a narrower tag is shown, every value in the following tables is
[MEASURED: `python backtest/run_v130_risk_study.py --development-edge` @
`18b04c7a8613fcfdee952d2ceb7cddbed54eccd4`].

| column | trades | expectancy R | win rate | last-4-complete-quarter R | events | cross-EA-midnight trades |
|---|---:|---:|---:|---:|---:|---:|
| D0_TOUCH | 1,544 | +0.0580007762 | 41.58031088% | +0.0628647986 | 25,366 | 40 |
| F1_PER_BAR | 1,504 | +0.0175799036 | 40.29255319% | +0.0189162026 | 24,895 | 38 |
| F2_STRICT_ASK | 1,497 | +0.0025410956 | 39.61255845% | +0.0009467120 | 24,565 | 38 |
| F2_STRICT_ASK_2X | 1,497 | -0.0445521560 | 39.41215765% | -0.0461761448 | 24,565 | 38 |

| column | symbol | n | expectancy R | win rate |
|---|---|---:|---:|---:|
| D0 | JP225.cash | 596 | +0.0804086257 | 43.95973154% |
| D0 | US100.cash | 380 | +0.0993865499 | 42.63157895% |
| D0 | US30.cash | 568 | +0.0068006488 | 38.38028169% |
| F1 | JP225.cash | 582 | +0.0417086051 | 42.61168385% |
| F1 | US100.cash | 366 | +0.0309624880 | 40.16393443% |
| F1 | US30.cash | 556 | -0.0164865175 | 37.94964029% |
| F2 | JP225.cash | 581 | +0.0268069303 | 41.99655766% |
| F2 | US100.cash | 363 | +0.0165379678 | 39.11845730% |
| F2 | US30.cash | 553 | -0.0321412093 | 37.43218807% |
| F2-2x | JP225.cash | 581 | -0.0229801996 | 41.82444062% |
| F2-2x | US100.cash | 363 | -0.0280165664 | 38.84297521% |
| F2-2x | US30.cash | 553 | -0.0780706474 | 37.25135624% |

| column | quarter | n | expectancy R | win rate |
|---|---|---:|---:|---:|
| D0 | 2025Q2 | 288 | +0.0260030736 | 40.27777778% |
| D0 | 2025Q3 | 309 | +0.0862631612 | 44.01294498% |
| D0 | 2025Q4 | 308 | +0.0513681685 | 40.25974026% |
| D0 | 2026Q1 | 299 | +0.0700242245 | 41.80602007% |
| D0 | 2026Q2 | 301 | +0.0434966910 | 40.86378738% |
| D0 | 2026Q3 partial | 39 | +0.1425090613 | 46.15384615% |
| F1 | 2025Q2 | 279 | -0.0001923641 | 39.42652330% |
| F1 | 2025Q3 | 299 | +0.0374882553 | 42.47491639% |
| F1 | 2025Q4 | 303 | +0.0194357638 | 38.94389439% |
| F1 | 2026Q1 | 294 | +0.0201065800 | 41.15646259% |
| F1 | 2026Q2 | 290 | -0.0019818724 | 38.96551724% |
| F1 | 2026Q3 partial | 39 | +0.1040827768 | 43.58974359% |
| F2 | 2025Q2 | 277 | -0.0049576717 | 38.98916968% |
| F2 | 2025Q3 | 299 | +0.0311990467 | 42.14046823% |
| F2 | 2025Q4 | 297 | -0.0012402830 | 38.04713805% |
| F2 | 2026Q1 | 297 | +0.0059325695 | 40.74074074% |
| F2 | 2026Q2 | 288 | -0.0333474210 | 37.50000000% |
| F2 | 2026Q3 partial | 39 | +0.1040827768 | 43.58974359% |
| F2-2x | 2025Q2 | 277 | -0.0519680385 | 38.98916968% |
| F2-2x | 2025Q3 | 299 | -0.0159208513 | 42.14046823% |
| F2-2x | 2025Q4 | 297 | -0.0484173219 | 37.37373737% |
| F2-2x | 2026Q1 | 297 | -0.0412537280 | 40.74074074% |
| F2-2x | 2026Q2 | 288 | -0.0803520508 | 37.15277778% |
| F2-2x | 2026Q3 partial | 39 | +0.0572973355 | 43.58974359% |

The registered last four complete quarters were 2025Q3, 2025Q4, 2026Q1,
and 2026Q2. [MEASURED: development-edge command @
`18b04c7a8613fcfdee952d2ceb7cddbed54eccd4`]

| column | deleted symbol | pooled expectancy R |
|---|---|---:|
| D0 | JP225.cash | +0.0439131408 |
| D0 | US100.cash | +0.0444899566 |
| D0 | US30.cash | +0.0877975716 |
| F1 | JP225.cash | +0.0023489879 |
| F1 | US100.cash | +0.0132758387 |
| F1 | US30.cash | +0.0375597877 |
| F2 | JP225.cash | -0.0128502254 |
| F2 | US100.cash | -0.0019393847 |
| F2 | US30.cash | +0.0228581661 |
| F2-2x | JP225.cash | -0.0582348052 |
| F2-2x | US100.cash | -0.0498452945 |
| F2-2x | US30.cash | -0.0249168534 |

| column | W2 rejects | occupied rejects | cooldown | cluster cap | global cap | day-fill cap | day-loss-streak cap |
|---|---:|---:|---:|---:|---:|---:|---:|
| D0 | 5,526 | 807 | 304 | 465 | 148 | 48 | 171 |
| F1 | 5,520 | 823 | 294 | 470 | 151 | 33 | 176 |
| F2 | 5,533 | 812 | 286 | 466 | 148 | 39 | 207 |
| F2-2x | 5,533 | 812 | 286 | 466 | 148 | 39 | 207 |

Queue fields were all zero because registered queue mode was off. [MEASURED:
development-edge command @
`18b04c7a8613fcfdee952d2ceb7cddbed54eccd4`]

| column | normalized event SHA256 |
|---|---|
| D0 | `aa7064cc2509cf1c7cdb158dae57feedc2e584098c72b5bf01b2b9a3bbda4a13` |
| F1 | `6f0025dffec7011edf9a3a2701df7775a26b34b51cbae9d6efc3c557c24bd849` |
| F2 | `6cd7b86866592927bd22475465feff138324c2487d8219a6a022e73b08b111a0` |
| F2-2x | `c34e15c96c7c2413dae8c77809c6f7bdbcc14b43b1007487e52f81e526d6d79e` |

The exact 15 failures were:

1. `F1_PER_BAR/US30.cash: symbol expectancy < 0`
2. `F1_PER_BAR: cross-server-midnight streak semantics differ from EA`
3. `F2_STRICT_ASK/US30.cash: symbol expectancy < 0`
4. `F2_STRICT_ASK/without-JP225.cash: pooled expectancy <= 0`
5. `F2_STRICT_ASK/without-US100.cash: pooled expectancy <= 0`
6. `F2_STRICT_ASK: cross-server-midnight streak semantics differ from EA`
7. `F2_STRICT_ASK_2X: pooled expectancy <= 0`
8. `F2_STRICT_ASK_2X: last-four-quarter expectancy <= 0`
9. `F2_STRICT_ASK_2X/JP225.cash: symbol expectancy < 0`
10. `F2_STRICT_ASK_2X/US100.cash: symbol expectancy < 0`
11. `F2_STRICT_ASK_2X/US30.cash: symbol expectancy < 0`
12. `F2_STRICT_ASK_2X/without-JP225.cash: pooled expectancy <= 0`
13. `F2_STRICT_ASK_2X/without-US100.cash: pooled expectancy <= 0`
14. `F2_STRICT_ASK_2X/without-US30.cash: pooled expectancy <= 0`
15. `F2_STRICT_ASK_2X: cross-server-midnight streak semantics differ from EA`

[MEASURED: JSON `edge_gate.failures` @
`e777d5aead187ffdb94e886b287987385bd46d6b`]

The fidelity control output was:

```text
V130_FIDELITY
symbol=US30.cash D0_n=1318 D0_max_abs_r_delta=0.0000000000001597 F1_n=1304 F1_max_abs_r_delta=0.0000000000000001
symbol=US100.cash D0_n=1267 D0_max_abs_r_delta=0.0000000000000998 F1_n=1243 F1_max_abs_r_delta=0.0000000000000002
symbol=JP225.cash D0_n=1172 D0_max_abs_r_delta=0.0000000000000601 F1_n=1140 F1_max_abs_r_delta=0.0000000000000002
fidelity_pass=True D0_total=3757 D0_max_abs_r_delta=0.0000000000001597 F1_total=3687 F1_max_abs_r_delta=0.0000000000000002
```

[MEASURED: `python backtest/v130_fidelity.py` @
`e777d5aead187ffdb94e886b287987385bd46d6b`]

This runner accessed only the mined frame; its code has no confirmation or
holdout CLI. Global pristine/blind status remains conditional on owner
attestation about any manual or untracked access. [MEASURED: runner source @
`18b04c7a8613fcfdee952d2ceb7cddbed54eccd4`]
