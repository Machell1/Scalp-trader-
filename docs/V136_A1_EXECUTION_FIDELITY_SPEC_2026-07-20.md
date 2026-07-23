# v1.36-A1 execution-fidelity audit specification

Date: 2026-07-20

Status: **PRE-REGISTERED BEFORE NEW AUDIT IMPLEMENTATION, METADATA CAPTURE,
TELEMETRY CENSUS, TAPE CONSTRUCTION, OR MONTE CARLO EXECUTION.** This is a
neutral fidelity measurement of the already-confirmed v1.36-A1 rules. It is
not an improvement search. Results must be reported whether they improve,
worsen, or leave the published estimate unchanged.

Nothing in this study authorizes an EA source change, compilation, terminal
file write, chart/input change, order action, position action, terminal
restart, symbol admission, A1+D1 test, or deployment.

## Provenance and rule resolution

Parent commit: `7c21153900b83e3253ee4c1713bf1913740b9b85`.

`CODEX_CONSTITUTION.md` is absent at the parent commit although `README.md`
links it as binding, while `CODEX_HANDOFF.md` says it was repealed. This study
follows the stricter surviving README research rules: isolated branch, frozen
data, pre-registration and SHA256 sidecar before outcomes, full failure
reporting, no live trading action, and owner review before any later release.

Frozen artifacts at the parent commit:

- canonical EA source SHA256
  `531d2a8b305e145241d00b9db11f716b49f1d90f190914046ce7b7cdae02b833`;
- data-manifest SHA256
  `ec1fcc26132366ab157b8d298c1cf60d79d63ac16708d1a887a1740ad46de49f`;
- broker-metadata SHA256
  `bb0b3489c48e7cad83e5a85c3eea6005db7c5ec0e7ed9098c76814bb049cd3a6`;
- corrected A1 result SHA256
  `712bd41522d7874dd8a20dff6ccea8d919b6e167ee70d5937f646e0c27d82c3d`;
- protected H1 builder SHA256
  `92151e8962fe23588ede2f5aaa31c5fd0d2afe4f5c0e6c4b37433ef9dff6333a`;
- Python risk-policy SHA256
  `971736ff32e47fdbeaddbf355050d4a9c2cad406545d086c5e2a3014251d3bd1`;
- Python pass-policy SHA256
  `00eb4b170c11464f099f511ef9d00d6c1d76f66366b4cee86c44dfa4b83304d9`;
- C# pass-policy-kernel SHA256
  `b9bb45e8c04fa0648f7a44a99fc77bd898045128d724975ac85a934f1c845a00`.

The conservative program trial floor is 300, as registered in the post-A1
signal challenge and the stopped universe-admission study. README's older 129
is not used. This audit charges zero discovery hypotheses and three
confirmatory fidelity cells: `300 -> 303`. Synthetic tests, protected
regressions, read-only telemetry rows, and deterministic rounding examples are
controls rather than strategy cells.

## Prior information disclosed before registration

The source audit that motivated this protocol already established:

1. The validated builder and v1.30 reference define `+1R` from frozen
   signal-bar Wilder ATR times `InpStopAtrMult`.
2. v1.36-A1 inherits v1.32 A5, which instead assigns `riskPrice` from the
   weighted actual entry to the currently placed SL when readable and uses it
   to form the partial level. The same reassignment occurs during restart
   restoration.
3. The account simulator already floors partial volume to broker step, checks
   both close and remainder against minimum volume, and uses actual remaining
   volume for final P&L. The corrected 100,000-path A1 result recorded zero
   rounding skips and zero minimum-lot rejections/substitutions. The earlier
   claim that it always banks a mathematical 75% was wrong and is withdrawn.
4. The historical builder books a partial at its trigger price. The EA closes
   at the next executable market price after a tick or bar-catch-up trigger and
   logs the difference as `slippage_R`.
5. The corrected builder inserts a partial before a same-bar final target.
   Live management is heartbeat-driven while TP is broker-side, so a move from
   the partial level to TP between heartbeats can close the full position before
   the partial request exists.
