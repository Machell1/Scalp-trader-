# Six-fill intraday sleeve report

## Verdict

**SIX-FILL TARGET NOT MET — BOTH M30 CELLS ARE KILLED.** Neither cell
produced a single symbol that preserved positive E2 expectancy in both the
causal calibration and confirmation windows. The final 30% OOS portfolio,
frequency gate, and account Monte Carlo were therefore not opened. The live
v1.31 H1 EA remains unchanged.

## Provenance and regression

The protocol was committed before outcomes at `bdc9ce2`, with recorded
pre-registration SHA256
`5748232e24bd8d78bb4349704a4ac9ab7f4c80d4e35a75902146103a1acb22fe`.

```text
verified 46 OK, 0 missing, 0 mismatched
```

[MEASURED: `python backtest/verify_data.py` @ `4605d22`]

The additive market-entry/timeframe parameters left default behavior intact:
the golden regression compared 134,626 trades across all 46 manifest files
and returned `46 identical, 0 failed`. Nine parity-hook synthetic checks and
all harness invariants also passed. The M30 aggregation regression returned
600 identical rows. [MEASURED: `python -u backtest/parity_regression.py`,
`python backtest/test_parity_hooks.py`, `python backtest/harness_invariants_test.py`,
and `python -u backtest/run_frequency_six_study.py` @ `4605d22`]

## Current frequency gap

The frozen four-symbol v1.31 H1 tape contains 1,645 accepted pending attempts,
969 fills, and 676 unfilled cancellations over 1,032 calendar days. That is
0.938953 fills per calendar day. Across the 738 Monday-Friday dates from
2023-09-05 through 2026-07-02, it is 1.313008 fills per trading day. Six fills
per trading day therefore requires 4.569659 times the current H1 rate.
[MEASURED: `build_h1_universe_tape(('Wall_Street_30','US_Tech_100','Japan_225','USDJPY'), stress=True)` @ `4605d22`; DERIVED: ratios]

Market conversion cannot close that gap by itself: the same tape has only
1.593992 accepted attempts per calendar day even before 41.094% of attempts
cancel unfilled. [MEASURED: same command @ `4605d22`; DERIVED: 676 / 1,645]

## M30 selection results

Each entry is `trade count / E2 expectancy`. The complete machine-readable
artifact is `backtest/frequency_six_results.json`, SHA256
`9bdde6d57336c386ed35a9b19dbcc2632bcf177cc446f5b90e1cd4878277c864`.
[MEASURED: `python -u backtest/run_frequency_six_study.py` @ `4605d22`]

