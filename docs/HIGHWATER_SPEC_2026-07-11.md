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

---
## RESULTS (appended post-run 2026-07-11; protocol hashed pre-run)

| T (lock arm) | paired Δexp (95% lo) | MC both | full-stop rate | quarters+ | verdict |
|---|---|---|---|---|---|
| 1.0R | −0.0378 (−0.0714) | 84.6% | 55.7→50.2% | 0/4 | no |
| 1.5R | −0.0227 (−0.0464) | 86.3% | 55.7→53.5% | 1/4 | no |
| 2.0R | −0.0107 (−0.0267) | 86.2% | 55.7→54.8% | 1/4 | no |
| 2.5R | −0.0041 (−0.0107) | 87.3% | unchanged | 2/4 | no (converges to baseline) |

Baseline: exp +0.1010, MC 87.4%/6.8%. **Monotone verdict: the more the lock can act,
the more it costs.** The full-stop rate DOES fall (the mechanism works — stops become
scratches) but expectancy pays more than the insurance is worth: trades that reach
+1..+2.5R and pull back to entry RECOVER often enough that protecting them destroys
value. Even 0.5R from target the lock is a hair negative. The resident's geometric
intuition ("little left to win, everything to give back") is empirically wrong on this
engine — the give-back risk is the price of the 3R tail, and the market pays for
enduring it.

**THE EXIT BOOK IS CLOSED.** Pure bracket SL1/TP3/hold8 is now undefeated across the
entire tested exit space: low-trigger locks, ladders, trails, partial scale-outs,
conditional holds, TP ratchets/variants, the 576-cell WFO sweep, and the high-water
corner (0-for-11 lifetime for exit modifications). Do not reopen without fundamentally
new evidence. Ledger 136.