6. Static inspection identified additional possible fidelity defects: the
   short bar-catch-up test reads bid-bar lows although a short close triggers
   on ask; restart can rebuild R from a moved current SL; immediate entry
   retries are back-to-back; partial-success order retcodes are not accepted
   by the entry success condition; and ticket-keyed persisted state is not
   namespaced by account and magic.

These observations are source facts and hypotheses about materiality. No new
historical outcome, metadata snapshot, live partial census, counterfactual
tape, or account path has been inspected for this study before registration.

## Frozen question

Does the live v1.36-A1 partial lifecycle materially differ from its published
corrected account model because the EA uses placed-stop R rather than frozen
signal R, or because a market partial is filled away from its trigger? Are
the already-modeled broker volume rules implemented identically in the EA,
Python, and C# paths?

## Frozen strategy and account rules

Every column retains the confirmed A1 strategy without selection or tuning:

- universe and priority: `US30.cash`, `US100.cash`, `JP225.cash`, `USDJPY`;
- clusters: `US30.cash|US100.cash;JP225.cash;USDJPY`;
- H1 signals, six-bar impulse at least 3.0 ATR, Wilder ATR(14), W2 at least
  0.30 ATR, both directions;
- pullback limit 0.60 ATR, bar-counted three-bar pending window;
- SL 1.0 signal ATR, nominal bank 75% once at +1R, final TP 1.5 signal ATR,
  eighth-H1-bar time exit;
- stop first, partial second, final target third on ambiguous bars;
- E2 stressed costs, existing symbol/cluster/global seats and account rails;
- risk 0.300% for the index trio and 0.050% for USDJPY in both phases.

No threshold, symbol, side, risk, target, hold, fill-window, cost, priority, or
portfolio rule may change.

## Exact geometry

For side `s` in `{+1,-1}` and positive prices, use MQL5-compatible tick
snapping (nearest tick, half upward):

```text
R_signal       = frozen_signal_ATR * 1.0
stop_floor     = 1.5 * trade_stops_level * point
R_sizing       = max(R_signal, stop_floor)
entry_raw      = signal_close - s * 0.60 * frozen_signal_ATR
entry_request  = SnapPrice(entry_raw)
SL_request     = SnapPrice(entry_request - s * R_sizing)
TP_distance    = max(1.5 * frozen_signal_ATR, stop_floor)
TP_request     = SnapPrice(entry_request + s * TP_distance)
R_placed       = abs(entry_request - SL_request)
partial_frozen = entry_request + s * R_signal
partial_placed = entry_request + s * R_placed
```

The historical requested-price calculation assumes a resting limit fills at
`entry_request`. Canonical OHLC cannot reveal actual broker improvement or
slippage. Actual weighted-fill-to-SL R is measured only where read-only live
telemetry contains sufficient fields; it is never imputed into history.

Lot sizing remains based on `R_sizing`, matching order placement. Physical SL
and TP requests are identical between the two primary columns. Only the
partial trigger denominator is allowed to differ.

## Three registered fidelity cells

| Cell | Partial denominator | Volume execution | Role |
|---|---|---|---|
| `C0_FROZEN_R_STEP` | `R_signal` | existing broker floor/min/remainder rules | intended v1.30/A1 control |
| `F1_PLACED_R_STEP` | `R_placed` | identical broker floor/min/remainder rules | current v1.36 A5 semantic |
| `B1_PLACED_R_TP_FIRST` | `R_placed` | identical broker rules, but suppress the partial when partial and final TP first appear in the same H1 bar | heartbeat/TP race endpoint |

The published unsnapped A1 tape remains a protected regression and context,
not a selectable third cell. Exact-75% partial volume is not an account cell;
it is only a deterministic explanatory comparison because it is not what the
EA or corrected simulator executes.

No cell may be chosen because it performs better. `B1` is an extreme endpoint,
not an estimate of how often a five-second race occurs. A whole-position TP can
raise gross R while also changing variance, so its direction is predeclared as
unknown. The canonical semantic is decided from the frozen specification and
implementation lineage; performance only quantifies the consequence of drift.

## Read-only FTMO metadata and telemetry freeze

