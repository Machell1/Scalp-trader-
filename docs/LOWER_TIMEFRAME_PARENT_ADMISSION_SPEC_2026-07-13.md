# v1.32 lower-timeframe parent-admission adapter

## Intent

The H1 v1.31 portfolio remains the default because it has the strongest current
evidence. The v1.32 change adds an optional adapter for operators who deliberately
set the EA working timeframe to M15 or M5:

* keep the existing W2 momentum-pullback entry and exits unchanged;
* admit lower-timeframe signals only when they align with an H1 parent impulse;
* reduce cash risk on those experimental lower-timeframe fills by default.

This is an execution-admission layer, not a new standalone entry family.

## Guardrails

The layer is inactive unless `InpTimeframeV131` is lower than
`InpParentTimeframeV132` and `InpUseParentTimeframeGateV132=true`. With the
default H1 timeframe, v1.32 should trade the same strategy geometry as v1.31.

The default parent gate requires the H1 close-to-close move over the existing
momentum lookback to align by at least `1.0` Wilder ATR. The optional parent
candle-alignment setting is off by default to avoid decimating sample size before
formal testing.

Lower-timeframe risk is multiplied by `InpLowerTimeframeRiskMultV132=0.50` by
default. This preserves the H1 risk profile while M15/M5 evidence is gathered.

## Required follow-up evidence

Before any claim that M15 or M5 matches H1 effectiveness, run the existing
out-of-sample and account-level gate on parent-gated M15/M5 tapes at real cost
and 2x cost stress. Report per-symbol results, pooled expectancy, trade count,
drawdown/halt impact, and whether the lower-timeframe adapter improves outcomes
versus unchanged H1 rather than just increasing turnover.
