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
