# Immediate pullback-reclaim entry with 3R target — results

## Verdict

**DISPOSE.** [MEASURED: `python -u backtest/run_reclaim_entry_3r.py` @
`64b837e267dc5be36d56e870d9220caf584e6c20`] Immediate reclaim improved pooled
stitched-OOS expectancy from −0.033880R to +0.024971R, but lifted net win rate
only from 34.0782% to 35.5140% (+1.4358 percentage points versus the registered
+5.00-point gate). Wall Street 30 remained negative and complete quarter 2026Q2
was negative. Three gates failed, so the candidate is not promoted or deployed.

## Provenance and integrity

- [MEASURED: runner @ `64b837e`] Protocol SHA256:
  `ef7e00a98e51cb7d407d0d79c08cda13d8efdb8d76a1943e23dcaad924bb4167`.
- [MEASURED: `python backtest/verify_data.py` @ `64b837e`]
  `verified 46 OK, 0 missing, 0 mismatched`.
- [MEASURED: runner @ `64b837e`] Default regression: 9 identical, 0 failed.
- [MEASURED: `python backtest/test_reclaim_entry_3r.py` @ `64b837e`]
  6 synthetic checks passed.
- [MEASURED: independent JSON audit @ `64b837e`] 22 result-consistency checks
  passed.
- [MEASURED: `Get-FileHash` @ `64b837e`] Result artifact SHA256:
  `85171635c5acad53cf48e799b80cb5d2e5188451fa1e3d13e6c95e1151b8e658`.
- [MEASURED: runner @ `64b837e`] Working ledger 212 -> 213; one charged cell.
- [MEASURED: runner @ `64b837e`] Confirmation accessed: false; blind holdout
  accessed: false; FTMO MC paths: 0; terminal writes: 0.

## Pooled results

| Cell/frame | n | Net win rate | Expectancy | Total R |
|---|---:|---:|---:|---:|
| C0 passive 3R, all | 3,593 | 33.3148% | −0.040533R | −145.634372R |
| R1 reclaim 3R, all | 1,793 | 33.6866% | −0.006000R | −10.758592R |
| C0 passive 3R, stitched OOS | 1,074 | 34.0782% | −0.033880R | −36.387618R |
| R1 reclaim 3R, stitched OOS | 535 | 35.5140% | +0.024971R | +13.359420R |
| R1 minus C0, stitched OOS | −539 | +1.4358 pp | +0.058851R | +49.747038R |

All source-cell values are [MEASURED: registered runner @ `64b837e`]. Delta
values are [DERIVED] exact candidate-minus-control arithmetic recorded by the
runner. [MEASURED] R1 retained 49.8138% of C0 stitched-OOS trades.

## Stitched-OOS symbol cells

| Symbol | C0 n | C0 win | C0 exp | C0 total R | R1 n | R1 win | R1 exp | R1 total R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Wall Street 30 | 368 | 32.6087% | −0.058213R | −21.422414R | 178 | 33.7079% | −0.008735R | −1.554821R |
| US Tech 100 | 354 | 34.1808% | −0.006543R | −2.316202R | 189 | 34.3915% | +0.021634R | +4.088759R |
| Japan 225 | 352 | 35.5114% | −0.035935R | −12.649002R | 168 | 38.6905% | +0.064437R | +10.825481R |

Every value is [MEASURED: registered runner @ `64b837e`].

## Stitched-OOS quarter cells

| Quarter | C0 n | C0 win | C0 exp | C0 total R | R1 n | R1 win | R1 exp | R1 total R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025Q4 | 381 | 31.4961% | −0.088032R | −33.540236R | 200 | 38.0000% | +0.093544R | +18.708793R |
| 2026Q1 | 352 | 36.6477% | +0.012632R | +4.446573R | 180 | 35.5556% | +0.048315R | +8.696789R |
| 2026Q2 | 331 | 33.5347% | −0.046489R | −15.387732R | 149 | 31.5436% | −0.111645R | −16.635170R |
| 2026Q3 partial | 10 | 60.0000% | +0.809378R | +8.093778R | 6 | 50.0000% | +0.431501R | +2.589007R |

Every value is [MEASURED: registered runner @ `64b837e`]. The complete-quarter
gate covers 2025Q4, 2026Q1, and 2026Q2; the partial 2026Q3 cell is reported but
not gated.

## Reclaim enumeration diagnostics

| Scope | Signals | Trade-throughs | Reclaim pass | Reclaim reject | Unfilled | Trades |
|---|---:|---:|---:|---:|---:|---:|
| Wall Street 30 | 1,819 | 1,279 | 635 | 644 | 540 | 635 |
| US Tech 100 | 1,836 | 1,246 | 599 | 647 | 590 | 599 |
| Japan 225 | 1,765 | 1,142 | 559 | 583 | 623 | 559 |
| Pooled | 5,420 | 3,667 | 1,793 | 1,874 | 1,753 | 1,793 |

Every value is [MEASURED: registered runner @ `64b837e`]. [DERIVED] The pooled
immediate-reclaim pass rate conditional on trade-through was 48.8956%.

## Gate table

| Gate | Result |
|---|---|
| OOS win-rate lift >=5.00 pp | **FAIL** (+1.4358 pp) |
| OOS expectancy >0 | PASS (+0.024971R) |
| OOS expectancy not below C0 | PASS |
| Every symbol OOS expectancy >0 | **FAIL** (Wall Street 30 −0.008735R) |
| Every complete OOS quarter >0 | **FAIL** (2026Q2 −0.111645R) |
| OOS trade retention >=35% | PASS (49.8138%) |
| Default regression and synthetic tests | PASS |
| Win rate >80% diagnostic | false (35.5140%) |

Gate results are [MEASURED: registered runner @ `64b837e`].

## Interpretation

[DERIVED] Immediate reclaim removed roughly half the trades and substantially
improved average OOS R, which supports the adverse-selection mechanism. It did
not reliably identify winners: the win-rate change was small, one symbol stayed
negative, and the most recent complete quarter was materially negative.

[HYPOTHESIS] A smoother-impulse/FIP entry gate remains a distinct next research
idea, but combining it with reclaim after seeing this result would be post-hoc.
It requires its own hashed specification and trial charge. No aspect of R1 is
authorized for the EA.

