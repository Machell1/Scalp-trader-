# Live-parity fidelity audit + opportunity recovery — pre-registration (2026-07-12)

**Origin:** Codex memo 2026-07-12 (four "W2 opportunity recovery" ideas). The resident
verified Codex's central claim against source and found the enumeration gap is WIDER
than reported. This audit is executed in-house by the resident; Codex's replication
assignment continues independently.

**Reframe (binding):** this is NOT an improvement hypothesis. It is a MEASUREMENT
CORRECTION of already-gated rules. Every headline number in the program (W2×3 87.4%
both / 6.8% bust / med 52d; W3×4 89.9%; timeline W2×3 88.0%/76d, W3×4 90.6%/93d) was
computed on an enumeration that is not what the live EA executes. Expectation is
neutral: corrected numbers may be better, worse, or unchanged. Success = the corrected
numbers, whatever they are. If a previously-passed gate FAILS on the corrected tape,
that is the headline finding and the challenge purchase is blocked pending owner
decision.

## Verified enumeration mismatches (source-cited)

The validated harness (`scalper_backtest.py::simulate_symbol`) vs the live EA
(`MomentumPullbackEA.mq5` v1.29.1, chart-verified inputs 2026-07-11):

| # | Mismatch | Harness | Live EA | Cite |
|---|---|---|---|---|
| 1 | W2 ordering | post-hoc filter on `signals_out`: non-W2 trades occupy the engine and shadow later W2 signals | W2 checked pre-entry (799–816): non-W2 signals never occupy | Codex's find, verified |
| 2 | Unfilled pending occupancy | unfilled → next signal bar i+1 eligible (line 231–233) | pending works bars i+1..i+3, cancelled at open of i+4 BEFORE that pass's scan → first eligible signal bar = i+3; signal bars i+1, i+2 consumed-and-dropped | resident's find; EA 1077–1091, 467–468, 500 |
| 3 | Portfolio coupling | per-symbol tapes pooled independently into the MC | global cap 2 (positions+pendings, magic, all symbols; line 502/1837), cluster cap 1 (positions+pendings; 691–699/1817), per-symbol cap 1 (689/1776); scan in whitelist order; bar consumed even when capacity-blocked (500) | resident's find |
| 4 | Day gates never modeled | none | MaxTradesPerDay=8 fills (485/528), 4-consecutive-losses day-stop (483) | resident's find |

**Confirmed parity (no correction needed):** post-exit re-arm — both exit types block
exactly the engine exit bar and resume at exit-bar+1 (EA 549–566, 707–713; sim
`i = exit_bar + 1` at line 296). v1.27's cooldown design holds. Fill window i+1..i+3
matches EA bar-counted expiry exactly (working during i+1..i+3, cancelled open of i+4).

**Stated approximations retained (with derivations):**
- `sendMarket` conversion (876–906) modeled as limit-touch fill: with stopsLevel≈0 on
  FTMO index CFDs the residual case (open in (entry, entry+stopsLevel]) is empty; the
  gap-through-open case books the limit price in both engines (pessimistic, validated).
- EA daily-loss halt (4%) not modeled: max daily loss = MaxTradesPerDay(8) ×
  0.3% ≈ 2.4% < 4% — unreachable. [DERIVED]
- DD floors / static floor: account-level, handled by the challenge MC, not the tape.
- News guard, freshness guard, blocked hours (empty live), spread-ATR gate intraday
  variation: not modeled, identical to every prior study (control and corrected columns
  share the omission — deltas are unaffected).

## Instrument set + live config (chart-verified 2026-07-11)

W2×3 (live): US30.cash, US100.cash, JP225.cash · wick ≥ 0.30 · clusters US30|US100 ;
JP225 · MaxConcurrent 2 · risk 0.3%. Deriv proxies: Wall_Street_30, US_Tech_100,
Japan_225 (spread-gated set, real per-instrument cost via `real_cost_per_side`).
W3×4 (pre-committed alternative): + Germany_40 (own EU cluster), wick ≥ 0.50,
MaxConcurrent 2 (as-is) with cap=3 sensitivity (would need an input edit).

