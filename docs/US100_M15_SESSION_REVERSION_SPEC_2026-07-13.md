# US100 M15 session-open mean-reversion proxy — pre-registration

Date: 2026-07-13  
Branch: `codex/session-open-mean-reversion`  
Base commit: `35e83651f063be103fa7431c2f8a35a029b2b1d4`

## 1. Question, prior, and scope

The owner supplied a video describing a discretionary Nasdaq one-minute
session-open fade: identify a pre-open fair-price area, wait for an opening
displacement, consolidation and fading volume, then use a market order after a
structure break back toward fair value. This study asks whether a fully causal,
mechanical **M15 proxy** of that mechanism has positive out-of-sample US100
expectancy at a fixed 3:1 reward/risk target after executable-side spread and
the repository's registered slippage stress.

There is no frozen M1 history in the workspace. M15 cannot recover the first
minute, the intrabar M1 path, minute-level volume, or the video's discretionary
chart reading. This study therefore makes no M1 claim and will not synthesize
M1 observations. A true M1 test requires a separately frozen dataset and a new
pre-registration.

The prior is neutral-to-low. `docs/SESSION_SPEC_2026-07-13.md` already found
that cash-session filters and an ORB-retest overlay did not improve the existing
v1.30 momentum-pullback family. This is not another filter on that family: it
is a separate, one-trade-per-day mean-reversion entry with its own anchor,
signal and bracket. No earlier session result is used to tune this rule.

The owner requires at least 3R gross geometry, so 3R is the only candidate
tested. The video's smaller example target is not tested as a rescue cell.
Win rate is reported but is not optimized or used as a gate. Historical passage
cannot establish an 88% FTMO account pass probability; it only authorizes a
separate, unchanged-rule account-level pre-registration.

## 2. Authority and live-system boundary

This branch may read only frozen repository data. It may not call MT5, an API,
or the internet at outcome time; refresh data; edit an EA; compile or deploy;
change terminal or EA settings; or place, modify, or close an order. The current
v1.31 H1 EA remains untouched. No result from this study authorizes a live
change.

## 3. Frozen inputs and provenance

Primary price file:

* `backtest/data/derivM15_spreadgated/US_Tech_100.csv`
* SHA256:
  `f62bf95c4a7a6ef1e3cd56582db24d5f6a713815647b1beda4098b91dfd946d9`
* Expected schema, in order:
  `time,open,high,low,close,volume,spread,spread_price`
* `time` is a UTC bar-open timestamp despite having no printed offset.
* OHLC is treated as bid. `spread_price` is the observed full spread in price
  units. Synthetic ask is bid plus the contemporaneous `spread_price`.
* `volume` is the exporter-renamed MT5 tick-volume count, not centralized
  exchange volume or liquidation/order-book data.

The runner must first execute the same checks as
`python backtest/verify_data.py`. The only acceptable canonical verification is
`verified 46 OK, 0 missing, 0 mismatched`. It must independently verify the
primary file hash, exact columns, strictly increasing unique timestamps,
finite positive OHLC, nonnegative spread, and OHLC consistency. Any mismatch
stops before a cell is evaluated.

Session exclusions are frozen in
`backtest/calendars/us_equities_session_exclusions_2024_2026.csv`, SHA256
`a019c12412906f681b7d5fd9279f30ac850548f1acd21c24ca5fdf6f87f89791`.
The file records U.S. equity full closures and 13:00 ET early closes for the
covered years. Its sources are the Nasdaq 2024/2025 trading calendars, the
Nasdaq 2026 holiday schedule, and Nasdaq's 2025-01-09 national-day-of-mourning
notice. Runtime code may not regenerate or amend the dates.

## 4. Clock, sessions, and causal indicators

1. Parse source timestamps with `utc=True` and convert them with the standard
   IANA zone `America/New_York`. Never use a fixed UTC offset.
2. M15 timestamps are bar opens and intervals are half-open. For example, the
   09:15 bar contains 09:15:00 through 09:29:59 ET and is complete at 09:30.
3. A candidate session is a Monday-through-Friday New York date within the
   data range that is absent from the frozen exclusion file.
4. A date is eligible only if it contains exactly one bar at every 15-minute
   open from 09:15 through 13:45 ET inclusive (19 contiguous bars). Any missing,
   duplicate or non-contiguous required bar rejects the whole date and is
   reported in the funnel.
