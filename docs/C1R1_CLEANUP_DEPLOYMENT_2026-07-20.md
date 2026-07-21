# v1.33-C1r1 cleanup deployment record (2026-07-20)

**Owner instruction:** "clean up the AI slop and inferior codes used in C1."
**Method:** 67-agent audit (5 dimensions over all 3,466 lines) with adversarial
behavior-preservation verification of every proposed edit; only CONFIRMED
A-inert (33 findings) and B-telemetry (22) edits applied — 28 canonical items
after dedup (full ledger: backtest/_c1_cleanup_findings.json; PR #58, compile
0 errors / 0 warnings). NO input renamed/removed; NO trading semantics touched.
14 behavior-affecting items -> owner decision list (below). 2 audit claims
REJECTED by verifiers; sendMarket-race defect confirmed already-RESOLVED
(v1.32 A6 bounded retry).

**Deployed artifacts:** MQ5 f1bd9a60...daac4a (169,169 B), EX5
7170c6b8...4a81c0 (146,312 B).

## Journal (2026-07-20)
| Time | Action | Result |
|---|---|---|
| 23:20:39 | Flat gate | 0 positions, 0 orders, bal=eq=99,521.94 |
| 23:20:39 | Backup live C1 -> backtest/deploy_backups/v133-c1-before-c1r1-20260720-232039/ | hashes match original C1 artifacts (f22b2b50/ec40230e) |
| 23:20:43 | PID-targeted graceful close (taskkill /PID 5548, no /F) | stopped in 12s; Deriv terminal verified still running (runbook amendment applied) |
| 23:20:55 | Replace Experts MQ5/EX5 with C1r1 | in-place hashes verified |
| 23:20:55 | Restart | init 23:21:05: "Panel v1.33-C1r1 ready=yes"; "v1.33-C1r1 ready ... bank 75% @ +1.00R + TP1.50 ... 4 symbols PERIOD_H1 ... 0.30%" - config echo identical to C1 |
| 23:23 | Final health | connected, trade_expert=true, flat, bal=eq=99,521.94 |

## Owner decision list (batch C - NOT applied; each needs its own decision)
1. Config-dead feature blocks (~600 lines total): lock/trail ladder, per-tick
   manager, stop-breakout entry, v1.32 B1-B3 research arms, AVWAP gate,
   Market-Watch scan, raw-points spread cap, hour blackout - keep (flags) or
   strip (feature removal, new version).
2. g_atrHandle machinery (handles created/retried but values unused since
   v1.27) - candidate for removal with care.
3. ConsecutiveLossesToday recomputed O(day-history) every heartbeat -
   incremental counter would change failure modes; perf-only today.
4. W2 filter silently PASSES on broken bar data (high/low <= 0).
5. Halted-day pre-loop returns skip the bar clock -> late mid-bar scans.
6. NEW: news guard checks only SYMBOL_CURRENCY_PROFIT - for USDJPY it watches
   JPY events but is blind to USD events on the base side.
7. NEW: hard-halt latches evaluated only after the g_halted early return
   (ordering nuance).
8. Pending-ATR GV leak on cancel-while-offline (Codex's disclosed debt;
   verifier downgraded cleanup to C).
