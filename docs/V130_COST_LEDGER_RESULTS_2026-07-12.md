# v1.30 executable-price cost-ledger audit result

## Headline verdict

**KILLED AT THE EDGE GATE.** Correcting the duplicated spread debit restores
positive pooled expectancy in all three executable-price columns, including
the mandatory E2 stress, but the result is not robust by symbol. E2 US30 is
negative, and E2 pooled expectancy becomes nonpositive when either JP225 or
US100 is deleted. The registered gate therefore forbids account Monte Carlo
and blind-frame access on this branch.

The corrected ledger does not support a high trade-win claim. E1 measured
39.61255845% wins and E2 measured 39.27855711%. An account-risk policy can
change Challenge pass probability but cannot change the win/loss labels of
this unchanged trade tape. [MEASURED: `python -u
backtest/run_v130_cost_audit.py --development` @
`304fe0dcb8cbcd00f963874818e697cfbf6c8112`]

## Provenance and access boundary

- Protocol SHA256:
  `271a12f4ce46717f15871aaf0c54321780484442709b82d628b047a2132d97a4`.
- Result timestamp: `2026-07-12T07:41:57.011705+00:00`.
- Result artifact SHA256:
  `d37455d10db728e7c4fbf6eea8321a2602b7621b9acb289255315814515ac3e0`.
- Frozen frame: FTMO development/mined split only.
- Confirmation accessed: false. Holdout accessed: false.
- Monte Carlo paths run: 0. Trial ledger: 209 -> 209; charge 0.

All values above are [MEASURED: result JSON and `Get-FileHash -Algorithm
SHA256 backtest/v130_cost_audit_results.json` @
`304fe0dcb8cbcd00f963874818e697cfbf6c8112`]. Repository lineage proves this
runner's accesses; global blind-frame status remains conditional on the owner
attestation concerning manual or untracked access.

## Registered command output, verbatim

Command: `python -u backtest/run_v130_cost_audit.py --development`

```text
verified cost-ledger protocol SHA256 271a12f4ce46717f15871aaf0c54321780484442709b82d628b047a2132d97a4
verified FTMO blind freeze 9 OK, 0 missing, 0 mismatched, 0 extra
verified 46 OK, 0 missing, 0 mismatched
parity hook synthetic checks: 9 passed
v130 cost-ledger synthetic tests: 49 passed
Golden regression: 46 identical, 0 failed, 134626 trades compared across 46 files.
verified FTMO blind freeze 9 OK, 0 missing, 0 mismatched, 0 extra
CONTROL mode=F1_PER_BAR n=1504 exp=+0.0175799036 sha256=6f0025dffec7011edf9a3a2701df7775a26b34b51cbae9d6efc3c557c24bd849
CONTROL mode=F2_STRICT_ASK n=1497 exp=+0.0025410956 sha256=6cd7b86866592927bd22475465feff138324c2487d8219a6a022e73b08b111a0
CONTROL mode=F2_STRICT_ASK_2X n=1497 exp=-0.0445521560 sha256=c34e15c96c7c2413dae8c77809c6f7bdbcc14b43b1007487e52f81e526d6d79e
EXECUTABLE mode=E0_EXECUTABLE n=1521 exp=+0.0505231267 win=0.4674556213 sha256=1ba0b57bddfdfc839b8a2d2e833f4cbd848c2927a2714569465b6fbdf29dd85c
EXECUTABLE mode=E1_MEASURED n=1497 exp=+0.0249106113 win=0.3961255845 sha256=0c4444421d354c3f24f019a0fe8fa3984dea4340ac84ecd3d0b9eb88d830a4a8
EXECUTABLE mode=E2_STRESS n=1497 exp=+0.0027554447 win=0.3927855711 sha256=eee99da264ed36680db5d6b080e291071849dc0bd78f0144ddb81eac3544d1c1
RESULT_FILE=C:\Users\Sanique Richards\Downloads\codex-scalp\backtest\v130_cost_audit_results.json
VERDICT=KILLED_AT_EDGE_GATE
```

[MEASURED: retained stdout from the registered command @
`304fe0dcb8cbcd00f963874818e697cfbf6c8112`]