5. Wilder ATR(14) is computed once over the complete chronological bid series
   using `scalper_backtest.wilder_atr`. `A` is the finite positive ATR known at
   the close of that date's 09:15 bar and is frozen for the setup.
6. `F` is the 09:15 bid close. This is the disclosed M15 proxy for the video's
   roughly 09:29 fair-price anchor.

No future bar, full-day volume, calibrated time bin, or later ATR value may
enter the signal.

## 5. Candidate `MR3`

All comparisons below are strict unless equality is explicitly allowed.

### 5.1 Opening displacement

The opening impulse is exactly the 09:30 bar. Let
`I = close_0930 - F`. Require `abs(I) >= 1.0 * A`; equality passes. The sign of
`I` fixes the only permitted fade direction for the date:

* `I > 0`: candidate direction is short, toward `F`;
* `I < 0`: candidate direction is long, toward `F`;
* `I == 0`: reject.

### 5.2 Consolidation and tick-volume fade

The consolidation box is exactly the 09:45, 10:00 and 10:15 bars.

* Width `max(high) - min(low) <= 1.0 * A`; equality passes.
* All three closes must remain strictly on the impulse side of `F`.
* Each of the opening and box bars must have finite, strictly positive tick
  volume.
* The median box volume must be strictly below 09:30 volume.
* The 10:15 volume must be strictly below 09:45 volume.

### 5.3 Structure break and market entry

The trigger is the first qualifying close among exactly 10:30 then 10:45 ET:

* Upward impulse: trigger close is below the box low and still above `F`.
* Downward impulse: trigger close is above the box high and still below `F`.

Enter with a market order at the next bar open: 10:45 for a 10:30 trigger or
11:00 for a 10:45 trigger. The later entry is explicitly allowed. Let `P` be
that entry bar's bid open and `s` its nonnegative observed full spread.

* Long entry executable price is `P + s`; short entry executable price is `P`.
* Long gross reward distance is `F - (P + s)`; short gross reward distance is
  `P - F`.
* A nonfinite or nonpositive reward distance cancels the setup.
* Frozen risk distance is `reward_distance / 3.0`.
* Long target is bid `F`; long stop is bid
  `entry_ask - risk_distance`.
* Short target is ask `F`; short stop is ask
  `entry_bid + risk_distance`.

This makes target and stop exactly +3R and -1R in executable-price space before
fixed slippage. There is no minimum-stop filter, broker-stop rescue, partial
close, breakeven, trail, runner, queue, re-entry, side flip, news filter, or
overnight hold. There is at most one setup and one trade per date.

### 5.4 Resolution

The entry bar participates. On every bar, bid OHLC is the file's OHLC and ask
OHLC is bid OHLC plus that bar's observed spread.

* Long stop/target touches use bid low/high; short stop/target touches use ask
  high/low.
* If stop and target are both touched in one bar, stop wins.
* If a bar opens through a stop, book the worse executable open: the lower of
  stop and bid open for a long, or the higher of stop and ask open for a short.
* A target receives no favorable gap improvement; book the target level.
* If neither resolves, exit at the executable close of the 13:45 bar (14:00 ET):
  bid close for a long and ask close for a short.

Zero-slippage trade return is executable P&L divided by the frozen risk
distance. Index commission is zero under the frozen broker calibration and
the intraday trade crosses no swap rollover.

## 6. Matched control `C1`

`C1` uses every `MR3` qualifying date and the identical entry bar, observed
spread, frozen risk distance and time exit, but takes the opposite direction
away from `F`. Its entry is executable on its own side. Its target is three
risk distances from its executable entry in the control direction and its stop
is one risk distance against it. It uses the same side-correct touch, gap,
stop-first and exit rules. It is not allowed to generate additional dates.

This control asks whether the return is attributable to the registered
mean-reversion direction rather than merely the selected time and volatility
state.

## 7. Cost columns

Observed per-bar spread is already embedded in entry, touch and exit prices, so
no median-spread debit is added.

* `E0_EXEC`: executable-price diagnostic, no added slippage.
* `E1_MEASURED`: `E0_EXEC - 0.02R` per completed trade.
* `E2_STRESS`: `E0_EXEC - 0.04R` per completed trade.

