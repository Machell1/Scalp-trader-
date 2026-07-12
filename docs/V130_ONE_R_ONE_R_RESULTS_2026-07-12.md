# v1.30 full-position 1R:1R screen — results

**Verdict: DISPOSE AS AN >80% WIN-RATE SOLUTION.**

The full-position +1R exit did not approach the registered win-rate gate.
[MEASURED: `python -u backtest/run_v130_one_r_one_r.py` @
`27a4c84cb3c8c0277590726ea4775bab036ac04d`] Its pooled stitched-OOS net win
rate was 57.4138% (666 positive trades of 1,160), versus the required strictly
greater than 80%. The idea is therefore not authorized for EA implementation
under this protocol.

The failure is specifically the high-win-rate claim, not the edge result. The
same candidate produced +0.111350R/trade stitched OOS versus +0.063534R for the
v1.30 control, a +0.047816R delta, and added 38 trades. All three symbols and
all three complete stitched-OOS quarters remained positive. These values are
promising geometry evidence but cannot be promoted post hoc after the frozen
win-rate gate failed.

## Provenance

- [MEASURED: runner output @ `27a4c84`] Protocol SHA256:
  `9a32d3f85f9107e175693f40cb5cef2b1eaf779708ff350051cf0a34ce4770f3`.
- [MEASURED: `python backtest/verify_data.py` @ `27a4c84`] `verified 46 OK, 0 missing, 0 mismatched`.
- [MEASURED: runner output @ `27a4c84`] Trial ledger `209 -> 210`; one new
  hypothesis cell.
- [MEASURED: runner output @ `27a4c84`] Confirmation/blind holdout accessed:
  false. FTMO account MC paths run: 0.
- [MEASURED: runner output @ `27a4c84`] Terminal writes, orders, EA changes,
  and terminal-setting changes: 0.

## Pooled results

| Cell/frame | n | Net win rate | Expectancy | Total R |
|---|---:|---:|---:|---:|
| v1.30 control, all | 3,757 | 40.6974% | +0.060884R | +228.742955R |
| full TP1, all | 3,897 | 57.8394% | +0.117099R | +456.333447R |
| v1.30 control, stitched OOS | 1,122 | 41.2656% | +0.063534R | +71.285329R |
| full TP1, stitched OOS | 1,160 | 57.4138% | +0.111350R | +129.166492R |
| candidate minus control, stitched OOS | +38 | +16.1482 pp | +0.047816R | +57.881164R |

Every table value is [MEASURED: `python -u backtest/run_v130_one_r_one_r.py`
@ `27a4c84`], except the displayed candidate-minus-control values, which are
[DERIVED] exact arithmetic from those measured cells.

## Candidate stitched-OOS robustness

| Slice | n | Net win rate | Expectancy | Total R |
|---|---:|---:|---:|---:|
| Wall Street 30 | 394 | 53.0457% | +0.036318R | +14.309191R |
| US Tech 100 | 386 | 60.6218% | +0.190229R | +73.428265R |
| Japan 225 | 380 | 58.6842% | +0.109024R | +41.429036R |
| 2025Q4 | 406 | 57.1429% | +0.109304R | +44.377291R |
| 2026Q1 | 388 | 56.7010% | +0.095902R | +37.209985R |
| 2026Q2 | 355 | 58.3099% | +0.126782R | +45.007641R |
| 2026Q3 partial | 11 | 63.6364% | +0.233780R | +2.571575R |

All table values are [MEASURED: `python -u backtest/run_v130_one_r_one_r.py`
@ `27a4c84`].

## Gate disposition

- [MEASURED] Pooled OOS win rate >80%: **FAIL**.
- [MEASURED] Pooled OOS expectancy >0: PASS.
- [MEASURED] Pooled OOS expectancy not below control: PASS.
- [MEASURED] Every symbol OOS expectancy >0: PASS.
- [MEASURED] Every complete OOS quarter expectancy >0: PASS.

[DERIVED] An 80% target would require at least 929 positive outcomes among
1,160 trades to be strictly above 80%; the candidate recorded 666, a shortfall
of 263. This is too large to describe as sampling noise near the threshold.

FTMO's current 2-Step objectives concern profit target and loss limits, not a
minimum trade win rate: https://ftmo.com/en/trading-objectives/ (accessed
2026-07-12). [HYPOTHESIS] The positive +0.111350R screen could improve challenge
pass probability, but that was not measured here and must not be reported as a
pass-probability result.