## Control reproduction

Every value in this section is [MEASURED: registered command @
`304fe0dcb8cbcd00f963874818e697cfbf6c8112`]. All three committed controls
reproduced exactly before any executable-ledger result was exposed.

| control | n | total R | expectancy R | win rate | last-four-complete-quarter R |
|---|---:|---:|---:|---:|---:|
| C0 F1 | 1,504 | +26.4401750127 | +0.0175799036 | 40.29255319% | +0.0189162026 |
| C0 F2 | 1,497 | +3.8040200649 | +0.0025410956 | 39.61255845% | +0.0009467120 |
| C0 F2X | 1,497 | -66.6945775721 | -0.0445521560 | 39.41215765% | -0.0461761448 |

### Control per-symbol cells

| control | symbol | n | total R | expectancy R | win rate |
|---|---|---:|---:|---:|---:|
| C0 F1 | JP225.cash | 582 | +24.2744081481 | +0.0417086051 | 42.61168385% |
| C0 F1 | US100.cash | 366 | +11.3322705958 | +0.0309624880 | 40.16393443% |
| C0 F1 | US30.cash | 556 | -9.1665037312 | -0.0164865175 | 37.94964029% |
| C0 F2 | JP225.cash | 581 | +15.5748264867 | +0.0268069303 | 41.99655766% |
| C0 F2 | US100.cash | 363 | +6.0032823014 | +0.0165379678 | 39.11845730% |
| C0 F2 | US30.cash | 553 | -17.7740887232 | -0.0321412093 | 37.43218807% |
| C0 F2X | JP225.cash | 581 | -13.3514959814 | -0.0229801996 | 41.82444062% |
| C0 F2X | US100.cash | 363 | -10.1700135886 | -0.0280165664 | 38.84297521% |
| C0 F2X | US30.cash | 553 | -43.1730680021 | -0.0780706474 | 37.25135624% |

### Control calendar-quarter cells

| control | quarter | n | total R | expectancy R | win rate |
|---|---|---:|---:|---:|---:|
| C0 F1 | 2025Q2 | 279 | -0.0536695876 | -0.0001923641 | 39.42652330% |
| C0 F1 | 2025Q3 | 299 | +11.2089883307 | +0.0374882553 | 42.47491639% |
| C0 F1 | 2025Q4 | 303 | +5.8890364369 | +0.0194357638 | 38.94389439% |
| C0 F1 | 2026Q1 | 294 | +5.9113345314 | +0.0201065800 | 41.15646259% |
| C0 F1 | 2026Q2 | 290 | -0.5747429953 | -0.0019818724 | 38.96551724% |
| C0 F1 | 2026Q3 partial | 39 | +4.0592282966 | +0.1040827768 | 43.58974359% |
| C0 F2 | 2025Q2 | 277 | -1.3732750625 | -0.0049576717 | 38.98916968% |
| C0 F2 | 2025Q3 | 299 | +9.3285149764 | +0.0311990467 | 42.14046823% |
| C0 F2 | 2025Q4 | 297 | -0.3683640451 | -0.0012402830 | 38.04713805% |
| C0 F2 | 2026Q1 | 297 | +1.7619731417 | +0.0059325695 | 40.74074074% |
| C0 F2 | 2026Q2 | 288 | -9.6040572422 | -0.0333474210 | 37.50000000% |
| C0 F2 | 2026Q3 partial | 39 | +4.0592282966 | +0.1040827768 | 43.58974359% |
| C0 F2X | 2025Q2 | 277 | -14.3951466677 | -0.0519680385 | 38.98916968% |
| C0 F2X | 2025Q3 | 299 | -4.7603345431 | -0.0159208513 | 42.14046823% |
| C0 F2X | 2025Q4 | 297 | -14.3799445919 | -0.0484173219 | 37.37373737% |
| C0 F2X | 2026Q1 | 297 | -12.2523572130 | -0.0412537280 | 40.74074074% |
| C0 F2X | 2026Q2 | 288 | -23.1413906412 | -0.0803520508 | 37.15277778% |
| C0 F2X | 2026Q3 partial | 39 | +2.2345960849 | +0.0572973355 | 43.58974359% |

