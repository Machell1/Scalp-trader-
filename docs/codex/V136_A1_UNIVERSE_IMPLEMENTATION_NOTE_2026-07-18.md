# v1.36-A1 universe study: outcome-free implementation note

Date: 2026-07-18

Status: recorded before any real control or candidate tape was built by the new
M15 harness and before any candidate statistic or Monte Carlo path was run.
This note resolves implementation details without changing the two registered
symbols, strategy, risk, gates, path ranges, or trial charge.

- Quarter attribution uses the pending-placement epoch. This is consistent
  with the specification's placement-based lifecycle ownership and prevents a
  signal closing at `23:45` from being assigned to the prior quarter when its
  pending is placed at `00:00` in the new quarter. Placement is the actual next
  observed M15 open, never signal time plus a nominal 15 minutes; this governs
  segment ownership across weekends and session gaps. A missing next open is
  explicitly excluded and counted.
- A W2-passing signal is outcome-blindly excluded when the common right edge
  cannot contain its complete 12-M15 pending window and the worst-case eighth-
  H1 TIME lifecycle, including the actual next observed open after a session
  gap. This prevents shortened cancels/exits and unequal file-edge censoring.
  W2 failures remain predicate rejections and are not counted as censored.
- The quote buffer represents the observed/frozen physical full spread and is
  therefore applied once in both E1 and E2. E2 doubles the charged complete
  round-trip transaction cost; it does not invent a second physical spread for
  trigger geometry. E1 and E2 lifecycle identities must consequently match.
- `CompactRun.summary()` uses the repository's house-standard one-sided 95%
  Wilson bound. The registered `>=0.88` account gate is evaluated against that
  exact lower bound.
- Checkpoints are bound to the complete committed experiment bundle, broker
  metadata, simulator configuration, result dtype, calendar frame, event tape,
  risk policy, bootstrap specification, and path range. Loaded checkpoints are
  rejected unless row count, dtype, and exact path IDs match.
- Python/package versions plus the C# compiler path and hash are recorded. The
  C# kernel source is already part of the committed experiment bundle.
- No swap credit or debit is synthesized because the frozen input does not
  contain venue swap events. This remains a reported transfer limitation.
- `AUS200.cash` retains the registered `0.03 ATR per side` fallback. It is not
  estimated or tuned in this study.

No outcome is recorded in this file.