These follow the registered v1.30 executable cost ledger. E2 is the binding
column; E0 cannot rescue a failure. E0/E1/E2 are repeated cost views of the two
registered hypothesis cells, not six separate design cells.

## 8. Frames and statistics

The binding OOS frame is the last four complete New York calendar quarters in
the frozen file: 2025Q3, 2025Q4, 2026Q1 and 2026Q2. All earlier eligible dates
are development/warm-up only. A conventional chronological 70/30 split by
eligible session date is reported as a nonbinding diagnostic and cannot rescue
the binding frame.

For both cells and every cost column report:

* full, development, binding OOS and diagnostic-70/30 trade counts;
* expectancy, win rate (`R > 0`), profit factor, cumulative-R maximum drawdown,
  median R, and longest strictly negative-R streak;
* each binding quarter's count and expectancy;
* setup-funnel counts for session, completeness, ATR, impulse, box, volume,
  trigger, valid reward and completed trade;
* qualifying trades per eligible day, per five eligible days, and per calendar
  week, plus long/short counts;
* minimum/median/maximum risk distance, entry spread in R, and holding bars.

No result is annualized. This one-symbol, one-trade-per-session rule cannot by
itself meet a six-trades-per-day portfolio objective. Cross-symbol expansion is
permitted only under a new unchanged-rule replication spec after passage.

## 9. Inference

Use seed `13020260713`.

* Circular moving-block bootstrap: 20,000 replicates, blocks of five
  consecutive chronological OOS trade pairs, sampling until the original OOS
  pair count is reached and truncating excess. Report the fifth percentile as
  the one-sided 95% lower bound for `MR3` E2 expectancy and paired
  `MR3 - C1` E2 mean delta.
* Paired direction placebo: 20,000 fixed-seed sign flips of the OOS paired E2
  deltas. One-sided p-value is
  `(1 + count(null_mean >= observed_mean)) / 20001`.
* DSR: call the repository's `experiment.psr` with
  `walkforward_dsr.dsr_hurdle(n_trials=278, n_obs=n_oos)` on `MR3` E2 returns.

The bootstrap and sign-flip machinery are inferential controls, not additional
parameter cells.

## 10. Binding gates and verdict

All gates must pass; there is no rescue or majority vote.

1. OOS contains at least 50 completed paired trades.
2. `MR3` OOS expectancy is strictly positive under E1 and E2.
3. The one-sided 95% block-bootstrap lower bound for `MR3` E2 expectancy is
   strictly above zero.
4. OOS paired E2 mean delta `MR3 - C1` is at least `+0.03R`, and its one-sided
   95% block-bootstrap lower bound is strictly above zero.
5. Paired sign-flip p-value is at most `0.05`.
6. Each of the four binding quarters has at least 10 `MR3` trades; at least
   three quarters have positive E2 expectancy, including 2026Q2.
7. `MR3` E2 DSR is at least `0.95` using the 278-trial global ledger.

Verdict is `HISTORICAL PASS` only if all seven pass. Any failed gate yields
`KILL — NO ACCOUNT TEST`. A historical pass queues one separately hashed,
unchanged-rule FTMO confirmation/account specification; it does not authorize
deployment and is not an 88% pass-rate claim.

## 11. Kill conditions, tests, and reproducibility

Stop before outcomes on any data/calendar/spec hash mismatch; canonical data
verification other than 46/0/0; timestamp, DST or OHLC invariant failure;
synthetic entry/touch/stop-first/gap/clock test failure; tracked dirty-tree
change; or nondeterministic rerun.

The standalone runner may import only shared deterministic indicator/statistic
helpers. It must not modify the existing simulator. Before the outcome command,
commit the spec, calendar, runner and tests; run synthetic tests; record the
exact commit; and ensure no tracked changes. The outcome JSON must be emitted
with sorted keys and stable float serialization. Run the outcome command twice
and require byte-identical JSON SHA256.

After the run, append every result and failure below this marker without
altering any byte above it. Stage only named study files; preserve unrelated
untracked artifacts.

## 12. Trial ledger

The repository has no consolidated current ledger. Reconciliation before this
study is 267 tested cells merged to main plus nine visible tested cells on
unmerged branches, for a conservative global start of 276. This is
`[DERIVED]`, pending owner adjudication.

