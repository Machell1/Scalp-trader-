# Smooth-impulse FIP entry gate with 3R target — results

## Verdict

**DISPOSE.** [MEASURED: `python -u backtest/run_fip_entry_3r.py` @
`f058de297064211225933bffbda395829db79e52`] FIP improved stitched-OOS
expectancy from −0.033880R to +0.016469R and win rate from 34.0782% to 36.2090%,
but the +2.1308-point lift missed the registered +5.00-point gate. Wall Street
30 and complete quarter 2025Q4 remained negative.

## Provenance

- [MEASURED: runner @ `f058de2`] Protocol SHA256
  `f5d20adc0f9d3d8535a8c4b585f4ef2c6fa5a82261b66d5b3073299325d79ad4`.
- [MEASURED: `python backtest/verify_data.py` @ `f058de2`]
  `verified 46 OK, 0 missing, 0 mismatched`.
- [MEASURED: runner @ `f058de2`] Default regression 9 identical, 0 failed;
  six synthetic checks passed.
- [MEASURED: independent audit @ `f058de2`] 19 consistency checks passed.
- [MEASURED: `Get-FileHash` @ `f058de2`] Artifact SHA256
  `719016399e824aebd69cb1d0db559c65f65020d17c5c66a94d9d6099ef06e5e0`.
- [MEASURED: runner @ `f058de2`] Ledger 213 -> 214; terminal writes 0;
  confirmation/holdout false; FTMO MC paths 0.

## Pooled cells

| Cell/frame | n | Win rate | Expectancy | Total R |
|---|---:|---:|---:|---:|
| C0 all | 3,593 | 33.3148% | −0.040533R | −145.634372R |
| F1 all | 2,728 | 34.6774% | −0.021150R | −57.698447R |
| C0 stitched OOS | 1,074 | 34.0782% | −0.033880R | −36.387618R |
| F1 stitched OOS | 823 | 36.2090% | +0.016469R | +13.553968R |
| F1 minus C0 OOS | −251 | +2.1308 pp | +0.050349R | +49.941586R |

Source cells are [MEASURED: runner @ `f058de2`]; deltas are [DERIVED] exact
arithmetic recorded by the runner. [MEASURED] OOS trade retention was 76.6294%.

## Stitched-OOS symbol cells

| Symbol | C0 n | C0 win | C0 exp | C0 R | F1 n | F1 win | F1 exp | F1 R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Wall Street 30 | 368 | 32.6087% | −0.058213R | −21.422414R | 277 | 33.5740% | −0.046654R | −12.923084R |
| US Tech 100 | 354 | 34.1808% | −0.006543R | −2.316202R | 290 | 35.8621% | +0.033786R | +9.798065R |
| Japan 225 | 352 | 35.5114% | −0.035935R | −12.649002R | 256 | 39.4531% | +0.065152R | +16.678986R |

Every value is [MEASURED: runner @ `f058de2`].

## Stitched-OOS quarter cells

| Quarter | C0 n | C0 win | C0 exp | C0 R | F1 n | F1 win | F1 exp | F1 R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025Q4 | 381 | 31.4961% | −0.088032R | −33.540236R | 291 | 33.6770% | −0.050932R | −14.821293R |
| 2026Q1 | 352 | 36.6477% | +0.012632R | +4.446573R | 280 | 37.8571% | +0.044761R | +12.533119R |
| 2026Q2 | 331 | 33.5347% | −0.046489R | −15.387732R | 244 | 36.4754% | +0.029068R | +7.092672R |
| 2026Q3 partial | 10 | 60.0000% | +0.809378R | +8.093778R | 8 | 62.5000% | +1.093684R | +8.749470R |

Every value is [MEASURED: runner @ `f058de2`].

## Enumeration and gates

[MEASURED: runner @ `f058de2`] F1 encountered 5,902 frozen signals, admitted
4,122, rejected 1,780, and produced 2,728 trades; eligibility was 69.8407%.
By symbol, admitted/rejected/trades were Wall Street 1,377/605/942, US Tech
1,411/609/944, and Japan 1,334/566/842.

| Gate | Result |
|---|---|
| OOS win-rate lift >=5 pp | **FAIL** (+2.1308 pp) |
| OOS expectancy positive/not below C0 | PASS |
| Every symbol OOS positive | **FAIL** (Wall Street −0.046654R) |
| Every complete OOS quarter positive | **FAIL** (2025Q4 −0.050932R) |
| OOS retention >=35% | PASS |
| Regression/synthetic checks | PASS |
| Win rate >80% diagnostic | false (36.2090%) |

[DERIVED] FIP contains some useful information but is neither sufficiently
selective nor robust. Combining it with the failed reclaim rule after observing
both outcomes is prohibited. No EA change is authorized.

