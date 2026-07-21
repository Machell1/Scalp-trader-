# v1.33-C1r3 deployment + incident record (2026-07-21)

**Owner instruction:** "do all 13 decision list to make the EA better."
**Shipped:** C13 earlier as C1r2 (news guard both currencies). This record: the
remaining 12 as v1.33-C1r3 (PR #61) + hotfix (PR #62) + the deployment incident.

## The change set (adversarially verified, 5/5 attacks HOLD, compile 0/0)
- Fixes: C11 W2 skips on broken bar data; C12 bar clock always consumed
  (gates in-loop; no stale mid-bar scans); C14 hard-halt latches hoisted;
  C10 ConsecutiveLossesToday memoized (exact invalidation on day/deals/positions).
- Removals (config-dead, 507 lines, 13 inputs, 6 functions): AVWAP gate, hour
  blackout, raw-points cap, Market-Watch scan, stop-breakout + pending trail,
  lock/trail ladder, per-tick manager, g_atrHandle machinery. B1/B2/B3 research
  arms preserved. C1/C2/C3/C5-C9 thereby executed as removals; C4 preserved by
  design.

## INCIDENT: OnInit hedging-race left the EA detached from its chart
1. 09:27:33 first C1r3 restart: the v1.30-era OnInit hard-refuse read
   ACCOUNT_MARGIN_MODE before account sync (LOGIN syncs first), saw netting on
   the hedging account, refused init -> **MT5 detached the EA from its chart**
   and subsequent chart saves persisted the EA-less state. Latent since v1.30
   (race won 3 of 4 prior restarts).
2. Diagnosis chain: no init line -> chart sweep revealed the true host was
   **Default\chart04.chr (BTCUSD)** - chart numbering had shifted days earlier;
   every deploy script's "chart01" assumption was stale (backups of chart01
   were backups of a US30 chart, not the EA host).
3. **Hotfix (PR #62):** hedging check deferred to the first g_ledgerValid
   heartbeat (v1.29.1 pattern) - synced hedging -> entries enabled; synced
   netting -> entries blocked loudly, management still runs. Init never
   hard-refuses on unsynced data again.
4. **Chart recovery:** restored chart04.chr from the hash-verified 07-18
   pre-A1 backup (69f17b74..., expert block + stored inputs: whitelist quartet,
   MomATR 2.0, EntryMode pullback, risk 0.3, clusters, magic 771025).
   EA-less chart files preserved as evidence in deploy_backups/.
5. 09:42:44 verified healthy: "MomentumPullbackEA v1.33-C1r3 ready ... bank 75%
   @ +1.00R + TP1.50/time. Scanning 4 symbols on PERIOD_H1. Base risk=0.30%;
   USDJPY risk=0.05%"; panel ready; ledger sane; flat (99,521.94); deferred
   hedging check passed silently (no ENTRIES-DISABLED line). Zero market
   exposure throughout (account flat the entire window).

## Runbook amendments (binding)
- **Locate the EA host chart BY CONTENT** (grep profiles for the expert name),
  never by assumed chart number; back up THAT file pre-deploy.
- After any deploy restart, POSITIVE verification = the new version's init
  line in the expert log; absence of errors is not success (the 09:27 failure
  was silent except one line).
- OnInit must never hard-refuse on unsynced account data; defer to synced
  heartbeat (now enforced in code).

## Operator action item (from the C1r2 warning, working as designed)
09:00:03: "CalendarValueHistory failed for USD (err 5035) - news guard
INOPERATIVE". The FTMO terminal appears to serve no economic-calendar data ->
the news guard has likely been silently inoperative in EVERY prior version;
the new warning made it visible. Options: enable the calendar in the terminal
(if available for FTMO-Demo) or accept the guard as inoperative and treat
news exposure as unmitigated (as it factually always was).
