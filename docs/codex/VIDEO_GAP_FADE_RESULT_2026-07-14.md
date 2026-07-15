# Video-inspired cash-session gap-fade result — 2026-07-14

## Verdict

**DISPOSED.** The one fixed, video-inspired index translation failed every
out-of-sample admission requirement under both observed and doubled spread.
This is not a reproduction of the supplied video's undisclosed strategy.

Protocol: [`VIDEO_GAP_FADE_SPEC_2026-07-14.md`](../VIDEO_GAP_FADE_SPEC_2026-07-14.md)
(`8f5acbfc8cf7d216bb16e4150184d33bab9a26e918559ada842960f5cad8901e`).

## Provenance

[MEASURED: `python backtest/verify_data.py` @ `de8407a`]

```text
verified 46 OK, 0 missing, 0 mismatched
```

[MEASURED: `python backtest/run_video_gap_fade.py` @ `de8407a`]

The exact machine-readable results are in `backtest/video_gap_fade_results.json`.

## Results

| Cost cell | Pooled OOS n | Mean net bps | Win rate | Total net bps | Gate |
|---|---:|---:|---:|---:|---|
| E1 observed spread | 156 | -4.3546 | 46.15% | -679.32 | FAIL |
| E2 doubled spread | 156 | -4.9094 | 46.15% | -765.87 | FAIL |

| Symbol | E2 OOS n | E2 mean net bps | E2 win rate |
|---|---:|---:|---:|
| JP225.cash | 75 | -6.8396 | 44.00% |
| US100.cash | 49 | -4.8711 | 46.94% |
| US30.cash | 32 | -0.4443 | 50.00% |

[DERIVED] The candidate fails on direction (negative E2 pooled return), every
symbol's E2 return, the 25-trades-per-symbol requirement for US30, and the
300-trade pooled requirement. It is not a strategy to install, tune, or
transfer to FTMO. No EA code, terminal state, order, or configuration changed.