### Control delete-one-symbol cells

| control | deleted symbol | pooled expectancy R |
|---|---|---:|
| C0 F1 | JP225.cash | +0.0023489879 |
| C0 F1 | US100.cash | +0.0132758387 |
| C0 F1 | US30.cash | +0.0375597877 |
| C0 F2 | JP225.cash | -0.0128502254 |
| C0 F2 | US100.cash | -0.0019393847 |
| C0 F2 | US30.cash | +0.0228581661 |
| C0 F2X | JP225.cash | -0.0582348052 |
| C0 F2X | US100.cash | -0.0498452945 |
| C0 F2X | US30.cash | -0.0249168534 |

### Control side, exit, and partial-state cells

| control | side | n | total R | expectancy R | win rate |
|---|---|---:|---:|---:|---:|
| C0 F1 | long | 680 | -35.1093060447 | -0.0516313324 | 37.79411765% |
| C0 F1 | short | 824 | +61.5494810573 | +0.0746959722 | 42.35436893% |
| C0 F2 | long | 676 | -34.4824259496 | -0.0510095058 | 37.86982249% |
| C0 F2 | short | 821 | +38.2864460145 | +0.0466339172 | 41.04750305% |
| C0 F2X | long | 676 | -66.3082417252 | -0.0980891150 | 37.86982249% |
| C0 F2X | short | 821 | -0.3863358469 | -0.0004705674 | 40.68209501% |

| control | exit | n | total R | expectancy R | win rate |
|---|---|---:|---:|---:|---:|
| C0 F1 | SL | 861 | -684.4882279426 | -0.7949921347 | 0.00000000% |
| C0 F1 | TIME | 243 | +129.7843102200 | +0.5340918116 | 84.77366255% |
| C0 F1 | TP | 400 | +581.1440927353 | +1.4528602318 | 100.00000000% |
| C0 F2 | SL | 871 | -696.9717763582 | -0.8001972174 | 0.00000000% |
| C0 F2 | TIME | 233 | +129.8129474290 | +0.5571371134 | 85.83690987% |
| C0 F2 | TP | 393 | +570.9628489941 | +1.4528316768 | 100.00000000% |
| C0 F2X | SL | 871 | -737.9435527164 | -0.8472371443 | 0.00000000% |
| C0 F2X | TIME | 233 | +118.8232771561 | +0.5099711466 | 84.54935622% |
| C0 F2X | TP | 393 | +552.4256979882 | +1.4056633537 | 100.00000000% |

| control | partial state | n | total R | expectancy R | win rate |
|---|---|---:|---:|---:|---:|
| C0 F1 | no partial | 712 | -679.1139512650 | -0.9538117293 | 4.35393258% |
| C0 F1 | partial | 792 | +705.5541262777 | +0.8908511695 | 72.60101010% |
| C0 F2 | no partial | 718 | -690.0343969416 | -0.9610506921 | 4.03899721% |
| C0 F2 | partial | 779 | +693.8384170065 | +0.8906783274 | 72.40051348% |
| C0 F2X | no partial | 718 | -723.8520800703 | -1.0081505293 | 3.76044568% |
| C0 F2X | partial | 779 | +657.1575024982 | +0.8435911457 | 72.27214377% |

## Executable-price cells

Every value in this section is [MEASURED: registered command @
`304fe0dcb8cbcd00f963874818e697cfbf6c8112`]. E0 is the zero-slippage
accounting diagnostic, E1 applies the measured-rounded debit and current
negative swap, and E2 doubles both registered stresses.

| column | n | total R | expectancy R | win rate | last-four R | events | cross-server-midnight trades | event SHA256 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| E0 | 1,521 | +76.8456756774 | +0.0505231267 | 46.74556213% | +0.0520300947 | 24,801 | 39 | `1ba0b57bddfdfc839b8a2d2e833f4cbd848c2927a2714569465b6fbdf29dd85c` |
| E1 | 1,497 | +37.2911850726 | +0.0249106113 | 39.61255845% | +0.0230125110 | 24,565 | 38 | `0c4444421d354c3f24f019a0fe8fa3984dea4340ac84ecd3d0b9eb88d830a4a8` |
| E2 | 1,497 | +4.1249007632 | +0.0027554447 | 39.27855711% | +0.0005067540 | 24,565 | 38 | `eee99da264ed36680db5d6b080e291071849dc0bd78f0144ddb81eac3544d1c1` |

