# Universe expansion under the W2 filter — pre-registration (2026-07-10, night)

**User ask:** "with the improved edge can we add my assets to our trading universe?"
This is the prediction from the VPOF spec finally getting its test — universe expansion
must be EARNED per symbol, not assumed from a pooled edge.

**Priors disclosed.** (1) 07-09 scan: adding GER40/JP225 to the unfiltered pair HURT
challenge odds at every matched trade cap (index correlation concentrates; lower
expectancy dilutes). W2 changes both sides of that trade-off: higher per-trade edge,
but only 3.3 trades/day — added frequency now has value it didn't have. (2) Gold: zero
edge in every prior test (t=0.28 on FTMO data; whole 2026 gold-desk history null). The
W2 filter selects a subset — it can only amplify an edge that exists in the wicky
subset; testing whether gold's wicky subset is nonzero is a NEW, narrow question.
(3) Crypto on FTMO: dead by commission arithmetic (~0.29R/round-turn vs ≤ +0.20R W2
expectancy) — no simulation needed, no cell spent. Crypto remains valid on Deriv only.

**Candidates (5 cells; ledger 110 → 115):** GER40.cash, JP225.cash, US500.cash, XAUUSD,
and XAUAUD/XAUEUR as a family rider (tested only if XAUUSD passes; no separate cells).

**Per-candidate gates (ALL required to be added to the live whitelist):**
1. **Deriv gate-grade (2.5y):** W2-filtered (adv_wick_atr ≥ 0.30 on the signal bar)
   stitched-quarter OOS expectancy > 0 at real per-instrument cost, and still > 0 at
   2× cost. (Deriv proxies: Germany_40, Japan_225, US_SP_500 from the spread-gated set;
   XAUUSD from the diverse set.)
2. **FTMO corroboration (~9 months, direction):** W2-filtered expectancy > 0 on FTMO's
   own M15 at FTMO's true cost — spread from the historical spread column plus
   commission for metals ($5/lot round turn via tick_value/tick_size conversion;
   indices commission-free).
3. **Portfolio criterion (decisive):** adding the candidate's W2-filtered FTMO-cost
   trade tape to the live pair's tape must IMPROVE the no-time-limit both-phases
   challenge probability vs the pair alone (prop MC, 0.5% risk, 4k sims). A symbol
   with positive expectancy that still drags the portfolio (correlation/dilution)
   is NOT added — same criterion that correctly excluded GER40/JP225 pre-filter.

**Ship rule.** Passers → whitelist/cluster input edit only (no recompile; cluster
assignment: EU/JP indices get their own cluster; gold its own), user sign-off, panel
verifies. No passer → the universe stays US30+US100 and the null is documented.

---
### Decision-analysis addendum (2026-07-12, pre-registered before running): near-miss recombination
No new edge claims; both analyses recombine ALREADY-GATED components with different
decision metrics (no ledger charge — decision analysis, not hypothesis testing).
- **D1 W3-vs-W2 challenge MC:** W3 (wick ≥0.50, full-gate passer, never MC'd) vs the
  live W2 on the trio tape, 0.3%, no-time-limit both-phases + bust + median days.
- **D2 funded-account objective:** day-block MC with FUNDED rules (no target; bust at
  −5% day or −10% static from initial; 252-day horizon; 0.3% risk): P(survive 1y),
  median annual P&L, median monthly P&L (×80% = withdrawal estimate) for (a) live trio,
  (b) trio+GER40 (its gated W2 config at real cost), (c) trio+GER40+EURUSD.
  Motivation: GER40/EURUSD failed the CHALLENGE-portfolio criterion specifically;
  the funded objective differs (income/survival vs pass-sprint). Decision rule: an
  addition must raise median monthly P&L WITHOUT raising 1-year breach probability.
  Any adoption would apply ONLY to the post-funding config, with owner sign-off.

**D1/D2 RESULTS (2026-07-12):**
- **D1: W3 beats W2 on challenge odds — a real, gated option.** W3 (wick≥0.50): both-phases
  89.5% / bust 5.1% / median 82 days vs W2's 87.4% / 6.8% / 52 days. Half the trades,
  +2.1 pts odds, −1.7 pts bust, +30 days patience. Both cells passed the identical full
  gate on 2026-07-10; this is a config choice (input-only), owner's call.
- **D2: trio+GER40 FAILS the pre-registered funded rule.** Median monthly +3.32% vs
  +2.73% (≈$2,657 vs $2,184/mo withdrawal @$100k, 80% split) and annual +40.3% vs
  +33.6% — but 1-year survival drops 93.2%→90.6%, violating "without raising breach
  probability." NOT adopted. Legitimate future cell (post-funding, new pre-registration):
  GER40 at REDUCED allocation — not run tonight per the no-post-hoc-flip rule.
  EURUSD: skipped honestly (no spread-gated CSV; diverse file lacks real spread).
