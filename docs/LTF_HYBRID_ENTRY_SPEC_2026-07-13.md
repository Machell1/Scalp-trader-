# LTF hybrid entry reliability — pre-registration (2026-07-13)

## Decision question

Can the validated H1 momentum-pullback edge be transferred to M15 and M5
without destroying expectancy, and can that transfer widen the tradable
universe relative to the live H1 trio+USDJPY book?

## Why H1 beats native M15/M5 (pre-registered mechanism)

Holding bar-count parameters fixed while changing timeframe changes the
*economic* impulse:

| TF | 6-bar lookback wall-clock | Typical ATR scale vs H1 | Cost / 1R |
|---|---|---|---|
| H1 | 6 hours | 1.0× | baseline |
| M15 | 90 minutes | ~0.5× | ~2× worse |
| M5 | 30 minutes | ~0.3× | ~3× worse |

So a "creative" LTF entry must preserve H1 *economic geometry*, not copy bar
counts. Two mechanisms are pre-registered; both keep pullback LIMIT geometry
(the validated entry lever) and v1.30 exits (1ATR stop, 50% @ +1R, TP2, 8-bar
hold in signal-TF bars).

## Arms (report every cell)

1. **H1_NATIVE** — control. Impulse/entry/exit all on H1. Params 6/2.0/W2=0.30/
   pullback 0.6 / pending 3 / hold 8.
2. **M15_NATIVE** — same bar counts on M15 (expected weak; negative control).
3. **M5_NATIVE** — same bar counts on M5 (expected weak; negative control).
4. **M15_CLOCK** — wall-clock scale on M15: lookback 24, pending 12, hold 32;
   ATR(14) stays local; stop/TP in local ATR.
5. **M5_CLOCK** — lookback 72, pending 36, hold 96; local ATR.
6. **HYBRID_H1_M15** — impulse + W2 + ATR risk measured on H1; LIMIT monitored
   and filled on M15 bars for 3 H1 bars (12 M15); exits hold 8 H1 bars of
   wall-clock (32 M15) using the frozen H1 ATR.
7. **HYBRID_H1_M5** — same hybrid with M5 fill (36-bar pending, 96-bar hold).
8. **HYBRID_CONFIRM_M15** — HYBRID_H1_M15 plus one reliability gate: the first
   M15 bar that trades to the limit must also print an *adverse* wick ≥ 0.15
   H1-ATR (contested touch, not a clean spike-through). Mirror for shorts.
9. **HYBRID_CONFIRM_M5** — same confirm on M5.

No other filters. No new indicators. Pullback LIMIT geometry is never replaced
by stop-chase.

## Data / cost / split

* Primary tape: Yahoo proxy H1/M15/M5 for US30, US100, JP225, USDJPY, GER40,
  FRA40, UK100, AUS200, XAUUSD, BTCUSD (research proxy — not gate-grade Deriv).
* Cost per side = `spread_price / signal_ATR` (synthetic Yahoo half-spread
  proxy from fetch). Stress = 2× that cost.
* Chronological final 30% of each series is OOS. Report full + OOS N, exp,
  win%, per symbol and pooled.
* Trade-through fill buffer = 0 (touch fill) for the primary table; append a
  robustness column with buffer = 0.02 × signal ATR on limit fills only.

## Kill / promote

Kill an arm if pooled OOS exp ≤ 0, or if it underperforms H1_NATIVE OOS by
more than 0.05R while also cutting N by >40%. Promote only if:

* Pooled OOS exp ≥ H1_NATIVE OOS − 0.02R (parity with H1),
* ≥ 70% of symbols OOS-positive,
* 2× cost OOS still positive on the pooled set,
* Hybrid arms do not require changing the H1 impulse definition.

EA change (if any) is flag-gated, default OFF for live H1, ON only when the
operator selects M15/M5 working timeframe or an explicit hybrid mode. Ledger
charge: 9 screen cells.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `3320f2889be9b29be944ac9da4c3f36d839f6ced928edc8cdd6b37ee75ae491f`

---

## RESULTS (Yahoo proxy, 2026-07-13 — NOT gate-grade Deriv)

Venue caveat: gate-grade Deriv M15 CSVs were absent from this workspace. Numbers
below use Yahoo H1 (~2y) + M15/M5 (~60d) with FTMO-measured ATR cost fractions.
Treat as mechanism evidence, not a SHIP verdict. Re-run on Deriv before live LTF.

### Negative controls (same bar-counts / local ATR)

| arm | pooled OOS | core OOS | note |
|---|---:|---:|---|
| H1_FTMOCOST | −0.022 | **+0.123** | H1 edge lives in the core book |
| M15_NATIVE | −0.138 | −0.192 | destroyed |
| M5_NATIVE | −0.421 | −0.582 | destroyed |
| M15_CLOCK (local ATR) | −0.315 | −0.510 | wall-clock alone insufficient |
| HYBRID_H1_M15 fill | −0.252 | −0.702 | H1 signal + LTF fill without abs threshold failed |

### Winning mechanism — Structural Absolute Impulse (SAI)

Impulse over wall-clock lookback (24 M15 bars), threshold & geometry in **H1 ATR**,
deeper pullback. Plateau (E1 OOS > 0 and E2 OOS > 0, n≥30):

| cell | E1 OOS | E2 OOS | n | sym+ |
|---|---:|---:|---:|---|
| m=2.0 pb=1.0 w=0.20 | +0.192 | +0.118 | 56 | 6/10 |
| m=2.0 pb=1.0 w=0.30 | +0.168 | +0.087 | 35 | 6/10 |
| **m=2.0 pb=0.8 w=0.30 (chosen)** | **+0.120** | **+0.038** | **41** | **5/10** |
| m=2.0 pb=0.8 w=0.20 | +0.155 | +0.080 | 70 | 6/10 |

Chosen cell keeps W2 wick at 0.30 (live definition) and uses pb=0.8 (not the
most extreme 1.0). Core OOS for chosen cell **+0.261** (n=16) — matches or
exceeds H1 core on the short Yahoo overlap window.

M5 native abs-impulse failed. M5 viability path = **parent M15 signal / M5 fill**
(same SAI geometry); implemented in EA when working TF < M15.

### EA change

`mql5/MomentumPullbackEA.mq5` → **v1.32**. H1 defaults are a no-op (SAI armed
but inactive when work TF == risk TF). Switching `InpTimeframeV131` to M15 or
M5 activates SAI. Stage-A extras (FRA40/XAUUSD) remain **OFF**.

### Promote / kill

Exploratory promote of the **mechanism** (flag-gated, H1-safe). Kill claim of
gate-grade SHIP until re-run on manifest-pinned Deriv data. Ledger: 9 primary
+ follow-up grid cells (Yahoo proxy).
