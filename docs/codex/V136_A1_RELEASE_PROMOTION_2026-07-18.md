# MomentumPullbackEA v1.36-A1 release-promotion record

Date: 2026-07-18.

Status: **READY FOR OWNER-AUTHORIZED RELEASE; NOT YET DEPLOYED**.

## Decision evidence

- [MEASURED: merged research PR #49 @ `b6981d2`] The protected-main merge
  contains the preregistered specification, corrected-fidelity runner, complete
  result JSON, report, and archived candidate source.
- [MEASURED: SHA256 @ `b6981d2`] The archived candidate source
  `mql5/MomentumPullbackEA_v136_A1.mq5` is unchanged at
  `397ece9d1c8b841bbe3ed763ef2a6d8ddb3cd207f9ea69244d8857f162feef82`.
- [MEASURED: registered 100,000-path confirmation @ `e3461c2`] v1.36-A1
  modeled both-phase pass was 90.9940% versus 88.9020% for the paired
  v1.33-C1 control. The conservative paired lower bound was +1.7366
  percentage points, A1 hard halt was 0.0350%, and verdict was
  `A1_CONFIRMED_BEATS_V133_C1`.
- [MEASURED: same confirmation @ `e3461c2`] The cost of the improvement was
  lower opportunity frequency: 395 filled entries versus 987, and modeled
  median successful completion increased from 499 to 978 days.

## Canonical promotion

- [MEASURED: Git diff @ `0449218`] The only executable strategy change
  in `mql5/MomentumPullbackEA.mq5` is the versioned input
  `InpMomentumAtrMultV136 = 3.0`, replacing the v1.33-C1 default of 2.0 ATR.
  The rename prevents MT5 chart persistence from silently retaining 2.0.
- [MEASURED: Git diff @ `0449218`] H1 timing, the four-symbol universe,
  W2 0.30-ATR predicate, 0.6-ATR pullback limit, pending semantics, stop,
  75% bank at +1R, 1.5-ATR final target, eight-bar exit, 0.30%/0.05% risk,
  cluster seats, magic 771025, and broker comment `MomPullback` are unchanged.
- [MEASURED: Git diff @ `0449218`] Other edits are release/version text,
  panel identity, and a startup-field print of `MomATR>=3.00` for post-restart
  proof. The archived candidate file remains byte-for-byte unchanged.

## Release verification

- [MEASURED: `python backtest/verify_data.py` @ `0449218`] Output
  verbatim: `verified 46 OK, 0 missing, 0 mismatched`.
- [MEASURED: deterministic legacy tape regression @ `0449218`] The
  default path reproduced 1,645 trades, 7,317 events, and SHA256
  `3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f`.
- [MEASURED: deterministic explicit tape regression @ `0449218`] The
  2.0-ATR control reproduced 1,684 trades, 7,145 events, and SHA256
  `b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187`;
  A1 reproduced 662 trades, 2,819 events, and SHA256
  `3c38f90cf3b36de09718eca8fb5796fb154a589ba514254e71ce6ee87b70c573`.
- [MEASURED: synthetic checks @ `0449218`] Pass policy passed 10/10,
  risk policy passed 16/16, and parity hooks passed 9/9.
- [MEASURED: FTMO MetaEditor compile @ `0449218`] The canonical source
  compiled with `Result: 0 errors, 0 warnings, 18448 ms elapsed,
  cpu='X64 Regular'`.
- [MEASURED: SHA256 @ `0449218`] Pre-merge canonical source SHA256 was
  `531d2a8b305e145241d00b9db11f716b49f1d90f190914046ce7b7cdae02b833`;
  the fresh 142,982-byte EX5 SHA256 was
  `078f09d9e4955cce98b1f88ee986f9b0da6b8679cc1af9171fb02e1e90e288f4`.

One verification wrapper printed the passing legacy regression and then
failed with `KeyError: 'events_sha256'` because the wrapper used the wrong
return-field label. [MEASURED: corrected deterministic command @ `0449218`]
The subsequent control/A1 assertions completed successfully. No
Monte Carlo was rerun, no dataset changed, and no terminal write occurred.

## Live preflight before promotion PR

- [MEASURED: explicit-path MetaTrader5 query at
  `2026-07-18T18:13:45-05:00`] The target was login 1513946641 on
  `FTMO-Demo`, terminal build 5836, connected with algorithmic trading
  allowed. Balance and equity were 99,521.94, margin was 0.00, and the account
  had zero positions and zero pending orders.
- [MEASURED: live artifact audit at the same preflight] The running EA was
  v1.33-C1. Its MQ5 SHA256 was
  `f22b2b502b34db83e14646366ea210fc69d5f031d9a71d41db0d6e107a0fab8d`;
  its EX5 SHA256 was
  `ec40230e53faa40556f6e7922b17e2533c146edffbd0d6db3dc357aed036f408`.

No MT5 file, chart, input, order, position, or process was changed during this
promotion record. Deployment requires a fresh flat-state check, rollback
backup, graceful close, merged-artifact hash verification, restart, and full
post-load health verification.