The registered last four complete quarters are 2025Q3, 2025Q4, 2026Q1,
and 2026Q2. [MEASURED: result JSON @ `304fe0d`]

### Executable per-symbol cells

| column | symbol | n | total R | expectancy R | win rate |
|---|---|---:|---:|---:|---:|
| E0 | JP225.cash | 589 | +44.6052533755 | +0.0757304811 | 48.72665535% |
| E0 | US100.cash | 367 | +26.7329726599 | +0.0728418874 | 47.13896458% |
| E0 | US30.cash | 565 | +5.5074496420 | +0.0097476985 | 44.42477876% |
| E1 | JP225.cash | 581 | +29.9583903039 | +0.0515634945 | 41.99655766% |
| E1 | US100.cash | 363 | +12.8803749862 | +0.0354831267 | 39.11845730% |
| E1 | US30.cash | 553 | -5.5475802175 | -0.0100317906 | 37.43218807% |
| E2 | JP225.cash | 581 | +17.3056141093 | +0.0297859107 | 41.30808950% |
| E2 | US100.cash | 363 | +4.5272842157 | +0.0124718573 | 38.84297521% |
| E2 | US30.cash | 553 | -17.7079975619 | -0.0320216954 | 37.43218807% |

### Executable calendar-quarter cells

| column | quarter | n | total R | expectancy R | win rate |
|---|---|---:|---:|---:|---:|
| E0 | 2025Q2 | 281 | +8.5287504726 | +0.0303514252 | 44.48398577% |
| E0 | 2025Q3 | 303 | +22.3773295206 | +0.0738525727 | 49.83498350% |
| E0 | 2025Q4 | 305 | +13.9018172050 | +0.0455797285 | 45.90163934% |
| E0 | 2026Q1 | 299 | +17.6870804504 | +0.0591541152 | 46.15384615% |
| E0 | 2026Q2 | 294 | +8.5219165977 | +0.0289861109 | 46.59863946% |
| E0 | 2026Q3 partial | 39 | +5.8287814310 | +0.1494559341 | 51.28205128% |
| E1 | 2025Q2 | 277 | +5.0646281593 | +0.0182838562 | 38.98916968% |
| E1 | 2025Q3 | 299 | +14.2973659022 | +0.0478172773 | 42.14046823% |
| E1 | 2025Q4 | 297 | +6.4263067966 | +0.0216373966 | 38.04713805% |
| E1 | 2026Q1 | 297 | +9.0129555703 | +0.0303466518 | 40.74074074% |
| E1 | 2026Q2 | 288 | -2.5588527869 | -0.0088849055 | 37.50000000% |
| E1 | 2026Q3 partial | 39 | +5.0487814310 | +0.1294559341 | 43.58974359% |
| E2 | 2025Q2 | 277 | -0.7423571913 | -0.0026799899 | 38.98916968% |
| E2 | 2025Q3 | 299 | +6.7174022838 | +0.0224662284 | 41.47157191% |
| E2 | 2025Q4 | 297 | -0.3117280594 | -0.0010495894 | 37.71043771% |
| E2 | 2026Q1 | 297 | +2.8383375935 | +0.0095566922 | 40.74074074% |
| E2 | 2026Q2 | 288 | -8.6455352945 | -0.0300192198 | 36.80555556% |
| E2 | 2026Q3 partial | 39 | +4.2687814310 | +0.1094559341 | 43.58974359% |

### Executable delete-one-symbol cells

| column | deleted symbol | pooled expectancy R |
|---|---|---:|
| E0 | JP225.cash | +0.0345927278 |
| E0 | US100.cash | +0.0434252193 |
| E0 | US30.cash | +0.0746215754 |
| E1 | JP225.cash | +0.0080052345 |
| E1 | US100.cash | +0.0215262876 |
| E1 | US30.cash | +0.0453800480 |
| E2 | JP225.cash | -0.0143894251 |
| E2 | US100.cash | -0.0003548355 |
| E2 | US30.cash | +0.0231280703 |