After the spec commit, one audit script may initialize only the documented
FTMO terminal executable, then must verify login `1513946641` and server
`FTMO-Demo` before reading anything. It may read only terminal/account identity,
terminal build, and `symbol_info` for the four frozen symbols. Required fields
are point, digits, trade tick size, trade stops/freeze levels, tick values, and
volume min/step/max. Tick, point, tick values and volume fields must be
positive; stops/freeze levels may be zero but not negative. It must not call
any order function, copy rates, change a
setting, restart a process, or write inside the terminal data folder. Account
or server mismatch, a missing symbol, or an invalid required field stops the
study. The resulting JSON is committed and SHA256 reported.

The audit may read, never alter, the existing terminal-side
`MomentumPullback_partials_v130.csv` and related A1 trade/decision logs. The
window begins at the documented successful A1 initialization,
`2026-07-18T18:40:03-05:00`, and ends at the metadata-capture UTC timestamp.
Rows must be attributable to that flat-start A1 deployment lineage; any row
whose account/magic lineage cannot be established from the frozen files is
excluded and counted. Every included/excluded row count is reported. Zero rows
or zero A1 partials is `n=0`, never backfilled.

For each usable partial position, report nominal close volume, modeled broker
close volume, logged target volume, cumulative actual deal volume, effective
bank fraction, trigger tag, level, fill, price slippage, and slippage R.
Model/log disagreement of any size is a discrepancy. Live performance is not
estimated from this census. Split normal-tick and `bar-catchup` triggers and
report minimum, p10, median, p90 and maximum fill R/slippage R, plus counts with
fill R at or below zero and slippage worse than -0.25R. A bar-catchup fixture
must prove that a historical bar touch followed by a current quote below entry
can close a long partial at a loss; that behavior is never represented as a
guaranteed +1R bank.

## Audit-only implementation

New tooling must be additive and default-off. Existing builders and account
engines retain byte-identical default behavior. Separate fields must represent
`R_signal`, `R_sizing`, and `R_placed`; the existing `stop_distance` must not
be overloaded to serve incompatible purposes.

The source-tape comparison uses the same signals, admission decisions, pending
occupancy, entry assumption, SL, TP and time exit in both cells. It reports:

- counts and distributions of `R_placed/R_signal`, signed and absolute level
  shifts in price, ticks, and R;
- counts where the stop floor binds;
- partial occurrence/time differences, final-reason differences, and every
  affected trade ID;
- counts of partial-plus-TP in the same H1 bar and the cash/outcome effect of
  suppressing those partials in the registered TP-first bound;
- pooled, per-symbol, side, stitched-OOS-quarter, and E2-stress expectancy;
- gap-through/marketable-at-next-open cases separately, without changing their
  fill price.

The volume audit independently mirrors EA, Python, and C# formulas:

```text
raw_close = initial_volume * 0.75
close      = floor((raw_close + 1e-12) / volume_step) * volume_step
skip if close < volume_min
skip if initial_volume - close < volume_min
effective_bank_fraction = close / initial_volume
```

It covers every one-cent volume from 0.01 through 2.00 plus all volumes reached
by deterministic sizing of every A1 entry at balances 91,000, 100,000, and
110,000. Report exact matches, skips, fraction shortfall, and the worst case.

## Mandatory pre-outcome gates

1. `python backtest/verify_data.py` prints exactly
   `verified 46 OK, 0 missing, 0 mismatched`.
2. Legacy regression remains 1,645 trades / 7,317 events / SHA256
   `3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f`.
3. C1 remains 1,684 admitted trades / 7,145 events / SHA256
   `b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187`.
4. Published A1 remains 662 admitted trades / 2,819 events / SHA256
   `3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573`.
5. Existing pass-policy, risk-policy, adapter, and relevant builder synthetic
   suites pass unchanged.
6. Two independent builds of each new cell produce identical event bytes.
7. Existing default paths remain byte-identical before and after audit-tool
   implementation.
8. EA/Python/C# volume helpers agree on every registered volume case.
9. New deterministic fixtures cover long/short exact tick geometry, one-tick
   snap drift, binding stop floor, partial level at/above TP, favorable and
   adverse fill displacement, normal and minimum-lot partials, invalid
   remainder, short bid-low without ask-low touch, entry-bar pre-fill touch,
   restart after a moved SL, partial-success entry retcode, and stale persisted
   ID under a different account/magic.
