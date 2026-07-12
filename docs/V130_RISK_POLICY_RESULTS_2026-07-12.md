# v1.30 FTMO risk-policy development result

## Headline verdict

**KILLED AT THE EDGE GATE.** The unchanged v1.30 tape is positive under the
primary observed-spread column but loses its edge under the mandatory strict-ask
2x-cost stress. No Monte Carlo risk-policy cell ran, no ledger hypothesis was
charged, and neither locked confirmation nor sealed holdout was opened.

The 90% trade-win objective is not supported: the eligible execution columns
measured 39.41% to 40.29% winning trades. Risk sizing cannot change that trade
win rate. [MEASURED: `python backtest/run_v130_risk_study.py --development-edge`
@ `18b04c7a8613fcfdee952d2ceb7cddbed54eccd4`]

## Provenance and fidelity

- Protocol SHA256: `8f2043af550df082e493a3d295f305d014c4083115b96bfbdfe61855f860e30a`.
- Development frame: newest 30,000 frozen FTMO M15 bars/symbol; confirmation
  and holdout remained unopened. [MEASURED: edge command @ `18b04c7`]
- `verified FTMO blind freeze 9 OK, 0 missing, 0 mismatched, 0 extra`.
  [MEASURED: `python backtest/freeze_ftmo_v130_blind.py --verify` @ `18b04c7`]
- `verified 46 OK, 0 missing, 0 mismatched`.
  [MEASURED: `python backtest/verify_data.py` @ `18b04c7`]
- Golden regression: 46 identical, 0 failed, 134,626 trades across 46 canonical
  files. [MEASURED: `python backtest/parity_regression.py` @ `18b04c7`]
- Independent D0 identity: 3,757 trades, maximum absolute R difference
  0.0000000000001597. Independent F1 identity: 3,687 trades, maximum absolute R
  difference 0.0000000000000002. Both are below the registered 1e-12 tolerance.
  [MEASURED: `python backtest/v130_fidelity.py` @ `18b04c7`]
- Synthetic gates: parity hooks 8/8, account/risk engine 16/16, coupled adapter
  7/7. [MEASURED: synthetic commands @ `18b04c7`]

## Coupled execution results

All values in the following tables are [MEASURED: development-edge command @
`18b04c7`]. D0 is diagnostic only. F1, F2, and F2-2x are the registered
eligibility columns.

| column | trades | expectancy R | win rate | last-4-complete-quarter R | events | cross-EA-midnight trades |
|---|---:|---:|---:|---:|---:|---:|
| D0_TOUCH | 1,544 | +0.0580007762 | 41.58031088% | +0.0628647986 | 25,366 | 40 |
| F1_PER_BAR | 1,504 | +0.0175799036 | 40.29255319% | +0.0189162026 | 24,895 | 38 |
| F2_STRICT_ASK | 1,497 | +0.0025410956 | 39.61255845% | +0.0009467120 | 24,565 | 38 |
| F2_STRICT_ASK_2X | 1,497 | **-0.0445521560** | 39.41215765% | **-0.0461761448** | 24,565 | 38 |

F2 and F2-2x had identical trade IDs, bars, prices, reasons, occupancy, and
lifecycle events; only registered transaction-cost cashflows differed.
[MEASURED: runner identity assertion @ `18b04c7`]

### Per-symbol cells

| column | symbol | n | expectancy R | win rate |
|---|---|---:|---:|---:|
| D0 | JP225.cash | 596 | +0.0804086257 | 43.95973154% |
| D0 | US100.cash | 380 | +0.0993865499 | 42.63157895% |
| D0 | US30.cash | 568 | +0.0068006488 | 38.38028169% |
| F1 | JP225.cash | 582 | +0.0417086051 | 42.61168385% |
| F1 | US100.cash | 366 | +0.0309624880 | 40.16393443% |
| F1 | US30.cash | 556 | **-0.0164865175** | 37.94964029% |
| F2 | JP225.cash | 581 | +0.0268069303 | 41.99655766% |
| F2 | US100.cash | 363 | +0.0165379678 | 39.11845730% |
| F2 | US30.cash | 553 | **-0.0321412093** | 37.43218807% |
| F2-2x | JP225.cash | 581 | **-0.0229801996** | 41.82444062% |
| F2-2x | US100.cash | 363 | **-0.0280165664** | 38.84297521% |
| F2-2x | US30.cash | 553 | **-0.0780706474** | 37.25135624% |

