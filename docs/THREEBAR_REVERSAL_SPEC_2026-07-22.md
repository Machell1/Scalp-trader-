# Three-bar reversal pattern — pre-registration (2026-07-22)

**Owner directive:** "lets test the 3 bar reversal pattern strategy."
**Adverse family prior disclosed:** standalone candle-pattern entries are
0-for-5 lifetime on this venue (wick rejection, pin bar, sweep-continuation,
candlestick pullback, wick pressure — all failed their gates); reversal-class
entries additionally carry the fade-direction prior (catastrophic on the
momentum tape). This is a NEW cell, not a rerun: the specific 3-bar sequence
was never mechanized here.

**Canonical mechanization (pattern at bar t, all execution-TF bars):**
BULLISH: c[t-2] < o[t-2] AND l[t-1] < l[t-2] AND c[t] > h[t-1].
BEARISH mirrored: c[t-2] > o[t-2] AND h[t-1] > h[t-2] AND c[t] < l[t-1].
Entry: market at open of t+1. Risk denominator/stop distances in ATR14 at t.

**Cells (ledger 317 -> 320):**
- **T1 (H1, house exits):** SL 1.0 ATR, bank 75% @ +1R, TP 1.5 ATR, 8-bar
  time exit (the validated exit geometry — no exit mining).
- **T2 (H1, pattern-native exits):** SL at the reversal extreme (bullish:
  l[t-1] − 0.1 ATR; capped at 1.5 ATR), TP 2.0R, 16-bar time exit, no partial.
- **T3 (M30, house exits):** T1 on M30 — informational for the frame question;
  the M30 cost prior applies.

**Frames/gates:** canonical manifest (verify first); quartet primary
(US30/US100/JP225/USDJPY via Deriv proxies) + 10-symbol holdout column; E2
double-cost currency; OOS = last 30% quarters. Stage-A kill gates per cell:
E2 full > 0 AND OOS > 0 AND >= 3/4 quartet symbols positive. Survivors
advance to the account-MC stage under a separate registration. All cells
reported.

---
## RESULTS (appended post-run 2026-07-22; protocol hashed pre-run: 87f7b6e8...)

Data gate passed. All three cells FAIL with maximal breadth — negative on all
14 symbols in every cell, full-sample AND OOS:

| cell | quartet n | expE2 | OOS | syms+ | holdout n / exp / syms+ |
|---|---|---|---|---|---|
| T1 H1 house-exits | 5,417 | -0.1248 | -0.1270 | 0/4 | 13,411 / -0.2679 / 0/10 |
| T2 H1 native-exits | 4,229 | -0.1013 | -0.0943 | 0/4 | 10,413 / -0.2257 / 0/10 |
| T3 M30 house-exits | 10,792 | -0.1541 | -0.1568 | 0/4 | 26,600 / -0.3657 / 0/10 |

**VERDICT: NO ADMISSION (0/3). Ledger 317 -> 320.** The 3-bar reversal loses
roughly a tenth to a third of R per trade at study cost on every symbol and
frame tested — among the most uniformly negative families ever screened here.
Candle-pattern standalone entries are now 0-for-8 lifetime; the
reversal/fade-direction prior is reconfirmed at n≈70k trades. Family closed.
