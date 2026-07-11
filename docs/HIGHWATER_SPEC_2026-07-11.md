# High-water breakeven lock — pre-registration (2026-07-11, night; resident's own input)

**Hypothesis (mine):** locking the stop to breakeven ONLY after the trade reaches a HIGH
water mark (≥1.0–2.5R) removes full round-trip losses (+1.1R → −1R, observed live
2026-07-10 on US100) at bounded truncation cost, because a trade near target has little
room left to win and everything to give back. Distinct from the dead ladder family:
the 07-02 study locked at ~0.25R — strangling the 3R tail early; the high-water region
was never isolated. Honest framing: the target metric is the FULL-LOSS rate and MC odds
with expectancy non-inferiority — not raw "win rate," which closer TPs game (rejected).

**Mechanization (engine-native, zero new code paths):** `scalper_backtest.simulate_symbol`
with `lock_trigger_atr = T`, `trail_atr = 999` (pure BE-lock, no trail) — lock evaluated
at BAR CLOSE (close ≥ entry + T×ATR), matching the live EA's bar-close management
exactly (P0-parity semantics). Entries identical to live (W2 trio, real costs) → trades
pair 1:1 with baseline by signal bar.

**Cells (4; ledger 132→136):** T ∈ {1.0, 1.5, 2.0, 2.5} R.

**Gates (ALL required):**
1. **Edge non-inferiority (the user's constraint):** paired per-trade expectancy delta
   vs baseline ≥ −0.005R with the 95% CI lower bound > −0.02R, on stitched OOS quarters.
2. Challenge MC (no-time-limit both-phases, 0.3%, 8k sims) ≥ flat baseline; bust ≤.
3. Full-stop rate (r ≤ −0.9R) reduced by ≥2 points OOS (the actual objective).
4. Quarters: paired delta ≥ 0 in ≥60% of OOS quarters; no per-symbol OOS sign flip
   of the delta.
**Report regardless:** win rate, TP rate, scratch rate, avg win/loss, MFE-conditional
table P(outcome | reached T) — the mechanism must be visible, not just the net.

**Prior disclosed:** exit modifications are 0-for-7 lifetime; low-trigger locks cut avg
win 1.72→1.02R. The high-water variant survives only if P(TP | reached T) is high and
reverse-recover is rare. If all 4 cells fail, the bracket's dominance extends to the
last untested corner of the exit space and the exit book CLOSES.

**Ship rule:** a passing cell → v1.30 `InpUseLockTrail` variant (the ladder inputs
already exist in the EA: lock trigger + buffer, trail off), flag-gated, shadow-first,
owner sign-off. Otherwise: documented null, exits remain pure bracket.