### Calendar-quarter cells

| column | quarter | n | expectancy R | win rate |
|---|---|---:|---:|---:|
| D0 | 2025Q2 | 288 | +0.0260030736 | 40.27777778% |
| D0 | 2025Q3 | 309 | +0.0862631612 | 44.01294498% |
| D0 | 2025Q4 | 308 | +0.0513681685 | 40.25974026% |
| D0 | 2026Q1 | 299 | +0.0700242245 | 41.80602007% |
| D0 | 2026Q2 | 301 | +0.0434966910 | 40.86378738% |
| D0 | 2026Q3 partial | 39 | +0.1425090613 | 46.15384615% |
| F1 | 2025Q2 | 279 | -0.0001923641 | 39.42652330% |
| F1 | 2025Q3 | 299 | +0.0374882553 | 42.47491639% |
| F1 | 2025Q4 | 303 | +0.0194357638 | 38.94389439% |
| F1 | 2026Q1 | 294 | +0.0201065800 | 41.15646259% |
| F1 | 2026Q2 | 290 | -0.0019818724 | 38.96551724% |
| F1 | 2026Q3 partial | 39 | +0.1040827768 | 43.58974359% |
| F2 | 2025Q2 | 277 | -0.0049576717 | 38.98916968% |
| F2 | 2025Q3 | 299 | +0.0311990467 | 42.14046823% |
| F2 | 2025Q4 | 297 | -0.0012402830 | 38.04713805% |
| F2 | 2026Q1 | 297 | +0.0059325695 | 40.74074074% |
| F2 | 2026Q2 | 288 | -0.0333474210 | 37.50000000% |
| F2 | 2026Q3 partial | 39 | +0.1040827768 | 43.58974359% |
| F2-2x | 2025Q2 | 277 | -0.0519680385 | 38.98916968% |
| F2-2x | 2025Q3 | 299 | -0.0159208513 | 42.14046823% |
| F2-2x | 2025Q4 | 297 | -0.0484173219 | 37.37373737% |
| F2-2x | 2026Q1 | 297 | -0.0412537280 | 40.74074074% |
| F2-2x | 2026Q2 | 288 | -0.0803520508 | 37.15277778% |
| F2-2x | 2026Q3 partial | 39 | +0.0572973355 | 43.58974359% |

The registered last-four complete quarters were 2025Q3, 2025Q4, 2026Q1, and
2026Q2. [MEASURED: edge command @ `18b04c7`]

### Delete-one-symbol cells

| column | deleted symbol | pooled expectancy R |
|---|---|---:|
| D0 | JP225.cash | +0.0439131408 |
| D0 | US100.cash | +0.0444899566 |
| D0 | US30.cash | +0.0877975716 |
| F1 | JP225.cash | +0.0023489879 |
| F1 | US100.cash | +0.0132758387 |
| F1 | US30.cash | +0.0375597877 |
| F2 | JP225.cash | **-0.0128502254** |
| F2 | US100.cash | **-0.0019393847** |
| F2 | US30.cash | +0.0228581661 |
| F2-2x | JP225.cash | **-0.0582348052** |
| F2-2x | US100.cash | **-0.0498452945** |
| F2-2x | US30.cash | **-0.0249168534** |

### Coupling census

| column | W2 rejects | occupied rejects | cooldown | cluster cap | global cap | day-fill cap | day-loss-streak cap |
|---|---:|---:|---:|---:|---:|---:|---:|
| D0 | 5,526 | 807 | 304 | 465 | 148 | 48 | 171 |
| F1 | 5,520 | 823 | 294 | 470 | 151 | 33 | 176 |
| F2 | 5,533 | 812 | 286 | 466 | 148 | 39 | 207 |
| F2-2x | 5,533 | 812 | 286 | 466 | 148 | 39 | 207 |

