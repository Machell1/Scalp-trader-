# Arena tournament #1 — 2026-07-05

Four AI models each independently developed one improvement candidate for the
DerivScalper strategy (iterating only on the DEV split, first 70% of bars),
then competed on the hidden HOLDOUT split (last 30%). The winner faced the
reigning champion — the live **v1.23 pure bracket** config — in a title match.

- Data: Yahoo proxy (yahooM15 60d + yahooH1 730d), 11 crypto/index majors
  (the Yahoo analog of the Deriv spread-gated universe). Cost 0.02 ATR/side
  real, 0.04 stress. **Screening-grade only** per `HANDOFF.md`.
- Every candidate ran through the same trusted simulator
  (`backtest/scalper_confluence.py`); guardrails (pullback LIMIT entry,
  TP ≥ 3.0 ATR, no AVWAP, bounded knobs) enforced at load.

## Holdout leaderboard

| Rank | Candidate | Model | Change vs champion | N | exp@.02 | exp@.04 | M15 | H1 |
|---|---|---|---|---|---|---|---|---|
| — | CHAMPION: v1.23 pure bracket | human+validated | — | 2447 | −0.0101 | −0.0501 | −0.0415 | −0.0019 |
| 1 | **patient pullback, unhurried exit** | **claude-opus-4-8-thinking-high** | pend 3→4, hold 8→12 | 2412 | **+0.0517** | **+0.0117** | +0.0342 | +0.0563 |
| 2 | pullback patience +1 bar | composer-2.5 | pend 3→4 | 2492 | +0.0192 | −0.0208 | +0.0340 | +0.0154 |
| 3 | moderate bracket hold14 | gpt-5.5-high | hold 8→14 | 2334 | +0.0171 | −0.0229 | −0.0689 | +0.0400 |
| 4 | pure bracket hold10 | gpt-5.3-codex-high | hold 8→10 | 2399 | −0.0009 | −0.0409 | −0.0368 | +0.0086 |

Notable: all four models independently converged on "the strategy quits the
setup too early" (entry patience and/or exit patience) — no one bet on a new
filter, consistent with the repo's history (0/19 bolt-on filters ever shipped).
The winner combined *both* patience axes and was the only candidate positive
at 2× cost on the holdout.

## Title match — challenger vs champion (holdout)

All 5 gates passed:

| Gate | Result |
|---|---|
| Marginal OOS expectancy > champion | PASS (d = +0.0618 R) |
| No 2×-cost regression | PASS (d2x = +0.0618; challenger +0.0117 vs champion −0.0501) |
| Consistent across both datasets (within noise) | PASS (M15 +0.0757, H1 +0.0582) |
| Sample floor N ≥ max(150, 50% champion) | PASS (2412 vs 2447) |
| Monthly sign stability (H1 holdout) | PASS (83% of 12 months positive) |

Paired per-signal delta on common entries (87% overlap, N = 2107):
**+0.0241 R/signal, t +1.71**.

**PROMOTED.** `champion.json` now holds *patient pullback, unhurried exit*
(pending_expiry_bars 4, max_hold_bars 12; everything else unchanged from
v1.23). The old champion is archived in its `history`.

## Honest caveats

1. **Proxy data.** Yahoo bars, modelled flat cost, no live-spread column. Per
   `HANDOFF.md` this is screening, not validation — the promotion is *staged*.
   The EA defaults (`InpPendingExpiryBars`, `InpMaxHoldingBars`) must NOT
   change until the new config clears the real-Deriv M15 walk-forward + DSR
   gate (`backtest/walkforward_dsr.py`, MT5 required).
2. **Statistical strength.** The winner's holdout t is +1.60 pooled / +1.71
   paired — directionally strong, not conclusive alone. It is, however,
   consistent with prior *real-Deriv* evidence: RESULTS.md §7 already
   pre-registered "promote hold 8→16 after live bracket trades track the
   backtest," and fill-realism day-1 data showed live fills beat the 3-bar
   modeled expiry. The arena result independently re-derived both directions.
3. **Search intensity.** Models self-reported 6–40 dev configurations each
   (~67 total across contestants). The holdout was never exposed to
   contestants, but with 4 finalists the winner's holdout edge carries a mild
   selection effect (best of 4).

## Next step to make it real

Run on a machine with the MT5 terminal:

```bash
cd backtest
python fetch_spreadgated.py     # refresh the 12 spread-gated majors
python walkforward_dsr.py       # champion (pend3/hold8) baseline
# then re-run with pending_expiry_bars=4, max_hold_bars=12 and compare
```

If the staged config clears the same SHIP gates there, bump the EA defaults
(v1.25) and update `HANDOFF.md`.