## Side, exit, and partial-state attribution

Every value in this section is [MEASURED: registered command @
`304fe0dcb8cbcd00f963874818e697cfbf6c8112`].

| column | side | n | total R | expectancy R | win rate |
|---|---|---:|---:|---:|---:|
| E0 | long | 692 | +1.7375092443 | +0.0025108515 | 44.21965318% |
| E0 | short | 829 | +75.1081664330 | +0.0906009245 | 48.85404101% |
| E1 | long | 676 | -18.7979967371 | -0.0278076875 | 38.01775148% |
| E1 | short | 821 | +56.0891818097 | +0.0683181264 | 40.92570037% |
| E2 | long | 676 | -34.9393833001 | -0.0516854783 | 37.86982249% |
| E2 | short | 821 | +39.0642840633 | +0.0475813448 | 40.43848965% |

| column | exit | n | total R | expectancy R | win rate |
|---|---|---:|---:|---:|---:|
| E0 | SL | 883 | -664.0000000000 | -0.7519818800 | 11.89127973% |
| E0 | TIME | 237 | +139.3456756774 | +0.5879564375 | 86.49789030% |
| E0 | TP | 401 | +601.5000000000 | +1.5000000000 | 100.00000000% |
| E1 | SL | 871 | -674.5380910488 | -0.7744409771 | 0.00000000% |
| E1 | TIME | 233 | +130.6000671807 | +0.5605153098 | 85.83690987% |
| E1 | TP | 393 | +581.2292089407 | +1.4789547301 | 100.00000000% |
| E2 | SL | 871 | -693.0761820977 | -0.7957246637 | 0.00000000% |
| E2 | TIME | 233 | +124.2426649795 | +0.5332303218 | 83.69098712% |
| E2 | TP | 393 | +572.9584178813 | +1.4579094603 | 100.00000000% |

| column | partial state | n | total R | expectancy R | win rate |
|---|---|---:|---:|---:|---:|
| E0 | no partial | 728 | -664.9237290641 | -0.9133567707 | 4.39560440% |
| E0 | partial | 793 | +741.7694047415 | +0.9353964751 | 85.62421185% |
| E1 | no partial | 718 | -673.4641509533 | -0.9379723551 | 4.17827298% |
| E1 | partial | 779 | +710.7553360259 | +0.9123945263 | 72.27214377% |
| E2 | no partial | 718 | -689.1099603274 | -0.9597631759 | 3.62116992% |
| E2 | partial | 779 | +693.2348610906 | +0.8899035444 | 72.14377407% |

## Ledger decomposition and rollover

Every value in this section is [MEASURED: registered command @
`304fe0dcb8cbcd00f963874818e697cfbf6c8112`]. `loss-classifier R` is the sum
used by the deployed EA's final-day four-loss classifier, not pooled total R.

| column | legacy debit removed R | short-time correction R | fixed slippage R | swap R | loss-classifier R |
|---|---:|---:|---:|---:|---:|
| E0 | +71.6262660701 | -3.8775200789 | +0.0000000000 | +0.0000000000 | +67.3456756774 |
| E1 | +70.4985976370 | -3.8451483199 | -29.9400000000 | -3.2262843094 | +27.9811850726 |
| E2 | +70.4985976370 | -3.8451483199 | -59.8800000000 | -6.4525686189 | -4.9950992368 |

E1 contained 35 rollover events across 34 trades. E2 used the same event
schedule and doubled only negative swap. Positive credits were suppressed.

