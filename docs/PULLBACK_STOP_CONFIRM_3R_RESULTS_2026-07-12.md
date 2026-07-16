# First-touch pullback stop-confirmation with 3R target — results

**Verdict: DISPOSE — catastrophic.** [MEASURED: registered runner @
`728dd156362c6e95d97e01ad336505efb1bd806a`] OOS win rate fell from 34.0782%
to 21.3531% and expectancy fell from −0.033880R to −0.419143R.

[MEASURED] Protocol SHA256 `3c0635497fcbee2211ea43c170524458f3b9ffd1b296a9772af5a915db84e664`;
canonical data 46/46; control regression 9/9; synthetic tests 5/5; ledger
215 -> 216; terminal writes/FTMO MC/blind access all zero.

| Cell/frame | n | Win | Exp | Total R |
|---|---:|---:|---:|---:|
| C0 all | 3,593 | 33.3148% | −0.040533R | −145.634372R |
| S1 all | 1,561 | 22.1012% | −0.386172R | −602.814189R |
| C0 OOS | 1,074 | 34.0782% | −0.033880R | −36.387618R |
| S1 OOS | 473 | 21.3531% | −0.419143R | −198.254576R |
| S1 minus C0 | −601 | −12.7251 pp | −0.385262R | −161.866958R |

| S1 OOS slice | n | Win | Exp | Total R |
|---|---:|---:|---:|---:|
| Wall Street 30 | 158 | 17.7215% | −0.483536R | −76.398625R |
| US Tech 100 | 170 | 26.4706% | −0.285765R | −48.580017R |
| Japan 225 | 145 | 19.3103% | −0.505351R | −73.275934R |
| 2025Q4 | 165 | 19.3939% | −0.476331R | −78.594653R |
| 2026Q1 | 155 | 20.6452% | −0.416796R | −64.603374R |
| 2026Q2 | 147 | 23.8095% | −0.375091R | −55.138389R |
| 2026Q3 partial | 6 | 33.3333% | +0.013640R | +0.081841R |

All table source values are [MEASURED: runner @ `728dd15`]; deltas are
[DERIVED]. [MEASURED] OOS retention was 44.0410%. Enumeration totals were 5,268
signals, 3,565 pullback touches, 1,561 confirmations, 2,004 unconfirmed expiries,
and 1,703 unfilled orders. All performance gates failed except retention and
integrity. No EA change is authorized. Lossless artifact:
`backtest/pullback_stop_confirm_3r_results.json`.

