# v1.33-C1 revert deployment record (2026-07-20)

**Owner instruction:** "revert to C1" (2026-07-20, after the marginal-sleeve
study PR #55 established the frontier {A1 91.0%/979d/395 fills, C1
88.9%/499d/987 fills} with all intermediate mixes dominated by C1).
**Executed by:** the resident (Claude, Fable 5). Canonical source reverted in
PR #56 (main); this record covers the terminal deployment.

## Method: byte-exact artifact restoration
No new code. The deployed files are the exact v1.33-C1 artifacts backed up by
the v1.36-A1 deployment (its recorded pre-replacement hashes), re-verified at
deploy time:
- MQ5 `f22b2b502b34db83e14646366ea210fc69d5f031d9a71d41db0d6e107a0fab8d` (159,649 B)
- EX5 `ec40230e53faa40556f6e7922b17e2533c146edffbd0d6db3dc357aed036f408` (142,754 B)
Source: `Documents\Momentum Pullback EA beta testing\v136-a1-release\backtest\
deploy_backups\v133-c1-before-v136-a1-20260718-183826\`. Canonical
`mql5/MomentumPullbackEA.mq5` on main == the same MQ5 bytes (PR #56).
Chart untouched: C1 reads its own chart-stored input names, unchanged since its
healthy run through 2026-07-18.

## Journal (all times local, 2026-07-20)
| Time | Action | Result |
|---|---|---|
| 22:08:32 | Pre-deploy gate (MT5 read-only) | flat: 0 positions, 0 orders; balance=equity=99,521.94 |
| 22:08:32 | Backup live A1 → `backtest/deploy_backups/v136-a1-before-c1-revert-20260720-220832/` | MQ5 531d2a8b…, EX5 f5005255…, chart pre-close 792401bc… |
| 22:08:34 | Graceful close (`taskkill /IM terminal64.exe`, no /F) | WM_CLOSE delivered; stopped in 3s |
| 22:09:14 | Post-close chart backup | c5656a32… |
| 22:09:14 | Replace Experts MQ5/EX5 with verified C1 bytes | in-place hashes match expected |
| 22:09:14 | Restart FTMO terminal | PID 5548 running |
| 22:09:29 | Init verification (expert log) | `Risk ledger restored: dayStartBal=99521.94 … halted=no hard=no`; `Panel v1.33-C1 initialized: ready=yes`; 4× CandleParity; **`MomentumPullbackEA v1.33-C1 ready. Entry=PULLBACK(limit). Exits=bank 75% @ +1.00R + TP1.50/time. Scanning 4 symbols on PERIOD_H1.`** |
| 22:12 | Final health (MT5 read-only) | connected, trade_expert=true, 0 positions, 0 orders, balance=equity=99,521.94 |

## Deviation disclosed + remediated
`taskkill /IM` broadcast WM_CLOSE to ALL terminal64 processes (PIDs 2700 FTMO
and 3868 — the Deriv terminal), collaterally closing the Deriv FB9A terminal
(guardian/AD_XAU host). Both closes were graceful (state saved). Detected in
the same session; Deriv terminal restarted (PID 15492) and both terminals
verified running. **Runbook amendment: target the graceful close by PID, never
by image name.**

## Effective state
Live book = v1.33-C1: H1, US30/US100/JP225 @ 0.30% + USDJPY @ 0.05%, momentum
≥ 2.0 ATR, W2 0.30, pullback limit 0.6 ATR, bank 75% @ +1R, TP 1.5 ATR, 8-bar
time exit. Modeled (100k paths, corrected fidelity): both-phase 88.902%, hard
halt 0.191%, median completion 499 days, 987 fills/2.5y. No order was placed,
modified, or closed; no chart input or terminal setting edited.
