# Corrected-engine re-derivation program — pre-registration (2026-07-12, night)

**Owner directive (verbatim intent):** every idea previously killed in COMPARATIVE
tests was judged against the contaminated (+0.101 hindsight) baseline — those
verdicts are void in both directions. Recall and retest them on the corrected
live-parity engine, plus harvest new mechanizable ideas from trading communities.

**Scope of voiding (honest taxonomy):**
- VOID (re-testable): all comparative results on the momentum-pullback tape —
  the 11-0 exit book (locks/trails/scale-outs/TP/hold variants), W1/W2/W3/K
  threshold selection, entry-style superiority (pullback-limit vs market/stop —
  market entries were NEVER contaminated), direction (cont vs fade), supervisory
  sizing arms, volatility-sync arms, confluence gates, entropy sizing, universe
  and portfolio selections.
- STANDING (not re-tested without new data): standalone signal-information
  nulls — SMC concepts, VPOF level informativeness (S1.5 kill), crypto
  microstructure ICs, Golden-Asia zone stat, liquidation-sweep, cross-sectional
  RV, candle strategies THAT failed at signal level (re-screened cheaply anyway
  where cost ≈ 0).

**Engine:** `backtest/parity_engine.py` primitives (golden- and journal-verified)
+ a general bracket resolver mirroring simulate_symbol's management semantics
(SL-before-TP intrabar, end-of-bar lock/trail, time exit), extended with partial
scale-out. Live enumeration: pre-entry filter, pending occupancy, window=4,
re-arm at i+window, cooldown exit_bar+1. Per-symbol frames (trio, real Deriv
cost) for the screen; portfolio coupling + FTMO corroboration only for
promotions.

**Design: staged screen, honestly labeled.**
- Stage 1 (axis sweeps from the corrected base config): filters {none, W2 .30,
  W3 .50, K3 clean-climax-drop}; direction {cont, fade}; entry {limit-pullback
  0.6, market, stop-breakout 0.05}; TP {1.5, 2, 2.5, 3, 4}; hold {4, 8, 12, 16,
  24}; SL {0.75, 1.0, 1.5}; lock {0.5, 1, 1.5, 2}R (buffer 0); lock+trail pairs
  {(0.5,1.5),(1,1),(1,2)}; scale-out {50%@1.5R, 50%@2R, 33%@1R}. ~35 cells.
- Stage 2: combinations of any Stage-1 axis winners (OOS exp > +0.03 at real
  cost) + harvested-idea screens (workflow wf_910ad55a).
- Promotion rule (unchanged house law): nothing ships without the full gate at
  the incremented ledger + owner sign-off + forward validation; the corrected
  engine's own discovery data is CONTAMINATED for anything derived from the
  collapse decomposition — the forward test is the decision frame for those.

**Multiplicity honesty:** this is an exploratory SCREEN batch (like the crypto
kill-screen precedent): noted at the ledger as a batch (155 -> 155+screens
noted); confirmatory charges begin at promotion. Every cell is reported,
including — especially — the failures. Expectation stated up front: the
corrected base is ~0.00R; a fundable variant must find +0.05..0.10R OOS with
controls, a materially higher bar than "improve +0.101". The prior is thin;
the hunt is honest.

*Results appended below after runs; protocol frozen at hash time.*

---
## RESULTS (appended post-run 2026-07-12/13 night; protocol hashed pre-run:
SHA256 e7df76dfd077a1672abac3829505b5ba76b678204f036c241503986a1f7dc7a5)

**Consistency anchor:** Stage-1 BASE reproduces the parity census exactly
(n=3664, exp −0.0119) — third independent implementation of live enumeration.

### Stage 1 (30 axis cells, corrected engine, trio, real cost) — what flipped
- **THE EXIT BOOK VERDICT REVERSES.** On the honest tape: TP1.5 exp +0.0360
  (win 44.3%, MC 69.6%) vs bracket-TP3 −0.0119; owner's scale-out 33%@1R
  +0.0304 full / **+0.0419 OOS** (MC 64.8%); holds 12–16 mildly positive.
  The 11-0 "bracket undefeated" record was a hindsight-tape artifact — the
  +0.31R re-arm riders that made TP3 look unbeatable never existed live.
- Still negative on the honest engine (verdicts STAND, not baseline artifacts):
  all breakeven locks (−0.016..−0.030) and lock+trail pairs; fade direction
  (−0.07..−0.11, bust 87–89%); SL 0.75/1.5 no help.