## Engine + modes

New file `backtest/parity_engine.py` — event-driven multi-symbol replay of the exact
validated bracket rules (Wilder ATR 14 signal-bar frozen; momentum 6-bar/2.0 ATR with
candle-direction; limit at close ∓ 0.6·ATR; SL 1.0/TP 3.0 ATR; SL-first pessimistic
intrabar incl. the fill bar; time exit close of entry_bar+7; cost = cost_atr_frac·ATR
per side, r = net/1.0·ATR). Two-phase epoch loop: bar-close resolutions (fills, SL/TP,
time exits) for all symbols first, then bar-open management (pending expiry) + scans in
whitelist order. **`scalper_backtest.py` is NOT modified.**

- **M0 sim-parity (golden regression):** reproduces `simulate_symbol` enumeration
  exactly (unfilled → i+1, no pre-entry W2, no caps). GATE: trade-for-trade identity
  ((i, entry_bar, side, r) with |Δr| < 1e-9) on ALL 46 manifest CSVs. Any diff = stop.
- **M1 live-parity per-symbol:** mismatches 1+2 corrected (pre-entry W2 predicate,
  pending occupies to i+3), single symbol, no cross-symbol caps.
- **M2 coupled portfolio:** M1 + mismatches 3+4 (global/cluster/symbol caps counting
  positions+pendings at scan time, whitelist scan order, fills/day cap, consec-loss
  day-stop with r<0=loss reset on r≥0). Sensitivity: reversed scan order (bounds the
  intra-epoch ordering assumption).
- **M2q frozen-queue (Codex idea 3):** M2 + retain a signal blocked ONLY by
  global/cluster capacity (never symbol occupancy, never quality gates): original bar,
  side, ATR, entry/SL/TP, original expiry (open of i+4). Release at a later bar-open
  within the window iff capacity free AND price has not touched entry since the signal
  (buy: min low since > entry). Newest signal per symbol replaces a stale queued one.
  No repricing, no extended expiry.
- **M3 mixed sleeve (Codex idea 2):** M2 with per-symbol thresholds — trio @ 0.30 +
  GER40 @ 0.50. **CONTAMINATED** (GER40-W3 was selected on this same data): decision
  analysis only, can never ship from this frame, labeled so in every table.

## Control column (must reproduce documented numbers)

The control is the CURRENT method, rerun verbatim: `nearmiss_decisions.wick_trades`
tapes + `challenge_mc` (seed 7, 8000/4000 sims, risk 0.3). It must reproduce
W2×3 87.4%/6.8%/52d and W3 trio 89.5%/5.1%/82d before any corrected number is reported.
Failure to reproduce = pipeline broken, stop.

## Cells + ledger

Ledger 146 → **150**: (1) W2×3 corrected census (M1+M2 are one cell — one hypothesis,
two fidelity layers), (2) W3×4 corrected census, (3) M2q queue, (4) M3 mixed sleeve.
DSR re-checks evaluated at N=150 trials using the house `walkforward_dsr` machinery.

## Report format (all cells, all numbers, [MEASURED] only)

Per config {W2×3, W3×4} × {control, M1, M2}: n trades, expectancy, OOS expectancy
(stitched last-30% quarters), win%, 2×-cost OOS, MC both/bust/medDaysP1, full-timeline
median (P1+P2 days), plus deltas vs control. Census of drop reasons in M2 (per-symbol
occupancy, cluster, global, day gates, pending window, cooldown) — this feeds the
queue verdict. Binding frequency of the never-modeled day gates.

## Decision rules (pre-registered)

- **Corrected census:** if W2×3 M2 still clears OOS>0, 2×-cost>0, and MC both/bust not
  materially worse (>2pts both or >1pt bust = material), the documented baseline is
  UPDATED to the M2 numbers and the live config stands. If materially worse or a gate
  fails: headline finding, challenge purchase blocked, owner decides with corrected
  numbers. The live EA is not touched in either branch — it already IS the corrected
  enumeration; only our estimates change.