Queue fields were all zero because the registered queue mode is off.
[MEASURED: edge command @ `18b04c7`]

### Determinism hashes

| column | normalized event SHA256 |
|---|---|
| D0 | `aa7064cc2509cf1c7cdb158dae57feedc2e584098c72b5bf01b2b9a3bbda4a13` |
| F1 | `6f0025dffec7011edf9a3a2701df7775a26b34b51cbae9d6efc3c557c24bd849` |
| F2 | `6cd7b86866592927bd22475465feff138324c2487d8219a6a022e73b08b111a0` |
| F2-2x | `c34e15c96c7c2413dae8c77809c6f7bdbcc14b43b1007487e52f81e526d6d79e` |

Each hash matched an immediate second run byte-for-byte. [MEASURED:
development-edge command @ `18b04c7`]

## Gate failures and disposition

The edge gate failed 15 checks: F1 US30 expectancy; F2 US30 expectancy; two F2
delete-one-symbol cells; F2-2x pooled expectancy; F2-2x last-four expectancy;
all three F2-2x symbol cells; all three F2-2x delete-one-symbol cells; and the
cross-server-midnight fidelity condition in F1, F2, and F2-2x. [MEASURED: edge
command @ `18b04c7`]

The risk-policy idea is disposed. C0, R1, R2, and R3 Monte Carlo were not run,
because position sizing cannot restore a negative pre-account edge. Registered
paths run: 0 of 100,000. Ledger: 209 -> 209; charge 0. [MEASURED: edge command @
`18b04c7`]

Confirmation and holdout status: **unopened**. [MEASURED: runner has no blind
frame CLI @ `18b04c7`]

## Failed-command journal

The first blind-freeze attempt failed transactionally and published no frame:

```text
Traceback (most recent call last):
  File "C:\Users\Sanique Richards\Downloads\codex-scalp\backtest\freeze_ftmo_v130_blind.py", line 603, in <module>
    main()
    ~~~~^^
  File "C:\Users\Sanique Richards\Downloads\codex-scalp\backtest\freeze_ftmo_v130_blind.py", line 599, in main
    freeze()
    ~~~~~~^^
  File "C:\Users\Sanique Richards\Downloads\codex-scalp\backtest\freeze_ftmo_v130_blind.py", line 523, in freeze
    raise RuntimeError(f"{symbol}: copy_rates_range failed: {mt5.last_error()}")
RuntimeError: US30.cash: copy_rates_range failed: (-2, 'Terminal: Invalid params')
```

The first manifest-safe parity run failed before opening any CSV because the
historical manifest comment header was CP-1252:

```text
UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97 in position 29: invalid start byte
```

The verifier correctly rejected both uncommitted below-hash appends (the
implementation conventions and, later, this result append) before their
respective commits:

```text
RuntimeError: working protocol differs from committed HEAD
```

Intermediate synthetic assertions also failed while timing and no-epsilon lot
fixtures were being corrected; the final suites above passed. [MEASURED:
development logs before `18b04c7`]

## Terminal-write and operational journal

- FTMO access for this study was read-only market-data retrieval. No order was
  placed, modified, or closed; no EA input, chart, terminal setting, or deployed
  file was changed during this study. [MEASURED: study operations @ `18b04c7`]
- Repo writes were the preregistration, exporter, frozen-data manifest, fidelity
  engines, result JSON, and this report. [MEASURED: Git history]
- A process-status diagnostic inadvertently exposed an unrelated resident Deriv
  bridge credential in the tool log. The Deriv terminal was not connected to or
  operated. That credential should be rotated. [MEASURED: operational incident]

## One-line verdict

**V1.30 RISK-SIZING IDEA DISPOSED — EDGE LOST UNDER MANDATORY F2 2X COST;
>88% FTMO CHALLENGE PASS EXPECTANCY NOT DEMONSTRATED.**
