# Overnight short thesis result — 2026-07-14

## Verdict

**DISPOSED — neither fixed close-to-next-open short definition has a
provisional out-of-sample edge.**  No EA, FTMO terminal, order, or live
configuration was changed.

The protocol is
[`OVERNIGHT_SHORT_THESIS_SPEC_2026-07-14.md`](../OVERNIGHT_SHORT_THESIS_SPEC_2026-07-14.md),
SHA256 `2cf705ceb2e9c665b80088cdfb20500674e49825d2fa52005c75c017bb869607`.

## Provenance

[MEASURED: `python backtest/verify_data.py` @ `d286fe3`]

```text
verified 46 OK, 0 missing, 0 mismatched
```

[MEASURED: `python backtest/run_overnight_short_thesis.py` @ `d286fe3`]

The resulting machine-readable record is
`backtest/overnight_short_thesis_results.json`.

## Out-of-sample comparison

Net returns are basis points after the specified spread multiplier. E1 uses
the observed spread and E2 doubles it. The final 30% of each source frame is
out of sample.

| Cell | E1 pooled OOS mean | E1 n | E2 pooled OOS mean | E2 n | E2 win rate | Result |
|---|---:|---:|---:|---:|---:|---|
| CASH | -12.1481 bps | 553 | -12.8555 bps | 553 | 42.13% | FAIL |
| BROKER | +129.8216 bps | 251 | +128.9834 bps | 251 | 64.14% | FAIL |

The BROKER cell's pooled result is larger, but it is **not** a better edge:
the registered admission rule requires every symbol to have a positive E2 OOS
mean with at least 50 trades. It fails because JP225 is negative.

| Cell | JP225 E2 OOS | US100 E2 OOS | US30 E2 OOS | Admission result |
|---|---:|---:|---:|---|
| CASH | -22.0475 bps (n=189) | -9.7556 bps (n=182) | -6.4098 bps (n=182) | FAIL — all symbols negative |
| BROKER | -124.6649 bps (n=97) | +311.7256 bps (n=77) | +265.7721 bps (n=77) | FAIL — JP225 negative |

## Interpretation

[DERIVED] The requested cash-session construction loses after observed and
stressed spread on every tested symbol. The broker-midnight construction has
a positive pooled arithmetic average, but it is not a cross-symbol edge and
therefore is rejected rather than selected. It additionally omits financing,
swap, gap-risk, and stop modelling, so even a pass would not have authorised a
live implementation.

No follow-up tuning, symbol selection, or live deployment is justified from
these failed cells.