| Symbol | P30 calibration | P30 confirmation | M30 calibration | M30 confirmation |
|---|---:|---:|---:|---:|
| AUDJPY | 295 / -0.133747R | 131 / -0.078001R | 500 / -0.134397R | 207 / -0.298188R |
| AUS200.cash | 247 / -0.073958R | 89 / -0.014501R | 383 / -0.228723R | 140 / -0.264453R |
| BCHUSD | 369 / -0.240982R | 143 / -0.162864R | 552 / -0.399865R | 225 / -0.261813R |
| BTCUSD | 367 / -0.279094R | 134 / -0.083681R | 561 / -0.317297R | 211 / -0.207020R |
| ETHUSD | 407 / -0.261503R | 139 / +0.026103R | 619 / -0.265786R | 242 / -0.150463R |
| EURGBP | 339 / -0.211071R | 128 / -0.221455R | 492 / -0.328676R | 189 / -0.249371R |
| EURJPY | 332 / -0.179798R | 124 / -0.251606R | 559 / -0.207460R | 203 / -0.246852R |
| EURUSD | 396 / -0.101637R | 142 / -0.134922R | 569 / -0.269305R | 222 / -0.187748R |
| FRA40.cash | 317 / -0.166021R | 116 / -0.148656R | 484 / -0.284345R | 180 / -0.208881R |
| GBPJPY | 333 / -0.096615R | 123 / -0.113583R | 547 / -0.163163R | 204 / -0.158917R |
| GBPUSD | 387 / -0.152501R | 128 / -0.001099R | 588 / -0.241951R | 208 / -0.128434R |
| GER40.cash | 322 / -0.051281R | 131 / -0.067975R | 487 / -0.205617R | 187 / -0.179881R |
| HK50.cash | 319 / -0.274213R | 106 / -0.126395R | 490 / -0.262834R | 170 / -0.177744R |
| JP225.cash | 292 / -0.069901R | 105 / -0.199514R | 445 / -0.215266R | 184 / -0.256460R |
| LTCUSD | 346 / -0.189047R | 135 / -0.300738R | 533 / -0.291103R | 213 / -0.271528R |
| NATGAS.cash | 352 / -0.566699R | 181 / -0.668546R | 539 / -0.593232R | 261 / -0.720956R |
| NZDUSD | 312 / -0.243995R | 123 / -0.044791R | 514 / -0.308667R | 209 / -0.232648R |
| SOLUSD | 355 / -0.155924R | 148 / -0.266268R | 554 / -0.266652R | 237 / -0.190368R |
| UK100.cash | 272 / -0.526213R | 96 / -0.397541R | 420 / -0.616629R | 158 / -0.647203R |
| UKOIL.cash | 284 / -0.473000R | 123 / -0.508368R | 417 / -0.636392R | 175 / -0.656747R |
| US100.cash | 329 / +0.074536R | 134 / -0.030790R | 484 / -0.070403R | 204 / -0.186766R |
| US2000.cash | 314 / -0.399224R | 128 / -0.296340R | 465 / -0.511266R | 187 / -0.485693R |
| US30.cash | 348 / +0.111966R | 118 / -0.061078R | 511 / -0.139959R | 189 / -0.064669R |
| US500.cash | 314 / +0.004883R | 116 / -0.180893R | 485 / -0.142485R | 180 / -0.170378R |
| USDCAD | 346 / -0.341761R | 123 / -0.081892R | 517 / -0.373152R | 188 / -0.275666R |
| USDCHF | 355 / -0.226134R | 121 / -0.195625R | 533 / -0.294068R | 201 / -0.238010R |
| USDJPY | 362 / -0.194706R | 121 / -0.218520R | 563 / -0.210976R | 221 / -0.201958R |
| USOIL.cash | 332 / -0.451762R | 135 / -0.499689R | 475 / -0.594828R | 194 / -0.572078R |
| XAGUSD | 337 / -0.817385R | 125 / -0.707017R | 537 / -0.960256R | 184 / -1.066740R |
| XAUUSD | 395 / -0.092555R | 136 / -0.157718R | 623 / -0.190703R | 216 / -0.139439R |
| XCUUSD | 53 / +0.142897R | 20 / -0.250569R | 82 / -0.108722R | 38 / -0.339503R |
| XPTUSD | 333 / +0.097916R | 104 / -0.173458R | 522 / -0.195663R | 153 / -0.322709R |
| XRPUSD | 404 / -0.342387R | 144 / -0.309202R | 595 / -0.467301R | 228 / -0.380880R |

P30 produced 10,865 calibration trades at -0.217077R pooled expectancy and
4,070 confirmation trades at -0.215775R. Five of 33 symbols were positive in
calibration, one was positive in confirmation, and none was positive in both;
the frozen selector admitted zero. M30 produced 16,645 calibration trades at
-0.320544R and 6,408 confirmation trades at -0.303370R; zero of 33 symbols
were positive in either selection window. [MEASURED: same command @ `4605d22`]

## Decision

M30 market orders increased the gross single-symbol sample by 53.198% in
calibration and 57.445% in confirmation relative to M30 pendings, but worsened
pooled expectancy by 0.103467R and 0.087594R respectively. [DERIVED from the
measured pooled counts and expectancies]

The proposed M30 frequency sleeve is disposed of. No final-OOS data were used,
no account-risk cells were charged, and no terminal, EA, whitelist, lot sizing,
or live settings were changed. A six-fill target remains a valid research
objective, but the next attempt must be an independent intraday entry edge;
lowering the validated momentum-pullback timeframe or converting it to market
execution is now a measured dead end.
