# MomentumPullbackEA v1.36-A1 FTMO deployment report

Date: 2026-07-18 America/Bogota.

## Release decision

- [MEASURED: registered confirmation @ `e3461c2`] The corrected-fidelity
  100,000-path head-to-head measured 90.9940% modeled both-phase pass for
  v1.36-A1 versus 88.9020% for paired v1.33-C1. The conservative paired lower
  bound was +1.7366 percentage points, A1 hard halt was 0.0350%, and verdict
  was `A1_CONFIRMED_BEATS_V133_C1`.
- [MEASURED: same confirmation @ `e3461c2`] A1 retained 395 filled entries
  versus 987 for C1 and increased modeled median successful completion from
  499 to 978 days. The modeled pass rate is not a guarantee of a future
  challenge outcome.
- [MEASURED: GitHub @ `b6981d2`] Research PR #49 merged the preregistered
  evidence into protected `main`.
- [MEASURED: GitHub @ `a796c74`] Release PR #51 passed CodeRabbit and merged
  the canonical v1.36-A1 source into protected `main` as
  `a796c74645fd78b5eb542d44c4804808cdbccee8`.

## Exact merged build

- [MEASURED: `python backtest/verify_data.py` @ `a796c74`] Output verbatim:
  `verified 46 OK, 0 missing, 0 mismatched`.
- [MEASURED: Git blob comparison @ `a796c74`] The filtered working-tree blob
  and `origin/main:mql5/MomentumPullbackEA.mq5` were both
  `23e8aab4c278044e65360f56cf3074bd9425965e`.
- [MEASURED: FTMO MetaEditor @ `a796c74`] The exact merged canonical source
  compiled with `Result: 0 errors, 0 warnings, 13917 ms elapsed,
  cpu='X64 Regular'`.
- [MEASURED: SHA256 @ `a796c74`] Merged/deployed MQ5 SHA256:
  `531d2a8b305e145241d00b9db11f716b49f1d90f190914046ce7b7cdae02b833`.
  Fresh merged/deployed EX5 SHA256:
  `f5005255407ca95df907d69483833239f7b0e208ffb2bbcd2e4e3ebd6f6a3f3d`;
  EX5 length was 143,504 bytes.

## Immediate pre-write flat gate

- [MEASURED: explicit-path MetaTrader5 query @
  `2026-07-18T18:38:26-05:00`] The target was account 1513946641 on
  `FTMO-Demo`, terminal build 5836, connected and trading allowed. Balance and
  equity were both 99,521.94, margin was 0.00, and there were zero positions
  and zero pending orders.
- [MEASURED: process audit at the same gate] The only running MT5 process was
  PID 15880 at
  `C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe`.

## Rollback artifacts

- [MEASURED: backup before terminal close @ `a796c74`] The live v1.33-C1
  artifacts and chart were copied to
  `backtest/deploy_backups/v133-c1-before-v136-a1-20260718-183826/` and mirrored
  into the prior research worktree's deployment-backup directory.
- [MEASURED: SHA256 @ backup time] v1.33-C1 MQ5:
  `f22b2b502b34db83e14646366ea210fc69d5f031d9a71d41db0d6e107a0fab8d`;
  v1.33-C1 EX5:
  `ec40230e53faa40556f6e7922b17e2533c146edffbd0d6db3dc357aed036f408`;
  pre-close chart:
  `69f17b7429779d0d2ad3d8bd0b7f843516b12c04361995ba6bc289ed4ef53474`;
  post-graceful-close chart:
  `792401bc0b2b18ee9a9e06b208c029d0681ec87db66a7aaa668ff86627ab80ab`.

## Terminal-write journal

All writes targeted only FTMO data folder
`81A933A9AFC5DE3C23B15CAB19C63850`. No order was placed, modified, or closed;
no chart input or terminal setting was edited.

1. [MEASURED: `CloseMainWindow` @ `2026-07-18T18:39:39-05:00`] Requested a
   graceful close of FTMO PID 15880. The terminal log recorded expert removal
   at 18:39:41 and disconnection at 18:39:47; the process exited by 18:39:48.
   No process kill was used.
2. [MEASURED: post-close backup @ `2026-07-18T18:39:48-05:00`] Preserved the
   chart saved by the graceful shutdown before replacing either EA artifact.
3. [MEASURED: `Copy-Item` plus SHA256 @ `a796c74`] Replaced only
   `MQL5/Experts/MomentumPullbackEA.mq5` and
   `MQL5/Experts/MomentumPullbackEA.ex5`. Both destination hashes matched the
   exact merged artifacts byte for byte.
4. [MEASURED: `Start-Process` @ `2026-07-18T18:39:50-05:00`] Restarted the
   same FTMO terminal executable hidden as PID 2700. The terminal log recorded
   `expert MomentumPullbackEA (BTCUSD,H1) loaded successfully` at 18:39:59 and
   authorization on `FTMO-Demo` at 18:40:00.

## Post-deployment health

- [MEASURED: Expert log @ `2026-07-18T18:40:03-05:00`] The risk ledger
  restored with day-start balance 99,521.94, day PnL 0.00, fills today zero,
  peak equity 100,447.83, initial balance 100,000.00, and both halt flags `no`.
- [MEASURED: Expert log @ `2026-07-18T18:40:06-05:00`] The panel reported
  `Panel v1.36-A1 initialized: requested=yes ready=yes`.
- [MEASURED: same Expert log] CandleParity printed for all four admitted
  symbols: `US30.cash`, `US100.cash`, `JP225.cash`, and `USDJPY`.
- [MEASURED: same Expert log] The live initialization line was:

  `MomentumPullbackEA v1.36-A1 ready. Entry=PULLBACK(limit). MomATR>=3.00. Exits=bank 75% @ +1.00R + TP1.50/time. ManageOnBarClose=yes. Scanning 4 symbols on PERIOD_H1. Base risk=0.30%; USDJPY risk=0.05%. v1.32 arms: exit=bracket stopEval=touch (defaults OFF = v1.31 behavior).`

- [MEASURED: explicit-path MetaTrader5 query @
  `2026-07-18T18:41:42-05:00`] The terminal was connected to login 1513946641
  on `FTMO-Demo`, algorithmic trading was enabled, balance and equity were
  99,521.94, margin was 0.00, and the account still had zero positions and
  zero pending orders.
- [MEASURED: process/file audit at the same snapshot] PID 2700 was responsive
  on the exact FTMO executable path; the live MQ5 and EX5 hashes remained
  byte-identical to the merged artifacts.

## Verdict

**DEPLOYED AND HEALTHY.** [DERIVED from the protected merge, exact build,
flat-state gates, rollback backup, artifact hashes, Expert log, process state,
and post-restart account query.] Forward demo execution remains the live
validation.
