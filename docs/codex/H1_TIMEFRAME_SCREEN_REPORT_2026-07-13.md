# H1 timeframe screen

## Verdict

**SURVIVES SCREEN — proceed to a separately preregistered FTMO account MC.**
This is not yet evidence of an 88% account pass rate.

[MEASURED: `python backtest/verify_data.py` @ commit `3e4d706`]

```text
verified 46 OK, 0 missing, 0 mismatched
```

[MEASURED: `python -u backtest/run_h1_timeframe_screen.py` @ commit `3e4d706`]

The test aggregated complete contiguous groups of four frozen M15 bars into
UTC H1 bars, using first open, last close, extrema, summed volume, and maximum
source spread. It then applied unchanged W2 momentum-pullback geometry and v1.30
exits: 1ATR stop, 50% bank at +1R, TP2, and eight-bar hold.

| Symbol | H1 bars | Full N | Full exp | Full win | OOS N | OOS exp | OOS win |
|---|---:|---:|---:|---:|---:|---:|---:|
| Wall Street 30 | 14,383 | 322 | +0.204560R | 50.621% | 115 | +0.222844R | 53.913% |
| US Tech 100 | 14,383 | 287 | +0.139431R | 42.857% | 78 | +0.259497R | 47.436% |
| Japan 225 | 14,440 | 254 | +0.094726R | 46.063% | 87 | +0.142487R | 47.126% |
| **Pooled** | — | **863** | **+0.150574R** | **46.698%** | **280** | **+0.208086R** | **50.000%** |

At 2x cost the same H1 cell remained positive: [MEASURED: same command @
`3e4d706`] Wall Street 30 OOS `+0.207740R`, US Tech 100 `+0.248147R`, Japan
225 `+0.108878R`, pooled `+0.188278R`, with pooled OOS win rate `50.000%`.

The H1 candidate therefore clears the preregistered expectancy screen: pooled
OOS positive, every symbol OOS positive, and pooled stress OOS positive. The
next required test is an H1-specific account tape and 100,000-path sequential
FTMO Challenge/Verification simulation. No live EA change is authorized before
that result and forward validation.
