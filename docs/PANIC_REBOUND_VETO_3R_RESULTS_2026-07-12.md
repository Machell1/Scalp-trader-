# Panic-rebound veto with 3R target — results

**Verdict: DISPOSE.** [MEASURED: registered runner @
`58f2cc57723b39d56ea3049a921051ce4cb1514d`] OOS expectancy remained negative
(−0.030920R versus C0 −0.033880R) and win rate fell from 34.0782% to 33.6373%.

[MEASURED: runner @ `58f2cc5`] Protocol SHA256
`239f3889bb36fd0dfcc46ee3376f55b86b48c1d1375c2b3be695b3f892a25467`;
data `verified 46 OK, 0 missing, 0 mismatched`; default regression 9/9;
synthetic tests 7/7; ledger 214 -> 215; terminal writes 0; no confirmation,
holdout, or FTMO MC.

| Cell/frame | n | Win | Exp | Total R |
|---|---:|---:|---:|---:|
| C0 all | 3,593 | 33.3148% | −0.040533R | −145.634372R |
| P1 all | 3,342 | 33.1837% | −0.036294R | −121.294217R |
| C0 OOS | 1,074 | 34.0782% | −0.033880R | −36.387618R |
| P1 OOS | 987 | 33.6373% | −0.030920R | −30.517713R |
| P1 minus C0 | −87 | −0.4409 pp | +0.002961R | +5.869905R |

| OOS slice | n | Win | Exp | Total R |
|---|---:|---:|---:|---:|
| P1 Wall Street 30 | 341 | 31.6716% | −0.059155R | −20.171855R |
| P1 US Tech 100 | 330 | 33.9394% | +0.004659R | +1.537457R |
| P1 Japan 225 | 316 | 35.4430% | −0.037605R | −11.883316R |
| P1 2025Q4 | 345 | 31.0145% | −0.090505R | −31.224061R |
| P1 2026Q1 | 323 | 35.6037% | +0.010889R | +3.517200R |
| P1 2026Q2 | 310 | 33.5484% | −0.038481R | −11.928984R |
| P1 2026Q3 partial | 9 | 66.6667% | +1.013126R | +9.118133R |

All table source values are [MEASURED: runner @ `58f2cc5`]; delta values are
[DERIVED] exact runner arithmetic. [MEASURED] P1 retained 91.8994% of OOS trades.

[MEASURED] Enumeration by symbol (frozen/admitted/vetoed/trades): Wall Street
1,843/1,672/171/1,178; US Tech 1,840/1,661/179/1,127; Japan
1,790/1,602/188/1,037. Pooled: 5,473/4,935/538/3,342; veto rate 9.8301%.

Failed gates: win-rate lift, positive OOS expectancy, every-symbol positivity,
and every-complete-quarter positivity. Win rate >80% diagnostic: false. No EA
change is authorized. The lossless artifact reports the C0 comparison cells and
all nine regression hashes: `backtest/panic_veto_3r_results.json`.

