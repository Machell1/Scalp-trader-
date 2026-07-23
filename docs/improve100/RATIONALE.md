# IMPROVE-100 rationale index (2026-07-15)

Binding cell definitions live in docs/IMPROVE100_SPEC_2026-07-15.md (hashed).
This file records, per family, the generation provenance and the evidence base
cited by the five generation passes (session 5bf065a7, six parallel agents:
one graveyard auditor with four readers + five family generators).

## Evidence anchors by family
- F filters: volatility-managed momentum (Barroso & Santa-Clara 2015; Moreira
  & Muir 2017); TSMOM (Moskowitz-Ooi-Pedersen 2012); variance ratios (Lo &
  MacKinlay 1988); KER (Kaufman 1995); market-state momentum (Cooper et al.
  2004); dollar factor (Lustig et al. 2011); safe havens (Ranaldo-Soderlind
  2010; Baur-Lucey 2010); carry crashes (Brunnermeier et al. 2008); relative
  strength (Jegadeesh-Titman 1993); announcement microstructure (Ederington-
  Lee 1993); limit-order adverse selection (Handa-Schwartz 1996); round-number
  stops (Osler 2003); S/R content (Osler 2000); short-horizon reversal
  (Jegadeesh 1990); compression-expansion (Crabel 1990); turn-of-month
  (Lakonishok-Smidt 1988; Etula et al. 2020).
- G geometry: corrected-engine fill realism (RETEST 2026-07-12; harvest #1);
  arena pend-4 proxy prior (TOURNAMENT_2026-07-05); Bars() live-window lesson
  (W2_PARITY); plateau doctrine (WFO_SPEC).
- X exits: MAE curves (Sweeney); post-correction exit-book reversal (RETEST);
  drift asymmetry (SMC-gold long-bias finding); harvest-open items #5/#6/#10
  queued in the RETEST addendum with priority order.
- R regime: turn-of-month/quarter-end flow literature; cross-market coupling
  (USDJPY-Nikkei); synchronized-vol liquidation regimes.
- S sizing: FTMO two-phase pass mechanics (H1 account MC); USDJPY sleeve
  admission (+8.21pp) as the family's one lifetime success.

## Forfeit citations
G11: CANDLE_SPEC/CANDLE_INVERSE clv_dir-family closure (inverted sign, 3x).
G13: W2_PARITY Q2 re-place + M2-REPLACE recovery nulls.
X08: cond_hold_study + VPOF conditional-hold fence.
X09: BACKTEST_OBSERVATIONS adaptive_tp do-not-re-propose.
X14: no historical spread series at exit timestamps (unmeasurable honestly).
X17: dominated under E2 by construction (many small wins taxed 2x cost).
X19: VPOF/HIGHWATER trailing-family fence wording.
S03/S10: SUPERVISOR T1a/T1b graded-throttle rejections.
S05/S18: account-MC day-block resampling breaks the within-day/next-day
  clustering these rules exploit — untestable in the registered harness.
S07: V130 "target-chasing band" fence wording.
S11: pre-declared timeout-gate failure (bounds the family without a run).