| symbol | side | cadence | events | open-fraction sum | min | max | base R | E1 R | E2 R | credits suppressed |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| JP225.cash | long | ordinary | 5 | 3.5000 | 0.5000 | 1.0000 | -0.2520876962 | -0.2520876962 | -0.5041753924 | 0 |
| JP225.cash | long | triple | 1 | 1.0000 | 1.0000 | 1.0000 | -0.1757907520 | -0.1757907520 | -0.3515815040 | 0 |
| JP225.cash | short | ordinary | 6 | 4.5000 | 0.5000 | 1.0000 | -0.2529297095 | -0.2529297095 | -0.5058594190 | 0 |
| JP225.cash | short | triple | 2 | 2.0000 | 1.0000 | 1.0000 | -0.3519680369 | -0.3519680369 | -0.7039360738 | 0 |
| US100.cash | long | ordinary | 2 | 1.5000 | 0.5000 | 1.0000 | -0.1990340674 | -0.1990340674 | -0.3980681347 | 0 |
| US100.cash | long | triple | 1 | 1.0000 | 1.0000 | 1.0000 | -0.8940567031 | -0.8940567031 | -1.7881134062 | 0 |
| US100.cash | short | ordinary | 2 | 1.5000 | 0.5000 | 1.0000 | +0.0000000000 | +0.0000000000 | +0.0000000000 | 2 |
| US100.cash | short | triple | 1 | 1.0000 | 1.0000 | 1.0000 | +0.0000000000 | +0.0000000000 | +0.0000000000 | 1 |
| US30.cash | long | ordinary | 6 | 4.0000 | 0.5000 | 1.0000 | -0.6798064303 | -0.6798064303 | -1.3596128606 | 0 |
| US30.cash | long | triple | 2 | 1.0000 | 0.5000 | 0.5000 | -0.4206109141 | -0.4206109141 | -0.8412218282 | 0 |
| US30.cash | short | ordinary | 6 | 5.0000 | 0.5000 | 1.0000 | +0.0000000000 | +0.0000000000 | +0.0000000000 | 6 |
| US30.cash | short | triple | 1 | 0.5000 | 0.5000 | 0.5000 | +0.0000000000 | +0.0000000000 | +0.0000000000 | 1 |

## Coupling census

Every value is [MEASURED: registered command @ `304fe0d`]. Queue fields are
zero because queue mode is off.

| column | W2 | occupied | cooldown | cluster cap | global cap | day fills | day losses | stashed | replaced | released | expired | stale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C0 F1 | 5,520 | 823 | 294 | 470 | 151 | 33 | 176 | 0 | 0 | 0 | 0 | 0 |
| C0 F2 | 5,533 | 812 | 286 | 466 | 148 | 39 | 207 | 0 | 0 | 0 | 0 | 0 |
| C0 F2X | 5,533 | 812 | 286 | 466 | 148 | 39 | 207 | 0 | 0 | 0 | 0 | 0 |
| E0 | 5,511 | 826 | 288 | 472 | 153 | 42 | 143 | 0 | 0 | 0 | 0 | 0 |
| E1 | 5,533 | 812 | 286 | 466 | 148 | 39 | 207 | 0 | 0 | 0 | 0 | 0 |
| E2 | 5,533 | 812 | 286 | 466 | 148 | 39 | 207 | 0 | 0 | 0 | 0 | 0 |

## Fidelity, sign changes, and deterministic evidence

- Default-off regression: 46 identical, 0 failed, 134,626 trades across all
  46 manifest files.
- Synthetic suites: 9 parity-hook tests and 49 cost-ledger tests passed.
- C0 F2 versus E0: 1,497 shared trades, 0 raw-geometry mismatches, maximum
  base-F2 absolute R delta 0.0, and 121 registered short-time-exit ask-price
  exceptions.
- The first C0/E0 admission divergence is trade
  `JP225.cash:1744031700:1` at epoch 1744032600: C0 rejected it under
  `consecutive_loss_day_stop`; E0 placed it. This is the preregistered causal
  reason for subsequent schedule divergence.
- E0/E1: 1,497 shared completed trades, 104 final-sign changes, 24 E0-only
  completed trades, 64 later E1 consecutive-loss rejections, and no E1-only
  completed trade.
- E0/E2: 1,497 shared completed trades, 109 final-sign changes, 24 E0-only
  completed trades, 64 later E2 consecutive-loss rejections, and no E2-only
  completed trade.
- Policy-neutral E0-admission replays checked 35 swap events for each of E1
  and E2. Maximum per-trade R delta and maximum swap-event R delta were both
  0.0; independently scheduled-only trade count was 0.
- Event and diagnostic bytes matched an immediate second run for E0, E1, and
  E2. Their hashes are retained in the pooled table and JSON.