- Filters on corrected tape: W2 ≈ K3 ≈ weakly helpful vs none; W3 best OOS.
- Market/stop entries (never pending-contaminated): OOS +0.067/+0.081 but
  IS-negative — unstable, not promoted alone.

### Stage 2 (19 combo cells) — finalists (OOS>0 at 2× cost AND 3/3 symbols)
| cell | exp | OOS | OOS@2× | MC both/bust | per-symbol OOS |
|---|---|---|---|---|---|
| **TP1.5 + so33@1R** | +0.0631 | +0.0529 | **+0.0109** | **93.0%/3.5%** | +.009/+.087/+.064 |
| **so50@1R TP2.0** | +0.0609 | +0.0635 | **+0.0216** | **93.6%/2.9%** | +.013/+.133/+.046 |
| so33@1R hold12 | +0.0397 | +0.0545 | +0.0125 | 67.9%/19.0% | 3/3 + |
| so33@1R TP2.0 | +0.0420 | +0.0482 | +0.0063 | 79.6%/10.8% | 3/3 + |

### Gate columns on finalists
- OOS quarters: **4/4 positive, all four cells.**
- FTMO second venue (~10mo, own bars/costs): pooled **+0.0526 / +0.0521**
  (top two); all four positive pooled.
- **DSR at the honest trial count (204 incl. tonight's 49 screen cells):
  0.139 / 0.226 / 0.082 / 0.088 — ALL FAIL 0.95.** After a 50-cell mining
  night, retrospective statistics cannot separate these from best-of-N luck.

### Cross-symbol HOLDOUT (prediction registered pre-run; 10 never-mined symbols)
- **The geometry DELTA replicates: +0.1046 / +0.0966 vs holdout-BASE, improving
  10/10 symbols.** First out-of-mining-sample replication in program history.
- Absolute level after the lift is symbol-dependent: holdout pool ≈ breakeven
  (+0.0113/+0.0032); strong members GER40 +0.078, XAUUSD +0.053, SP500 +0.038.
  The trio (+ GER40) remains the best base set on the CORRECTED ranking too.

### VERDICT
1. **Owner vindication, precisely scoped:** the scale-out family (his idea,
   previously killed against the fake baseline) + tighter targets is a REAL
   structural improvement (+0.10R/trade, replicated out-of-mining on 10/10
   symbols, both venues). The locks/trails and fade remain honestly dead.
2. **No retrospective ship.** DSR fails at the honest trial count and the
   discovery data is contaminated. **The decision-grade frame is FORWARD:**
   a v1.30 EA (partial-close module + TP cap; needs code, not just inputs),
   owner sign-off, on the free demo — the forward test that was going to
   validate a dead config now has something real to validate.
3. Candidate for owner choice (one, to stop selecting): **so50@1R TP2.0**
   (recommended: 2× cost margin +0.0216 = double the alternative's, best DSR,
   best MC) vs TP1.5+so33@1R (higher holdout delta/absolute). Face-value MC
   ~93%/3% carries the mining discount — treat as upper bound until forward.
4. Ledger: 155 + 54 retest screens (30+19+4 gate+1 holdout) noted → future
   retrospective DSR hurdles at ~209. Confirmatory charges begin at promotion.
5. Internet harvest (wf_910ad55a) results append separately when complete.

### Harvest + fill-realism addendum (2026-07-13, same night)
- Harvest delivered 57 raw -> 12 distilled ideas (docs/HARVEST_2026-07-13.md).
  **Idea #1 (trade-through limit fills; MQL5 live data: 59% of touched-but-not-
  crossed limits never fill) was actioned immediately** as a robustness column
  (backtest/retest_fillrealism.py + inline asymmetric variant):
  - Symmetric buffer stress: buf 0.02×ATR -> finalists +0.025; 0.05 -> negative.
  - **Venue-correct asymmetric rule** (bid bars: BUY-side limits — long entries,
    short TP/SO — need full-spread trade-through; sell-side fill at bid touch):
    **TP1.5+so33@1R +0.0288 / MC 67.1%/18.2%; so50@1R TP2.0 +0.0270 / 66.1%/17.6%;
    base −0.0310 / 14.0%.** The geometry delta (~+0.06) survives; the honest
    planning numbers are MC ≈ 66%, not the touch-fill 93% (upper bound).
- Queued for pre-registered screening next session (priority order): Alvarez
  entry-geometry A/B under real fills; Raschke first-touch/ADX>30 gate; JFE
  first/last-half-hour intraday momentum; uncapped stop-and-reverse exit;
  bar-close stop evaluation; bracket grid remainder. Ledger charges at their
  specs.