- **M2q queue (Codex kill conditions adopted verbatim):** discard if baseline trades
  are suppressed/modified; if added-trade OOS expectancy ≤ 0; if pooled OOS expectancy,
  MC both, bust, or 2×-cost deteriorate; if frequency rises without pooled-win-rate
  logic holding (added marginal win rate must exceed nothing — added expectancy > 0 is
  the bar); if added n_OOS < 50 → "insufficient evidence, no ship" regardless of sign.
  A pass here means a v1.30 EA-code proposal (flag-gated, shadow-first, full gate,
  owner sign-off) — nothing ships from this study alone.
- **M3 sleeve:** numbers reported for context only; adoption would require a fresh
  pre-registration on frames this discovery never touched (forward data).
- **Idea 4 (order recovery):** read-only FTMO log/journal audit runs in parallel;
  verdict = count of eligible orders actually lost to transient failures. No cell
  (diagnostic, no hypothesis).

**Prior disclosed:** the resident expects the trio's M2 deltas to be modest (cluster
cap US30|US100 already limits the pair; JP225 sessions barely overlap US) and the M1
W2-recovery effect to ADD trades of unknown quality. Direction of net MC change:
genuinely unknown. The 07-09 finding that added frequency at equal quality speeds
challenges argues up; signal-cluster serial correlation argues down.

*Results appended below the hash line after the runs. Protocol frozen at hash time.*

---
## RESULTS (appended post-run 2026-07-12; protocol hashed pre-run:
SHA256 03b9967a8eba3d0e366f78a62fb2b156f59a06d19b47e90570fce13cb1cc9a90)

### Verification chain (all [MEASURED], scripts in backtest/)
- Golden regression: M0 == simulate_symbol trade-for-trade on ALL 46 manifest CSVs
  (134,626 trades, 0 diffs) — before and after every engine edit.
- Causal engine == independent sequential reference, trade-for-trade, all trio
  symbols, both windows.
- Control column reproduces documented numbers EXACTLY (87.4%/6.8%/52d).
- Independent from-scratch numbers audit (no engine imports): aggregate stats +
  3 hand-verified trades reproduce to float epsilon, including same-bar
  fill-then-stop and 8-bar time exit.
- 5-agent adversarial verification: engine-code refutation attempt FAILED (zero
  down-bias bugs); EA-semantics claims confirmed (2 agent misreads resolved by
  direct grep: cooldown EXISTS at lines 222/560/708; day cap counts FILLS, 528).
- Second venue: FTMO's own ~10-month M15 — control +0.1399 vs live-parity
  +0.0014 pooled. Same collapse on independent prices.

### The window discovery (live EA defect, now documented)
FTMO order history reconciles everything: pre-v1.27 pendings died broker-side at
+3 bars wall-clock (tickets 492683912/492702269/492759198, EXPIRED at setup+45:00
exactly); the current v1.27+ bar-count path cancels at +4 bars (ticket 493361350,
20:00:04 -> 21:00:02). **MQL5 Bars() does not count the placement bar; the v1.27
comment "placement bar = 1" is wrong. Live as-deployed fill window = i+1..i+4,
one bar LONGER than the validated 3.** Off-by-one EA fix candidate — immaterial
to the edge verdict (both windows measured; both ~0).

### Corrected census (headline cells; full tables in run logs)
| cell | n | exp | OOS exp | 2x | DSR@150 | MC both | bust | med |
|---|---|---|---|---|---|---|---|---|
| W2x3 control (documented) | 3021 | +0.1010 | — | — | — | 87.4% | 6.8% | 52d |
| W2x3 M2 live-parity w4 (as-deployed) | 2874 | **−0.0158** | +0.0100 | −0.0349 | 0.007 | **21.0%** | 60.2% | 91d |
| W2x3 M2 w3 (post-fix) | 2830 | −0.0147 | +0.0015 | −0.0435 | 0.004 | 21.0% | 59.9% | 87d |
| W3x4 control (documented) | 2022 | +0.1168 | — | — | — | 90.3% | 5.1% | 66d |
| W3x4 M2 live-parity w4 | 2358 | −0.0059 | +0.0768 | +0.0393 | 0.078 | 27.1% | 52.9% | 94d |
Reversed scan order: immaterial (±0.006 exp). Day gates bind rarely (fills/day
14–20, consec-loss 205–497 signal-drops over 2.5y). Cluster/global drops: ~1,140.

