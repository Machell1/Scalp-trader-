# MomentumPullbackEA v1.33-C1 FTMO deployment report

Date: 2026-07-18 UTC / 2026-07-17 America/Bogota.

## Release decision

[MEASURED: `python backtest/verify_data.py` @ `b7716615`] The pinned-data gate
reported verbatim: `verified 46 OK, 0 missing, 0 mismatched`.

[MEASURED: corrected result assertions against
`backtest/v133_c1_headtohead_results.json` @ `b7716615`] The frozen 100,000-path
confirmation measured a 76.823% modeled both-phase pass rate for v1.31 and
88.274% for v1.33-C1. The v1.33-C1 Wilson lower bound was 88.1056%; hard-halt
probability was 0.2660% with a 0.2942% Wilson upper bound. The paired point
improvement was +11.4510 percentage points and the conservative paired lower
bound was +11.0265 points. Verdict: `C1_CONFIRMED_BEATS_V131`.

[MEASURED: `gh pr view 47` @ `b7716615`] PR #47 was merged to protected
`main` as merge commit `b7716615db1d5c7c7bf085317f91f2e082ed6998` at
2026-07-18T02:35:06Z.

## Build and artifact identity

[MEASURED: FTMO `MetaEditor64.exe /compile` @ `b7716615`] The canonical merged
source compiled with `Result: 0 errors, 0 warnings, 12953 ms elapsed,
cpu='X64 Regular'`.

[MEASURED: `Get-FileHash -Algorithm SHA256` @ `b7716615`] Merged/deployed MQ5
SHA256: `f22b2b502b34db83e14646366ea210fc69d5f031d9a71d41db0d6e107a0fab8d`.
Merged/deployed EX5 SHA256:
`ec40230e53faa40556f6e7922b17e2533c146edffbd0d6db3dc357aed036f408`.
The deployed EX5 length was 142,754 bytes.

## Pre-deployment live gate

[MEASURED: explicit-path MetaTrader5 read-only query @ `b7716615`] The target
was account 1513946641 on `FTMO-Demo`, terminal build 5836, connected and trade
enabled. Balance and equity were both 99,521.94; margin was 0.00. The account
had 0 positions and 0 pending orders. The flat gate passed before any terminal
write.

## Terminal-write journal

All actions below targeted only the FTMO data folder
`81A933A9AFC5DE3C23B15CAB19C63850`. No order was placed, modified, or closed;
no chart input was manually edited; no terminal setting was changed.

1. [MEASURED: `Copy-Item` and SHA256 verification @ `b7716615`,
   2026-07-17T21:37:15-05:00] Copied the live v1.31 MQ5, EX5, and chart profile
   to the rollback folder
   `backtest/deploy_backups/v131-before-v133-c1-20260717-213715/`. The backup
   hashes were MQ5
   `0c6d42e3cb2ed896ffc44664aee5c4f68d4f19207811b32cd93c81982107ea13`,
   EX5 `d8a58e10f0f3edd4a06e8c67469b2147f6229fd6e7940ee806aa917961dd8a6b`,
   and chart `a4f8a2b7db1793ad82857e71f24b6d3b58df44be077840c7b87cfd2b713152be`.
2. [MEASURED: `CloseMainWindow` plus terminal journal @ `b7716615`,
   2026-07-17T21:37:17-05:00] Requested a graceful close of FTMO terminal PID
   17048. The terminal removed the old expert, exited with code 0, and shut
   down cleanly. No process kill was used.
3. [MEASURED: `Copy-Item` plus source/destination SHA256 comparison @
   `b7716615`] Replaced only
   `MQL5/Experts/MomentumPullbackEA.mq5` and
   `MQL5/Experts/MomentumPullbackEA.ex5`. Both live hashes matched the merged
   artifacts byte for byte.
4. [MEASURED: `Start-Process` plus terminal journal @ `b7716615`,
   2026-07-17T21:37:54-05:00] Started the same FTMO terminal executable hidden.
   The replacement expert loaded successfully on `BTCUSD,H1`.

## Post-deployment verification

[MEASURED: FTMO Expert log @ `b7716615`, 2026-07-17T21:38:04-05:00] The risk
ledger restored with day-start balance 99,521.94, day PnL 0.00, fills today 0,
peak equity 100,447.83, initial balance 100,000.00, and both halt flags `no`.

[MEASURED: FTMO Expert log @ `b7716615`, 2026-07-17T21:38:04-05:00] The panel
reported `Panel v1.33-C1 initialized: requested=yes ready=yes`. CandleParity
lines were printed for all 4 admitted symbols: `US30.cash`, `US100.cash`,
`JP225.cash`, and `USDJPY`.

[MEASURED: FTMO Expert log @ `b7716615`, 2026-07-17T21:38:04-05:00] The live
initialization line was:

`MomentumPullbackEA v1.33-C1 ready. Entry=PULLBACK(limit). Exits=bank 75% @ +1.00R + TP1.50/time. ManageOnBarClose=yes. Scanning 4 symbols on PERIOD_H1. Base risk=0.30%; USDJPY risk=0.05%. v1.32 arms: exit=bracket stopEval=touch (defaults OFF = v1.31 behavior).`

[MEASURED: explicit-path MetaTrader5 read-only query @ `b7716615`] After load,
the terminal was connected to account 1513946641 on `FTMO-Demo`, algorithmic
trading was enabled, and the account still had 0 positions and 0 pending
orders.

## Verdict

DEPLOYED AND HEALTHY. [DERIVED from the build, artifact, log, account, and
flat-state evidence above.] The modeled pass rate is not a promise of a future
challenge result; forward demo execution is the remaining live validation.
