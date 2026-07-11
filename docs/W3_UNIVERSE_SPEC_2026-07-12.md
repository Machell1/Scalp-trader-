# W3 configuration + universe expansion to ≥5 assets — pre-registration (2026-07-12)

**Owner directive:** adopt W3 (adverse wick ≥ 0.50, full-gate passer 2026-07-10; challenge
MC 89.5%/5.1% on the trio) on the condition the EA trades no fewer than FIVE assets.
Design logic accepted: W3 halves per-symbol frequency; a wider earned universe restores
activity at higher signal quality. Seats are earned per symbol — if the evidence-optimal
portfolio is smaller than five, the cost of forcing the fifth seat is quantified and the
owner decides with numbers.

**Candidates (10 cells; ledger 136→146).** Every symbol with gate-grade Deriv data AND an
FTMO twin, excluding crypto (commission-dead, measured):
Germany_40→GER40.cash · US_SP_500→US500.cash · XAUUSD→XAUUSD · UK_100→UK100.cash ·
France_40→FRA40.cash · Australia_200→AUS200.cash · Hong_Kong_50→HK50.cash ·
US_Small_Cap_2000→US2000.cash · XAGUSD→XAGUSD · EURUSD→EURUSD.

**Per-candidate gates:**
1. **Deriv gate-grade under W3** (wick ≥ 0.50): stitched-quarter OOS exp > 0 AND 2× cost
   OOS > 0 AND n_OOS ≥ 50 (W3 halves n; threshold pre-set accordingly).
2. **FTMO cost at W3 economics:** measured cost/side (historical spread + commission:
   indices 0, metals/FX $2.50/side/lot via tick conversion) ≤ **0.085** ATR/side
   (W3 gross ≈ 0.20 at reference cost; margin retained).
3. **FTMO direction:** W3-filtered expectancy > 0 on FTMO's own ~9-month M15.

**Portfolio construction (challenge objective, the account we actually have):**
Greedy forward selection from the W3 trio: at each step add the passer that most
improves no-time-limit both-phases MC (0.3% risk, 8k sims) without raising bust;
stop when no candidate improves. Report the full path. If the stopped portfolio has
<5 symbols, ALSO report the best forced-5 portfolio and its odds cost vs the optimum —
the owner chooses between "evidence-optimal" and "five-asset floor" with numbers.

**Ship rule:** the chosen portfolio deploys as input edits only (InpMinAdvWickAtr=0.50,
whitelist, clusters — indices grouped by session: US | EU | Asia | metals | FX), flat
account, graceful restart, init-line + panel verification, owner sign-off on the final
composition. Cluster caps stay 1 per cluster.

---
## RESULTS (appended post-run 2026-07-12; protocol hashed pre-run)

- **W3 trio baseline: 89.5% both / 5.1% bust (n=1,536).**
- Candidate verdicts: **GER40 PASS** (Deriv W3-OOS +0.106, 2× +0.085; FTMO 0.0240/side,
  +0.101 own-data) — the W2-era portfolio drag INVERTS under W3 (thinner streams stop
  the correlation stacking); **EURUSD passes per-symbol gates** (+0.118/+0.058; FTMO
  +0.090 at 0.0550/side) but DRAGS every portfolio it joins; US2000's monster Deriv
  edge (+0.255) is FTMO-cost-dead (0.1125/side); **XAUUSD is NEGATIVE under W3**
  (−0.109 — gold's wicky subset is actively bad); UK100/FRA40 fail 2×-cost or FTMO
  direction; AUS200/HK50 fail FTMO direction; XAGUSD negative.
- **Greedy construction: evidence-optimal = W3 × 4 (US30, US100, JP225, GER40) at
  89.9% both / 5.1% bust.** Forced-5 (best possible fifth = EURUSD): **84.2% / 8.3%
  — the fifth seat costs 5.7 points of funding odds and +3.2 bust.**
- Owner decision pending: evidence-optimal 4 vs five-asset floor at quantified cost.
