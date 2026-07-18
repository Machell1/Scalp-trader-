# US100 M1 cash-open fair-price reversion — result

## Data provenance

- [MEASURED: `python backtest/freeze_video_m1_us100.py --verify` @ `efd42c4`]
  `verified video M1 freeze 4 OK, 0 missing, 0 mismatched, 0 extra`
- [MEASURED: `python backtest/freeze_video_m1_us100.py` @ `efd42c4`]
  frozen `US100.cash`: 98,807 M1 bars, `2026-03-31T18:43:00Z` through
  `2026-07-10T23:49:00Z`.
- [MEASURED] Strategy protocol SHA256:
  `6413ac7c63ea2f629951ba43c7edb1419bf913a2ac4981b59ea6c219f037b872`.

## Registered cell result

[MEASURED: `python backtest/run_video_m1_open_reversion.py` @ `a7c01e0`]

| Measure | Result |
|---|---:|
| Complete weekday sessions | 74 |
| Incomplete sessions | 1 |
| No qualifying cash-open impulse | 48 |
| Failed consolidation gate | 24 |
| Failed fair-price-at-least-3R gate | 1 |
| Structure-break candidates | 0 |
| Trades | 0 |
| Win rate | N/A |
| Mean / median R | N/A / N/A |
| First 60% / final 40% trades | 0 / 0 |

The machine-readable result contains all 74 complete session dates and the
empty trade ledger: `backtest/video_m1_open_reversion_20260713.json`.

## Verdict

**DISPOSED — no executable trades.** [DERIVED] This one fixed 3R mechanical
translation cannot improve the current EA or substantiate an FTMO pass-rate
claim. It will not be retuned, broadened, or deployed from this result.

## Non-outcome infrastructure failure

The first synthetic import check was invoked outside `backtest` and failed
before any frozen data was read:

```text
ModuleNotFoundError: No module named 'freeze_video_m1_us100'
```

[MEASURED: `Set-Location backtest; python -c "import run_video_m1_open_reversion ..." @ `a7c01e0`]
The registered import-path check then printed `registered runner non-outcome
checks OK`; this did not execute the strategy.
