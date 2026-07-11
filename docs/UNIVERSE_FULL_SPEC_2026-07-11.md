# Full-universe W2 sweep — pre-registration (2026-07-11, post-RAM-upgrade)

**User ask:** "why not test the entire universe" (RAM upgraded 3.9→11.9 GB).
**Honest constraints stated up front:** FTMO history ≈ 9 months → FTMO-side results are
directional screens, not gate-grade; confirmation requires the Deriv 2.5y frame, which
exists only for symbols Deriv also lists. This sweep is EXPLORATORY by design; only
cross-frame hits consume confirmatory trial-ledger cells (ledger currently 115).

**Part A — cost, every FTMO symbol (~167).** Measured per-side cost in ATR units =
0.5·median(historical spread)/median(ATR-M15) + commission: indices/cash 0; crypto
3.25 bps of notional per side (empirically measured on live BTC fills 2026-07-10);
FX/metals/energies $2.50/side/lot via tick_value/tick_size. **New W2-economics cost
ceiling, derived before results: 0.075 ATR/side** (W2 pooled gross ≈ +0.18R at zero
cost; 2×0.075 = 0.15 leaves margin; old 0.05 gate was calibrated to the unfiltered
+0.05R edge). Symbols with <3,000 M15 bars are reported as data-starved, not tested.

**Part B — FTMO W2 screen.** Cost passers → live engine (M15, mom 6/2.0, pullback-limit
0.6, SL1/TP3/hold8, Wilder ATR) + W2 filter (adverse wick ≥ 0.30 ATR) on the full ~9-month
window at each symbol's measured cost. Screen hit: expectancy > 0 with n ≥ 100.

**Part C — Deriv confirmation frame.** All 41 cached Deriv datasets (12 spread-gated with
real spread costs + 29 diverse at flat 0.03): W2 stitched-quarter OOS (last 30% of
quarters) plus 2× cost. Gate-grade pass: OOS > 0 AND 2× cost > 0 AND n_OOS ≥ 60.

**Part D — confirmatory battery (ledger-charged), only for symbols that hit in BOTH
B and C and are FTMO-tradable and not already live:** portfolio MC vs the live trio
(US30+US100+JP225 W2 tape, 0.5% risk, no-time-limit both-phases, 10k sims) must IMPROVE.
Passers → proposed whitelist adds (user sign-off). Everything else → knowledge table:
"edge exists, venue lacks it," "cost-dead," "data-starved," or "no edge."

**Market-Watch hygiene:** symbols selected for pulls are deselected afterward (keep the
live terminal lean); the live EA/whitelist is untouched throughout the sweep.
