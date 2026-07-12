# High-ADX first-touch EMA20 entry with 3R target — results

**Verdict: DISPOSE.** [MEASURED: registered runner @
`2c717850e1d2871282cc42972b4cdd1dba144d09`] The materially different entry
produced +0.015177R OOS with 318 trades, but win rate was 37.4214%, not >80%.
US Tech and Wall Street were negative; 2026Q1 and 2026Q2 were negative.

[MEASURED] Protocol SHA256 `2a087311596fcc04442c45e8d4f89065b7497c4b0b057493ce9c3d07f26c29e9`;
canonical verification 46/46; regression 9/9; synthetic tests 7/7; ledger
216 -> 217; terminal writes, blind access and FTMO MC all zero.

| Cell/frame | n | Win | Exp | Total R |
|---|---:|---:|---:|---:|
| H1 all | 945 | 35.7672% | +0.001780R | +1.682194R |
| H1 stitched OOS | 318 | 37.4214% | +0.015177R | +4.826299R |
| Wall Street OOS | 103 | 32.0388% | −0.058058R | −5.979926R |
| US Tech OOS | 107 | 38.3178% | −0.041762R | −4.468505R |
| Japan OOS | 108 | 41.6667% | +0.141433R | +15.274730R |
| 2025Q4 | 104 | 49.0385% | +0.285202R | +29.661041R |
| 2026Q1 | 109 | 32.1101% | −0.080979R | −8.826694R |
| 2026Q2 | 100 | 32.0000% | −0.148564R | −14.856434R |
| 2026Q3 partial | 5 | 20.0000% | −0.230323R | −1.151613R |

Every table value is [MEASURED: runner @ `2c71785`]. [MEASURED] Enumeration:
3,092 setups, 1,822 EMA touches, 734 invalidations, 536 touch expiries, 877
confirmation expiries, 945 confirmations/trades. Failed gates: >80% win rate,
every-symbol positivity, and every-complete-quarter positivity. Sample-size,
pooled expectancy and integrity gates passed. No EA change is authorized.

Lossless artifact: `backtest/holy_grail_entry_3r_results.json`.