- An independent read-only parser completed 371 structural, aggregate,
  row-level, projection, gate, provenance, and hash checks: 371 passed and 0
  failed. It reproduced the failure list in the same order and found no
  numerical or hash discrepancy.

Every number above is [MEASURED: registered command and result JSON @
`304fe0dcb8cbcd00f963874818e697cfbf6c8112`]. The exact sign-changing IDs,
before/after R values, E0-only IDs, and all later rejection IDs are retained in
`backtest/v130_cost_audit_results.json` at:

- `comparisons.E0_EXECUTABLE_vs_E1_MEASURED`
- `comparisons.E0_EXECUTABLE_vs_E2_STRESS`
- `comparisons.F2_STRICT_ASK_vs_E0_EXECUTABLE_raw_geometry`

This is the lossless report of those identifiers; none were sampled or
omitted from the committed artifact.

[MEASURED: independent read-only result audit @ `304fe0d`]

The parity-hook, manifest, and 46-file regression checks are abort-before-write
preflights and are evidenced by retained stdout plus the artifact's existence;
they are not persisted as separate booleans in the JSON. That is a reporting
limitation, not a numerical discrepancy. [MEASURED: runner source and
independent artifact audit @ `304fe0d`]

## Gate failures and disposition

The exact registered failures were:

1. `E2_STRESS/US30.cash: symbol expectancy < 0`
2. `E2_STRESS/without-JP225.cash: expectancy <= 0`
3. `E2_STRESS/without-US100.cash: expectancy <= 0`

[MEASURED: `edge_gate.failures` in result JSON @ `304fe0d`]

All other registered edge and fidelity gates passed. Nevertheless, one failed
gate is sufficient. The cost-ledger correction is retained as an accounting
finding, but it is disposed for promotion. No account MC ran, no risk input or
EA was changed, and confirmation/holdout remain inaccessible to this runner.
[MEASURED: registered command @ `304fe0d`]

The only result-supported next hypothesis that preserves signal and exit
geometry is portfolio allocation: US30 contributed negative expectancy under
both E1 and E2 while JP225 and US100 remained positive. Any deletion or
down-weight is a new, explicitly charged hypothesis and requires a new hash
before testing. [DERIVED from the preregistered per-symbol cells]

## Failed-command journal

The first read-only swap-calibration command attempted a field not supplied by
this MetaTrader5 package. It made no terminal write and failed before any
strategy outcome was run. The retained failure was:

```text
AttributeError: 'SymbolInfo' object has no attribute 'swap_sunday'
```

[MEASURED: retained pre-outcome calibration output]

A later Markdown-table extraction helper was quoted incorrectly for
PowerShell. It did not invoke an experiment, access data, or change a file. Its
retained first and representative parser lines were:

```text
At line:5 char:42
Expressions are only allowed as the first element of a pipeline.
```

[MEASURED: reporting-session output after the registered run]

The independent auditor's first read-only consistency script addressed a
policy-neutral row by the wrong field name. It did not rerun an outcome. The
complete retained exception was:

```text
Traceback (most recent call last):
  File "<stdin>", line 88, in <module>
  File "<stdin>", line 88, in <genexpr>
KeyError: 'total_r'
```

The corrected parser then passed all 371 checks. [MEASURED: independent
read-only result audit @ `304fe0d`]

## Terminal-write and operational journal

- FTMO access for the audit was read-only `history_orders_get`,
  `history_deals_get`, account state, and symbol metadata. No order was placed,
  modified, or closed; no terminal process was restarted; no EA input, chart,
  setting, deployed source, or binary was changed. [MEASURED: audit operations]
- Repository writes are the preregistration, default-off execution hook,
  executable-ledger implementation, result artifact, spec result append, and
  this report. [MEASURED: Git history through `304fe0d` plus this result commit]
- The unrelated Deriv terminal was not connected to or operated. [MEASURED:
  audit operations]

## One-line verdict

**COST ACCOUNTING CORRECTED; PROMOTION KILLED BY E2 SYMBOL-ROBUSTNESS GATES;
>88% FTMO CHALLENGE PASS EXPECTANCY NOT DEMONSTRATED.**
