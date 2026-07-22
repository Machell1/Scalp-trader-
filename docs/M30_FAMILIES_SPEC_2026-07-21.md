# M30-native signal family discovery — pre-registration (2026-07-21)

**Owner directive:** "30-minute book is something I genuinely want so design it
from scratch with a new signal family designed for 30M." Target: a SECOND book
candidate alongside the live H1 (two own-EAs are FTMO-legal; established
2026-07-12). Nothing deploys from this study — survivors advance through the
era's account gates, then a v1.34-M30 EA build, owner sign-off, forward
validation.

**Graveyard honored (not re-run):** momentum-pullback geometry below H1 (M15,
M30, sliding anchors, H4-anchor — all dead); confirmation filters (5×);
fade direction; SMC/VP/order-flow layers (3×); candle/wick standalones;
entry families F1–F4; ORB-retest; session/VWAP filters on the pullback
signal; gap fade; overnight-short; reclaim/FIP/panic-veto/stop-confirmation/
ADX-first-touch (PRs #24–#28); full-position 1R exit (#23); Kimi re-admissions.

**Three families, six cells (ledger 306 → 312):**

- **F-A session momentum** (external anchor: Gao-Han-Li-Zhou JFE 2018, SPY
  1993-2013 + ETFs/futures; M30 is the construction's native frame).
  Per symbol, cash-open bin self-calibrated (argmax median TR over the 48
  time-of-day bins; sanity-printed). r1 = (close of cash bar 1 − prior cash
  session's last close) / prior last close (includes the overnight gap, per
  the paper). Trade bar = open_bin+12 (6h after open, pre-registered
  simplification of "last half hour").
  **A1:** at the trade bar's open, enter sign(r1); exit at that bar's close.
  **A2:** additionally require sign(r12)==sign(r1), r12 = return over cash
  bars 2..12; else flat. Risk denominator = ATR14(M30) at entry; sized 1R per
  ATR; cost = full spread both sides (E2 currency).

- **F-B compression→expansion.** Squeeze at bar t (inside cash session):
  16-bar true-range sum in its bottom 20% vs the trailing 720 bars AND 16-bar
  range ≤ 2.0×ATR(M30). Arm stops at the 16-bar high/low for 8 bars; first
  touch enters (opposite side cancelled); SL = opposite boundary capped at
  1.5×ATR; bank 50% @ +1R; TP +2R; time exit 16 bars. **B1:** both sides.
  **B2:** long-only.

- **F-C overnight index drift** (documented equity overnight premium; the
  dead overnight-SHORT thesis is the opposite trade). Indices only.
  **C1:** long at the close of cash bar open_bin+12, exit at the next
  session's first-bar open (≤3 calendar days ahead, else skip). **C2:** C1
  gated on prior session net change ≥ 0. GROSS of swap at Stage A with the
  swap debit as a reported column; real swap rates applied before any
  Stage-B claim.

**Stage-A kill gates (tape level, per cell):** pooled E2 (double-cost)
expectancy > 0 full-sample AND stitched-OOS (last 30% quarters) > 0 AND
symbol sign-positivity ≥ 3/4 (F-A/F-B) or 2/3 (F-C, indices only). Report
every cell regardless: n, exp, win, per-symbol, OOS, 4×-cost stress column.
**Stage B (survivors only):** paired 20k account MC vs the deployed C1-H1
control (era gates: hard ≤ 0.37%, paired lower > 0 — evaluated for the
TWO-BOOK configuration, i.e., candidate ADDED to C1-H1 at a pre-registered
0.10% risk sleeve), then 100k confirmation. DSR at the incremented ledger for
any promotion claim.

**Prior stated:** F-A has the best external evidence but tiny per-trade gross
(~0.2-0.3R) against M30 costs (~0.03-0.06R/side) — cost math decides. F-B is
mechanically fresh here; squeeze evidence is practitioner-grade, mixed. F-C
depends entirely on swap drag on CFDs. Honest expectation: 0-2 of 6 survive
Stage A. The frames these cells first touch tonight are discovery frames —
any survivor's confirmatory life happens on the account gates + forward demo.

*Results appended below the hash after runs.*

---
## RESULTS (appended post-run 2026-07-21; protocol hashed pre-run: 6ac24154...)

Data gate passed. Costs measured: E2 cost/side = 0.037-0.039 ATR(M30) on the
US indices, 0.097 JP225, 0.114 USDJPY (the M30 cost problem, quantified).

| cell | n | expE2 | OOS | syms+ | verdict |
|---|---|---|---|---|---|
| A1 session momentum | 2,540 | -0.1622 | -0.1711 | 0/4 | FAIL (costs eat the JFE effect) |
| A2 aligned variant | 1,316 | -0.1918 | -0.1915 | 0/4 | FAIL |
| B1 squeeze both-sides | 8 | -0.41 | - | 1/4 | FAIL (undersampled as registered; any retune = new cell) |
| B2 squeeze long-only | 5 | -0.71 | - | 1/3 | FAIL (same) |
| C1 overnight drift | 1,817 | +0.1059 gross | +0.1507 | 3/3 | Stage-A survive -> **SWAP-NET -0.0915, 0/3 -> FAIL** |
| C2 momentum-gated | 934 | +0.1818 gross | +0.2764 | 3/3 | Stage-A survive -> **SWAP-NET -0.0200 full (OOS +0.1287, 2/3) -> FAIL (full-sample gate)** |

**Measured FTMO swaps (POINTS, read-only):** US30 long -11.27 price/night
(~-0.26 R(M30)), US100 -6.21 (~-0.21), JP225 -8.22 (~-0.13); Friday triple.
Average swap drag on the overnight cells: -0.20 R/trade.

**VERDICT: ROUND 1 NO ADMISSION (0/6). Ledger 306 -> 312.** Key learnings,
paid for honestly: (1) the JFE intraday-momentum effect does not survive this
venue's M30 costs; (2) the overnight equity premium IS present in the data
(+0.18 gross, OOS +0.28) but broker financing confiscates it - the entire
overnight-holding category is closed at M30 scale on this account type, which
also explains why the intraday H1 book is the lone survivor; (3) the squeeze
family was never really tested (definition too strict - 8 trades).

**ROUND 2 QUEUE (each requires its own pre-registration; NOT run tonight to
avoid post-hoc mining):** R2a C2-ex-US30 (JP225+US100 net +0.037/+0.058 - a
symbol-subset hypothesis formed AFTER results = new registration + fresh
frames); R2b Friday-avoidance overnight variant; R2c squeeze re-parameterized
to a testable density (e.g., 40th-percentile compression) as a NEW cell.