Charge `+1` for `MR3` and `+1` for matched control `C1`, including failures.
The fixed cost views, bootstrap and sign flips do not add designs. Global
ledger after this run is 278. No account cell is registered here.

## 13. Disclosed design freedom

The video does not supply the M1-to-M15 conversion, 09:15 anchor proxy, 1ATR
impulse threshold, three-bar/1ATR box, exact tick-volume tests, two-bar break
window, 11:00 latest entry, 14:00 exit, one-trade limit, exchange-calendar
handling, executable bid/ask convention, 3R owner constraint, costs, controls,
OOS split, inference, or gates. All are new researcher choices frozen here.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `26810e10f82d65bc2c68a284e8acb663bb6f9cac1d95d8ffec489d3ce338b2f1`

---

## Results

Not run at pre-registration time.

### Pre-outcome implementation clarifications

These choices were recorded before any strategy outcome command:

* The diagnostic 70/30 date cut uses `floor(0.70 * N)` complete eligible
  dates in the first segment and all remaining dates in the second.
* Dates after 2026-06-30 are full-sample-only and cannot enter development or
  binding OOS gates.
* Holding bars count the entry bar as bar one.
* Profit factor is JSON `null` when there is no strictly negative return.
* Both inference procedures use NumPy `default_rng` (PCG64); each procedure
  separately reinitializes the stream with seed `13020260713`.
* A duplicated source timestamp is a fatal global data-integrity error. A
  missing/non-contiguous required session bar rejects that date.
* Mean trades per calendar week includes zero-trade weeks that contain at least
  one complete eligible session.

### Pre-outcome synthetic-test record

The first test invocation exposed five test/implementation-fixture defects
before any outcome run: Pandas datetime integer units were not portable across
versions; two spread-trap fixtures had inconsistent OHLC; and one frame fixture
omitted June 30. Output ended `5 failed, 12 passed in 19.64s`. Epoch conversion
was changed to explicit UTC epoch seconds and the synthetic fixtures were
corrected without consulting strategy outcomes. The next invocation ended
`17 passed in 17.11s`. A later pre-commit invocation ended
`1 failed, 17 passed in 24.08s` solely because the newly appended clarification
made the protocol working copy differ from committed `HEAD`, which is the
intended hash guard. The final synthetic gate is run only after committing all
pre-outcome files. After the independent code-review fixes, the pre-commit
suite excluding that one provenance check ended
`19 passed, 1 deselected in 14.43s`; the independent reviewer separately
reported `19 passed, 1 deselected in 12.19s` and a no-blocker verdict.

### First registered-command failure (no outcome produced)

The first registered command stopped in date construction before setup
enumeration. Canonical/hash checks had passed, but no signal, trade or statistic
was produced. Output was:

```text
Traceback (most recent call last):
  File "C:\Users\Sanique Richards\Downloads\codex-scalp\backtest\run_us100_m15_session_reversion.py", line 815, in <module>
    main()
    ~~~~^^
  File "C:\Users\Sanique Richards\Downloads\codex-scalp\backtest\run_us100_m15_session_reversion.py", line 808, in main
    result = run()
  File "C:\Users\Sanique Richards\Downloads\codex-scalp\backtest\run_us100_m15_session_reversion.py", line 729, in run
    eligible, funnel, setups, trades = enumerate_trades(data, exclusions)
                                       ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
  File "C:\Users\Sanique Richards\Downloads\codex-scalp\backtest\run_us100_m15_session_reversion.py", line 442, in enumerate_trades
    candidates = candidate_dates(data, exclusions)
  File "C:\Users\Sanique Richards\Downloads\codex-scalp\backtest\run_us100_m15_session_reversion.py", line 273, in candidate_dates
    start = pd.Timestamp(data.local_date[0])
  File "pandas/_libs/tslibs/timestamps.pyx", line 2738, in pandas._libs.tslibs.timestamps.Timestamp.__new__
  File "pandas/_libs/tslibs/conversion.pyx", line 367, in pandas._libs.tslibs.conversion.convert_to_tsobject
TypeError: Expected str, got numpy.str_
```

The only correction is explicit conversion of the NumPy string scalar to a
built-in `str`, plus a synthetic regression test. No protocol threshold,
signal, execution rule, frame, statistic or gate changed.