10. Admissions, entry epochs, requested SL/TP, and time-exit clocks are exactly
    identical across C0, F1 and B1. Only registered partial geometry,
    same-bar-TP partial suppression in B1, downstream lifecycle resolution,
    cash, and path-dependent account rails may differ.

Any failure stops the study and is reported verbatim. It is not repaired and
rerun inside a registered cell.

## Paired account materiality stage

Run exactly 20,000 common-random-number paired paths for C0, F1 and B1 using seed
`13020260711`, 20-day moving blocks, 500-path chunks, common eligible flat
blocks, E2 stress, and the existing two-phase simulator. Python/C# path 0 must
match exactly for all three cells before the screen.

Run a fresh 100,000-path confirmation only if the screen has at least one
discordant both-phase pass, hard-halt, timeout, or firm-breach path. Otherwise
record exact account-level equivalence and do not spend the conditional run.

For every executed stage report all three cells' phase-1 pass, conditional phase-2
pass, both-phase pass and Wilson interval, hard halt and Wilson upper, timeout,
firm breach, successful median/p90 days, paired discordant counts, point
deltas, conservative paired bounds, row hashes, event hashes, and every
simulator counter.

## Verdicts and kill conditions

- `A1_FIDELITY_EQUIVALENT_ON_REGISTERED_FRAME`: C0 and F1 have identical
  lifecycle and account hashes. Source semantic drift still remains documented.
- `A1_FIDELITY_DRIFT_IMMATERIAL`: source lifecycles differ, but no account path
  is discordant at the screen or confirmation and all absolute gates remain.
- `A1_REBASED_TO_PLACED_R`: account outcomes differ while F1 retains a
  both-phase one-sided 95% Wilson lower bound at least 88%, hard halt at most
  0.3700%, and zero firm breaches. The published 90.994% may no longer be used
  as the live-semantic headline; F1 becomes the only admissible historical
  control for future comparisons.
- `A1_FIDELITY_INVALIDATED`: F1 fails any absolute gate above. This is the
  headline finding and A1+D1 is prohibited.
- `A1_HEARTBEAT_AMBIGUITY_MATERIAL`: B1 fails an absolute gate, or a two-sided
  95% paired interval for its pass delta versus F1 excludes zero in either
  direction. This does not prove the endpoint occurs on every ambiguous bar;
  it blocks A1+D1 until M15/real-tick evidence resolves the race.
- `INSUFFICIENT_LIVE_PARTIAL_EVIDENCE`: fewer than 20 usable A1 live partials.
  Historical and synthetic results remain reportable, but live slippage is not
  generalized and the live fill-price gap remains unresolved.

Any short-side catch-up, restart, persistence, retcode, or account-namespace
fixture that contradicts the frozen semantics is reported as a deterministic
implementation defect regardless of account-MC materiality. It cannot be
rationalized by a favorable backtest result.

## M15 boundary and sequence before A1+D1

The previously registered M15 universe study stopped at an E1/E2
`source_lifecycle` control failure before candidate cells. This audit may cite
that failure but may not repair or reopen that study. A new, separately hashed
pure-control branch must diagnose the first differing field and establish a
trustworthy M15 quote-side A1/C1 control before any A1+D1 outcome is viewed.

Only after this audit and that separate M15 control both complete may a new
one-cell specification test A1's 3.0-ATR threshold with a 0.40-ATR pullback.
No pullback neighbor, rescue grid, symbol change, risk change, or live default
change is permitted.

## Required report and artifacts

The final report must include every command and commit, verbatim failures,
spec/data/source/metadata/runner/result hashes, source-line findings, all
synthetic fixtures, full volume and R-drift censuses, every affected trade,
all paired account fields, the read-only terminal-access journal, and an
explicit statement that no EA or terminal state was changed.

Every quantitative statement is tagged `[MEASURED: command @ commit]`,
`[DERIVED]`, or `[HYPOTHESIS]`.
