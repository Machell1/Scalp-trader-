# M30 execution / H4 anchor — pre-registration (2026-07-21)

**Owner directive:** "i want it on the 30M time frame instead use the 4H as the
anchor time frame." Mechanized with the house's anchor framing: the signal
lives at ANCHOR scale, execution at the finer clock. Deployment happens ONLY
for a gate-passer (the H1 book v1.33-C1r3 stays live until then); if all cells
fail, the numbers go to the owner with the live book unchanged.

**Dead-cell priors disclosed (not re-run):** native lower-TF ports of this
geometry are a documented dead end (M15 live-parity ≈ 0 at real cost; cost per
side is measured against the EXECUTION-ATR, which shrinks faster than spread);
confirmation filters on this signal failed 4× incl. an H4-EMA-slope gate
(IMPROVE-100 F-family); the SLIDING anchor (signal re-evaluated every lower-TF
close) failed its phase-offset and holdout gates (MTF_ANCHOR_SPEC). The new,
untested construction is the GRID-ALIGNED higher anchor: H4-scale signal with
sub-bar execution. Its cost math is FAVORABLE vs H1 (same spread ÷ ~1.9×
larger ATR).

**Cells (ledger 303 → 306):**
- **V0 — native M30 book (attribution control):** the C1 geometry ported
  verbatim to M30 bars (6-bar ≥2.0 ATR(M30) impulse + candle direction, W2 0.30
  on the M30 signal bar, pullback limit 0.6×ATR(M30), rest window 4 M30 bars,
  SL 1.0 / bank 75% @ +1R / TP 1.5 ATR(M30), hold 8 M30 bars). Cost/side vs
  ATR(M30). Prior: dead (M15 precedent) — measured for attribution.
- **V1 — V0 + H4 direction gate:** V0 entries only when sign(H4 close −
  H4 close[6]) matches trade side, using the last CLOSED H4 bar. Prior:
  filters don't rescue (F-family) — measured for attribution.
- **V2 — H4 anchor, M30 execution (the owner's construction, primary):**
  signal evaluated on the H4 grid only (6 H4 bars ≥ 2.0 ATR(H4) + candle
  direction + W2 0.30 on the H4 signal bar; identical thresholds, H4 units).
  Entry = pullback limit at H4close − 0.6×ATR(H4)×side, resting 4 H4 bars =
  32 M30 bars, FILLS CHECKED ON M30 BARS; bracket SL 1.0 / partial 75% @ +1R /
  TP 1.5 in ATR(H4) units, MANAGED ON M30 BARS (pessimistic SL-first per M30
  bar); time exit at 8 H4 bars = 64 M30 bars from fill. One position per
  symbol; cooldown = exit M30 bar. Cost/side vs ATR(H4).

**Frame/control:** canonical 46-CSV manifest only (verify_data first); M15
resampled to M30/H4 (right-closed OHLC aggregation, epoch-aligned). Universe =
the live quartet (Wall_Street_30, US_Tech_100, Japan_225, USDJPY at its 0.05%
sleeve risk; trio 0.30%). Control = the deployed C1-H1 tape (audited builder,
head-to-head kwargs). Paired account MC on common bootstrap frames: seed
13020260711, 20-day blocks, 20k screen; 100k confirmation for any passer.

**Gates (era standard, verbatim):** hard-halt ≤ 0.003700; conservative
one-sided paired lower bound (candidate − C1) > 0. Report regardless: n/fills,
E2 expectancy, OOS split, both-phases, timeout, median days. Tape-level
sanity: per-symbol OOS signs, 2× cost column.

**Prior stated:** V0/V1 expected dead. V2 genuinely uncertain: ~4× fewer
signals than H1 (timeout risk worsens) vs better cost ratio and finer fills;
the paired-lower-vs-C1 gate decides. An EA build (v1.34 MTF) happens only
after a pass + owner sign-off on the final config echo.

*Results appended below the hash after runs.*

---
## RESULTS (appended post-run 2026-07-21; protocol hashed pre-run: 761329a6...)

Data gate: `verified 46 OK, 0 missing, 0 mismatched`. Control C1-H1 rebuilt
via the audited builder. Paired 20k MCs, era gates.

| cell | n trades | expE2 | OOS | both-phases | hard-halt (gate ≤0.37%) | verdict |
|---|---|---|---|---|---|---|
| control C1-H1 | 987 fills | +0.10-class | — | 87.3–90.3% (per-frame) | 0.08–0.67% | deployed |
| V0 native M30 | ~1.9k | negative | negative | 74.08% | **9.32%** | **FAIL** |
| V1 + H4 gate | 1,462 | −0.0503 | −0.0631 | 58.93% | **28.51%** | **FAIL** (filter made it worse — 5th confirmation) |
| V2 H4-anchor/M30-exec | 271 | −0.0759 | +0.0477 (n=112, noise) | **0.005%** | **87.11%** | **FAIL** (thin negative-drift tape → trailing-DD death) |

**VERDICT: NO ADMISSION (0/3). The live v1.33-C1r3 H1 book stays.** The M30
execution frame is dead at its own cost math exactly like M15 before it; the
H4 direction gate degrades further (confirmation-filter finding, now 5×); and
the H4-anchored/M30-executed construction produces ~4× fewer signals whose
quality does not survive — negative expectancy at E2 plus multi-day holds
turn the account MC into near-certain trailing-DD death (n10=0 of 18,056
discordant paths vs control). Paired lower bounds: −0.14 / −0.31 / −0.91.
Ledger 303 → 306. H1 remains the only timeframe that has ever survived the
gates on this signal family (H1_TIMEFRAME_SCREEN); M30-native, M30+H4-gate,
and H4-anchor/M30-exec join M15-native and the sliding anchor on the dead
list. Any future timeframe change starts from a NEW signal family, not this
geometry.
