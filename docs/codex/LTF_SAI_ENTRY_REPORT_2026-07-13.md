# v1.32 Structural Absolute Impulse — report (2026-07-13)

## Verdict

**Exploratory promote of the SAI entry mechanism.** H1 live defaults are unchanged
(SAI is a no-op when work TF == risk TF). M15/M5 become usable by preserving
H1 ATR economics instead of copying bar counts. Not a gate-grade SHIP — Yahoo
proxy only; re-run on Deriv before treating LTF as production.

## What was wrong with native M15/M5

The H1 book works because a 6-bar / 2 ATR impulse is a **6-hour structural move**
with stops sized to H1 ATR (cheap vs spread). The same bar counts on M15/M5
measure 90/30 minutes of noise and shrink ATR so cost/R explodes. That is why
H1 OOS on the core book is about +0.12R while native M15/M5 go deeply negative.

## Creative fix (edge preserved)

Keep the validated levers: pullback LIMIT, W2 contested wick, v1.30 bank 50%@1R
/ TP2 / 8-bar hold (wall-clock scaled). Change only the *ruler*:

1. Lookback = 6 × (H1 seconds / work-TF seconds) → 24 on M15, 72 on M5
2. Impulse threshold = 2.0 × **H1 Wilder ATR** in price (absolute impulse)
3. Stop / TP / pullback / wick all in H1 ATR
4. LTF pullback deepened to **0.8 ATR** (plateau on the proxy grid)
5. M5: impulse evaluated on **M15 parent closes**; fills/management on M5

## Proxy evidence (Yahoo + FTMO cost fractions)

Chosen cell `m=2.0 pb=0.8 w=0.30`: E1 OOS **+0.120R** (n=41, 5/10 symbols),
E2 OOS **+0.038R**, core OOS **+0.261R**. Native M15/M5 and wall-clock-only
scaling remain negative. See `docs/LTF_HYBRID_ENTRY_SPEC_2026-07-13.md`.

## Universe

Live whitelist unchanged. Optional Stage-A extras (`FRA40.cash`, `XAUUSD`) at
0.05% sleeve remain **OFF** (`InpAdmitStageAExtrasV132=false`) — they passed
per-symbol H1 Stage A but failed full-risk account gates.

## Operator use

- Leave `InpTimeframeV131=PERIOD_H1` for the live book (behavior unchanged).
- For M15: set `InpTimeframeV131=PERIOD_M15` (SAI activates automatically).
- For M5: set `InpTimeframeV131=PERIOD_M5` (parent-M15 signal / M5 fill).
- Compile in MetaEditor; chart-saved inputs persist by name — new v1.32 inputs
  pick up defaults on first load.