### Mechanism decomposition (the cause, proven)
- A1 (re-arm rule alone, W2 handling identical to control): +0.1010 -> −0.0022.
  The unfilled-pending re-arm non-causality IS the collapse; W2 ordering adds ~0.
- Overlap (key sym+signal bar): shared n=2454 exp +0.0610 (per-trade r identical
  100%); control-only (live cannot take) n=567 exp **+0.2740**; live-instead
  n=1210 exp −0.1596.
- **Strata (the final cut): control re-arm children n=943 exp +0.3105; control
  NON-children n=2078 exp +0.0059.** The entire validated edge lives in trades
  whose enumeration conditions on price action AFTER their own entry (a re-arm
  child exists only in the branch where the sim already knows the original
  pending stayed unfilled through bars beyond the child's fill). The
  live-realizable stratum of this strategy family is ~zero-edge at real cost.

### Recovery arms (ALL CONTAMINATED/exploratory; per-symbol w4)
| arm | n | exp | MC both | verdict |
|---|---|---|---|---|
| M2q frozen queue (Codex idea 3) | added 39 | added exp −0.18 | 20.9% | KILLED (own pre-registered conditions; n<50) |
| M2-REPLACE newest-signal-wins | 3168 | −0.0186 | 19.9% | no recovery |
| S1 post-expiry cooldown C=1/2/4 | ~3500 | −0.006/−0.004/−0.004 | 27.6–29.4% | no recovery |
| Q2 untouched expiry re-place | 3859 | −0.0106 | 25.0% | no recovery |
| L1 OCO ladder (2 or 3 rungs) | 3795 | **−0.1681** | 0.1% (bust 98.6%) | CATASTROPHIC — the both-touch conversion delta is ruinous |
| M3 mixed sleeve (Codex idea 2) | 3260 | −0.0109 | 23.8% | moot + contaminated |
M1 expiry-substitutes: n=151 exp −0.0463 — the "toxic substitutes are patchable"
hypothesis is REFUTED; the −0.16 live-instead pool is broad enumeration drift,
not a removable subclass.

### Codex idea verdicts
1. Enumeration mismatch: **correct, and the most consequential finding in this
   repo's history** (its narrow claim was the thread; the audit pulled it).
2. Mixed sleeve: moot (collapsed with everything else) + contaminated.
3. Frozen queue: killed by its own kill conditions.
4. Order recovery: 10 placement attempts since deploy, 9 accepted, 1 lost to a
   sendMarket race (retcode 10015, US30 2026-07-10 08:29) — real, minor, one-line
   retry candidate. Zero transient/broker failures otherwise.

### VERDICT (pre-registered decision rule fires)
**The corrected census fails the baseline gates catastrophically (−66 pts MC).
The validated W2/W3 edges of 2026-07-10 are OVERTURNED: they were artifacts of
non-causal pending re-arm enumeration in the harness, present in every study
built on simulate_symbol/simulate_symbol_c pending-limit entries. The
live-realizable strategy has ~zero expectancy at real cost. CHALLENGE PURCHASE
BLOCKED. No causal recovery mechanization survives even contaminated screening.
Owner decides the live EA's disposition; the resident recommends detaching it.**
Positive residue: the parity engine (golden-verified, journal-verified) is the
new gate-grade fidelity standard — nothing ships in this repo again without a
live-parity enumeration column. EA defect list for the record: 4-vs-3 pending
window; sendMarket race -> 10015; news guard ON (3 min) contradicting comment;
W2 silently passes on broken bar data; halted-day bars scanned late.

**Ledger: 146 -> 150 (four pre-registered cells) + 5 exploratory screens noted
(S1 x3, Q2, L1) -> future DSR hurdles evaluate at 155.**
