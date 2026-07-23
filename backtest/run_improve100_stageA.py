"""Stage A of the preregistered IMPROVE-100 screen (2026-07-15).

Spec: docs/IMPROVE100_SPEC_2026-07-15.md (committed + hashed before this file).
Implements the RUN cells of families F (30), G (13), X (19), R (15), H (1).
Family S (sizing) is out of scope here (separate MC harness per spec).

House pattern: run_orderflow_overlay.py (verbatim-extended run_cell loop with
parity assert; within-symbol permutation gates), run_h1_universe_screen.py
(load_symbol broker-meta costs, aggregate_h1_fast, E2 = cost_e1 * 2.0,
OOS = chronological last 30% of bars), session_study.resolve_v130 (exit book).

Statistics (frozen per spec):
  * Overlay cells (F, R, H01, G14): E2 mean-R gap (kept - vetoed); p from
    10,000 within-symbol permutations of the veto flag (P(perm_gap >= obs)).
    Materiality delta for the +-gates = mean_r(kept) - mean_r(all): the change
    in book expectancy from applying the veto ("gap-based equivalent").
  * Variant cells (G geometry, X exits): E2 pooled expectancy delta vs control;
    p from 2,000 day-clustered paired block bootstraps (see boot_p docstring).

Global conventions (frozen before any result was seen):
  * Feature-unavailable => ALLOW: a veto fires only when its feature is
    computable at the signal decision time and the block condition holds.
  * Aux-series alignment: last aux H1 bar whose OPEN epoch <= signal bar OPEN
    epoch.  Both are H1 bars, so that aux bar's close is complete at (or
    strictly before) the signal decision (close of bar i).  Strictly causal.
  * Daily aggregates: built from the raw M15 by UTC calendar day; "completed"
    means the calendar day is strictly earlier than the calendar day of the
    decision epoch (ep[i] + 3600).
  * Tape timestamps are Deriv server time == UTC; "server-day" == UTC day.
  * Trading-day calendars (F27, R01-R06): trading days = distinct tape days of
    the symbol's own H1 series.  "Last trading day of month" uses the month's
    realized calendar - ex-ante knowable market schedule, standard house use.
  * "Actionable signal" (F24 / X11 / X22): side[k] != 0 AND finite watr[k]
    AND watr[k] >= 0.30 (the full pre-entry predicate of the book).
  * G14 "first signal of day": first pending ARMED by the control enumeration
    that server-day (occupied bars cannot arm one, matching live semantics).
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from parity_engine import START, ATR_P, MOM_ATR, prep_symbol
from run_h1_timeframe_screen import run_cell
from run_h1_universe_screen import aggregate_h1_fast, load_symbol, source_path
from scalper_backtest import wilder_atr
from session_study import resolve_v130

HERE = Path(__file__).resolve().parent
META_PATH = HERE / "h1_universe_broker_meta.json"
RESULT_PATH = HERE / "improve100_stageA_results.json"
SPEC_PATH = HERE.parent / "docs" / "IMPROVE100_SPEC_2026-07-15.md"
SPEC_SHA = "562bbffa90df6b05586d748dc96efd2f7e6518d745ca0e49cf163ae62e5c09c8"

SEED = 13020260715
N_PERM = 10_000
N_BOOT = 2_000
FDR_Q = 0.10
MATERIALITY = 0.02
MIN_N = 50

SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
INDEX_SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225")
US_INDEX_SOURCES = ("Wall_Street_30", "US_Tech_100")

# Dollar-basket legs (F09/R07): +1 where USD is base (up = strong dollar).
DOLLAR_LEGS = {"EURUSD": -1, "GBPUSD": -1, "USDCAD": +1,
               "USDCHF": +1, "AUDUSD": -1, "NZDUSD": -1}
# R15 fixed 6-basket, pinned order per the task.
BREADTH6 = ("Wall_Street_30", "US_Tech_100", "Japan_225",
            "Germany_40", "UK_100", "US_SP_500")
# R05 frozen fixed-date holiday list (month, day).
R05_DATES = ((1, 1), (1, 2), (7, 3), (7, 4), (12, 24), (12, 25), (12, 26), (12, 31))


# ---------------------------------------------------------------------------
# spec hash check
# ---------------------------------------------------------------------------
def check_spec_hash() -> str:
    raw = SPEC_PATH.read_bytes().replace(b"\r\n", b"\n")
    marker = b"PRE-REGISTRATION ENDS"
    idx = raw.find(marker)
    if idx < 0:
        return "MARKER_NOT_FOUND"
    end = raw.find(b"\n", idx) + 1
    got = hashlib.sha256(raw[:end]).hexdigest()
    return "MATCH" if got == SPEC_SHA else f"MISMATCH({got})"


# ---------------------------------------------------------------------------
# small numeric helpers
# ---------------------------------------------------------------------------
def epochs(frame: pd.DataFrame) -> np.ndarray:
    dt = pd.to_datetime(frame["time"])
    if getattr(dt.dt, "tz", None) is not None:
        dt = dt.dt.tz_convert("UTC").dt.tz_localize(None)
    return ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy().astype(np.int64)


def true_range(h: np.ndarray, l: np.ndarray, c: np.ndarray) -> np.ndarray:
    pc = np.roll(c, 1)
    pc[0] = c[0]
    return np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))


def roll_pctile(x: np.ndarray, win: int = 500) -> np.ndarray:
    """Percentile of x[t] vs the trailing `win` bars INCLUDING t.
    Requires the full window (else NaN => feature unavailable => allow)."""
    n = len(x)
    out = np.full(n, np.nan)
    if n < win:
        return out
    sw = sliding_window_view(x, win)
    cur = x[win - 1:]
    finw = np.isfinite(sw)
    num = ((sw <= cur[:, None]) & finw).sum(axis=1)
    den = finw.sum(axis=1)
    ok = np.isfinite(cur) & (den > 0)
    out[win - 1:][ok] = 100.0 * num[ok] / den[ok]
    return out


def sma(x: np.ndarray, win: int) -> np.ndarray:
    return pd.Series(x).rolling(win).mean().to_numpy()


def ema(x: np.ndarray, span: int) -> np.ndarray:
    return pd.Series(x).ewm(span=span, adjust=False).mean().to_numpy()


def align_idx(aux_ep: np.ndarray, sig_ep: np.ndarray) -> np.ndarray:
    """Last aux bar with open epoch <= signal bar open epoch (see header)."""
    return np.searchsorted(aux_ep, sig_ep, side="right") - 1


# ---------------------------------------------------------------------------
# traded-symbol container
# ---------------------------------------------------------------------------
class TSym:
    """One traded symbol: E2-prepped SymData + control trades + features."""

    def __init__(self, source: str, meta: dict):
        t0 = time.time()
        self.source = source
        loaded = load_symbol(source, meta)
        self.cost_e1 = loaded.cost_e1
        self.h1 = loaded.h1
        s = prep_symbol(loaded.h1, loaded.cost_e1 * 2.0, source)   # E2 study currency
        s.oos = np.arange(len(loaded.h1)) >= int(len(loaded.h1) * 0.7)
        self.s = s

        # ---- control extraction: verbatim-extended run_cell loop -----------
        rows_ref = run_cell(s, market=False)
        recs, attempts = run_cell_trades_ext(s)
        assert [(t["ep"], t["r"], t["oos"]) for t in recs] == \
               [(int(a), float(b), bool(c)) for a, b, c in rows_ref], \
               f"parity break vs run_cell on {source}"
        self.trades = recs
        self.attempts = np.asarray(attempts, dtype=np.int64)

        # per-trade arrays
        self.ti = np.array([t["i"] for t in recs], dtype=np.int64)
        self.tj = np.array([t["j"] for t in recs], dtype=np.int64)
        self.txb = np.array([t["xb"] for t in recs], dtype=np.int64)
        self.tside = np.array([t["side"] for t in recs], dtype=np.int64)
        self.tentry = np.array([t["entry"] for t in recs], dtype=float)
        self.tr_r = np.array([t["r"] for t in recs], dtype=float)
        self.toos = np.array([t["oos"] for t in recs], dtype=bool)
        self.tep = np.array([t["ep"] for t in recs], dtype=np.int64)
        self.tday = self.tep // 86400
        self.tdec_day = (self.tep + 3600) // 86400     # decision-day (UTC)
        self.ta = s.atr[self.ti]

        # re-resolution parity: the local resolver copy must reproduce r exactly
        for t in recs:
            xb2, r2 = resolve_base(s, t["j"], t["side"], t["entry"], s.atr[t["i"]])
            assert xb2 == t["xb"] and abs(r2 - t["r"]) < 1e-12, \
                f"resolve_base parity break on {source} @ep {t['ep']}"

        # ---- H1 bar-level features ----------------------------------------
        c, o, h, l = s.c, s.o, s.h, s.l
        self.vol = loaded.h1["volume"].to_numpy(float)
        self.tr = true_range(h, l, c)
        self.sma20 = sma(c, 20)
        self.sma200 = sma(c, 200)
        self.atrp = roll_pctile(s.atr, 500)
        self.ema20 = ema(c, 20)
        self.atr22 = wilder_atr(h, l, c, 22)
        fin = np.isfinite(s.watr)
        self.sig_dir = np.where(fin & (s.watr >= 0.30), s.side, 0).astype(np.int64)
        self.logc = np.log(c)
        self.r1 = np.diff(self.logc, prepend=self.logc[0])   # r1[0] = 0

        # H4 aggregates from own H1 (F03): group by epoch//14400
        g = s.ep // 14400
        idx_last = np.flatnonzero(np.r_[g[1:] != g[:-1], True])
        self.h4_end = (g[idx_last] + 1) * 14400            # bar-complete epochs
        self.h4_ema20 = ema(c[idx_last], 20)

        # F20 round-number grid: 10^(floor(log10(median close)) - 2)
        self.round_grid = 10.0 ** (np.floor(np.log10(np.nanmedian(c))) - 2)

        # F28 week-segment ends (gap > 24h == weekend/holiday boundary)
        seg = np.r_[0, np.cumsum(np.diff(s.ep) > 86400)]
        last_of_seg = {}
        for k in range(len(s.ep)):
            last_of_seg[seg[k]] = k
        self.seg_last = np.array([last_of_seg[seg[k]] for k in range(len(s.ep))])

        # X12 end-of-week flat bar: last bar with open <= this week's Fri 20:00 UTC
        d = s.ep // 86400
        wd = (d + 3) % 7                                    # Mon=0..Sun=6
        fri20 = (d - wd + 4) * 86400 + 20 * 3600
        nxt = np.r_[s.ep[1:], np.iinfo(np.int64).max]
        self.eow_flat = (s.ep <= fri20) & (nxt > fri20)
        # X13 Tokyo-close flat bar (JP225): last bar with open <= 06:00 UTC that day
        d06 = d * 86400 + 6 * 3600
        self.tokyo_flat = (s.ep <= d06) & (nxt > d06)

        # ---- trading-day calendar from own H1 tape days (F27, R01-R06) -----
        days = np.unique(d)
        dts = [datetime.fromtimestamp(int(x) * 86400, timezone.utc) for x in days]
        ym = np.array([t.year * 100 + t.month for t in dts])
        td_idx = np.zeros(len(days), dtype=np.int64)
        td_rev = np.zeros(len(days), dtype=np.int64)
        for key in np.unique(ym):
            m = ym == key
            k = int(m.sum())
            td_idx[m] = np.arange(1, k + 1)
            td_rev[m] = np.arange(k, 0, -1)
        self.cal = {int(days[k]): (int(td_idx[k]), int(td_rev[k]),
                                   dts[k].month, dts[k].day) for k in range(len(days))}

        # ---- raw M15 (F15/F16/F17/F29) --------------------------------------
        raw = pd.read_csv(source_path(source))
        self.m15_ep = epochs(raw)
        self.m15_h = raw["high"].to_numpy(float)
        self.m15_l = raw["low"].to_numpy(float)
        self.m15_c = raw["close"].to_numpy(float)
        self.m15_tr = true_range(self.m15_h, self.m15_l, self.m15_c)
        self.m15_spr = (raw["spread_price"].to_numpy(float)
                        if "spread_price" in raw.columns else None)

        # per-H1-bar mean M15 spread + trailing-20 same-hour median (F15)
        if self.m15_spr is not None:
            pos = np.searchsorted(self.m15_ep, s.ep)
            self.h1_m15sp = np.array([self.m15_spr[p:p + 4].mean() for p in pos])
            hour = (s.ep % 86400) // 3600
            self.f15_med = np.full(len(s.ep), np.nan)
            for hh in np.unique(hour):
                w = np.flatnonzero(hour == hh)
                v = self.h1_m15sp[w]
                for q in range(20, len(w)):
                    self.f15_med[w[q]] = np.median(v[q - 20:q])
        else:
            self.h1_m15sp = None
            self.f15_med = None

        # ---- daily aggregates from M15 by UTC day (F04/F05/F21/R12/H01) ----
        mday = self.m15_ep // 86400
        du, first = np.unique(mday, return_index=True)
        last = np.r_[first[1:], len(mday)] - 1
        self.d_ord = du
        self.d_o = np.array([raw["open"].to_numpy(float)[a] for a in first])
        self.d_c = self.m15_c[last]
        self.d_h = np.array([self.m15_h[first[k]:last[k] + 1].max() for k in range(len(du))])
        self.d_l = np.array([self.m15_l[first[k]:last[k] + 1].min() for k in range(len(du))])

        # G14 first-armed-signal-of-day set (server-day == UTC day)
        att_day = s.ep[self.attempts] // 86400
        _, ai = np.unique(att_day, return_index=True)
        self.first_attempt = set(self.attempts[ai].tolist())

        print(f"  {source}: h1={len(s.c)} trades={len(recs)} attempts={len(self.attempts)} "
              f"cost_e1={loaded.cost_e1:.5f} ({time.time() - t0:.1f}s)", flush=True)


# ---------------------------------------------------------------------------
# control loop (verbatim run_cell + extended record + armed-signal log)
# ---------------------------------------------------------------------------
def run_cell_trades_ext(s):
    out, attempts = [], []
    i = START
    while i < len(s.c) - 1:
        side = int(s.side[i])
        if side == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < 0.30:
            i += 1
            continue
        entry = s.c[i] - 0.6 * s.atr[i] * side
        attempts.append(i)
        j = -1
        for b in range(i + 1, min(i + 4, len(s.c))):
            if (side > 0 and s.l[b] <= entry) or (side < 0 and s.h[b] >= entry):
                j = b
                break
        if j < 0:
            i += 4
            continue
        xb, r = resolve_v130(s, j, side, entry, s.atr[i])
        out.append(dict(i=i, j=j, xb=xb, ep=int(s.ep[i]), fill_ep=int(s.ep[j]),
                        side=side, entry=float(entry), r=float(r), oos=bool(s.oos[i])))
        i = xb + 1
    return out, attempts


# ---------------------------------------------------------------------------
# variant entry loop (G cells): parameterized copy of run_cell
# ---------------------------------------------------------------------------
def run_variant(s, start=START, depth=0.6, window=3, wick=0.30,
                persist=False, cooldown=0):
    """Control loop with one varied knob. Defaults reproduce run_cell exactly
    (asserted in main). No-fill advance = window+1 (control: 3 -> i+=4)."""
    out = []
    n = len(s.c)
    i = start
    while i < n - 1:
        side = int(s.side[i])
        ok = side != 0 and np.isfinite(s.watr[i]) and s.watr[i] >= wick
        if ok and persist:
            ok = i >= 1 and int(s.side[i - 1]) == side   # 2nd-bar anchor (G12)
        if not ok:
            i += 1
            continue
        entry = s.c[i] - depth * s.atr[i] * side
        j = -1
        for b in range(i + 1, min(i + 1 + window, n)):
            if (side > 0 and s.l[b] <= entry) or (side < 0 and s.h[b] >= entry):
                j = b
                break
        if j < 0:
            i += window + 1
            continue
        xb, r = resolve_v130(s, j, side, entry, s.atr[i])
        out.append((int(s.ep[i]), float(r), bool(s.oos[i])))
        i = xb + 1 + cooldown
    return out


def reprep_lookback(s, L: int):
    """Local copy of prep_symbol's momentum computation with lookback L
    (parity_engine is NOT edited).  Returns (s_copy, start_L)."""
    import copy
    s2 = copy.copy(s)
    c, o, h, l, atr = s.c, s.o, s.h, s.l, s.atr
    n = len(c)
    start_l = L + ATR_P + 1
    move = np.full(n, np.nan)
    move[L - 1:] = c[:n - (L - 1)] - c[L - 1:]
    with np.errstate(invalid="ignore", divide="ignore"):
        ma = move / atr
    valid = np.isfinite(atr) & (atr > 0) & (np.arange(n) >= start_l)
    falling = valid & (ma >= MOM_ATR) & (c < o)
    rising = valid & (-ma >= MOM_ATR) & (c > o)
    side = np.zeros(n, dtype=np.int8)
    side[falling] = -1
    side[rising] = 1
    up = h - np.maximum(o, c)
    dn = np.minimum(o, c) - l
    watr = np.full(n, np.nan)
    watr[rising] = up[rising] / atr[rising]
    watr[falling] = dn[falling] / atr[falling]
    s2.side, s2.watr = side, watr
    return s2, start_l


# ---------------------------------------------------------------------------
# X-cell resolvers.  Every one preserves resolve_v130's per-bar ordering:
# stop first, then bank, then TP, then (variant) close-evaluated rules.
# All are re-resolutions from the CONTROL fill (entries frozen per spec).
# ---------------------------------------------------------------------------
def resolve_base(s, j, sd, entry, a, risk=None, tp_r=2.0, hold=8,
                 bank=True, tp_price=None):
    """R-unit generalization of resolve_v130 (identical when risk=a, tp_r=2.0,
    hold=8, bank=True): bank 50% @ +1R then TP tp_r R / SL 1R / hold close."""
    risk = a if risk is None else risk
    sl = entry - risk * sd
    tp = entry + tp_r * risk * sd if tp_price is None else tp_price
    so = entry + 1.0 * risk * sd
    so_done = not bank
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * s.cost * a / risk
    n = len(s.c)
    for k in range(j, min(j + hold, n)):
        if sd > 0:
            if s.l[k] <= sl:
                return k, banked + frac * (sl - entry) / risk - cost_r
            if not so_done and s.h[k] >= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.h[k] >= tp:
                return k, banked + frac * (tp - entry) / risk - cost_r
        else:
            if s.h[k] >= sl:
                return k, banked + frac * (entry - sl) / risk - cost_r
            if not so_done and s.l[k] <= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.l[k] <= tp:
                return k, banked + frac * (entry - tp) / risk - cost_r
    k = min(j + hold - 1, n - 1)
    return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r


def resolve_close_rule(s, j, sd, entry, a, rule, exit_next_open=False, hold=8):
    """Control book + a close-evaluated exit rule.  rule(k, mfe, mae) -> bool,
    evaluated AFTER the intrabar SL/bank/TP checks each bar; exit at c[k]
    (or next open for X02).  mfe/mae are running extremes in R through bar k."""
    risk = a
    sl = entry - risk * sd
    tp = entry + 2.0 * a * sd
    so = entry + 1.0 * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * s.cost * a / risk
    n = len(s.c)
    mfe = mae = 0.0
    for k in range(j, min(j + hold, n)):
        if sd > 0:
            if s.l[k] <= sl:
                return k, banked + frac * (sl - entry) / risk - cost_r
            if not so_done and s.h[k] >= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.h[k] >= tp:
                return k, banked + frac * (tp - entry) / risk - cost_r
        else:
            if s.h[k] >= sl:
                return k, banked + frac * (entry - sl) / risk - cost_r
            if not so_done and s.l[k] <= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.l[k] <= tp:
                return k, banked + frac * (entry - tp) / risk - cost_r
        mfe = max(mfe, ((s.h[k] - entry) if sd > 0 else (entry - s.l[k])) / risk)
        mae = max(mae, ((entry - s.l[k]) if sd > 0 else (s.h[k] - entry)) / risk)
        if rule(k, mfe, mae):
            if exit_next_open and k + 1 < n:
                return k + 1, banked + frac * (s.o[k + 1] - entry) * sd / risk - cost_r
            return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r
    k = min(j + hold - 1, n - 1)
    return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r


def resolve_x03(s, j, sd, entry, a):
    """Fill-depth conditioned: penetration beyond the limit on the fill bar,
    known at close of bar j; if > 0.4*ATR the book becomes TP 1.2R + hold 5
    from bar j+1 (bar j itself resolves under the control book)."""
    pen = (entry - s.l[j]) if sd > 0 else (s.h[j] - entry)
    risk = a
    sl = entry - risk * sd
    so = entry + 1.0 * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * s.cost * a / risk
    n = len(s.c)
    deep = pen > 0.4 * a
    hold = 5 if deep else 8
    for k in range(j, min(j + hold, n)):
        tp = entry + (1.2 if (deep and k > j) else 2.0) * risk * sd
        if sd > 0:
            if s.l[k] <= sl:
                return k, banked + frac * (sl - entry) / risk - cost_r
            if not so_done and s.h[k] >= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.h[k] >= tp:
                return k, banked + frac * (tp - entry) / risk - cost_r
        else:
            if s.h[k] >= sl:
                return k, banked + frac * (entry - sl) / risk - cost_r
            if not so_done and s.l[k] <= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.l[k] <= tp:
                return k, banked + frac * (entry - tp) / risk - cost_r
    k = min(j + hold - 1, n - 1)
    return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r


def resolve_x05(s, j, sd, entry, a):
    """Stagnation tighten: at close of the 4th bar (j+3), if MFE < +0.5R the
    stop tightens to 0.5*ATR from entry (applies from bar j+4 onward)."""
    risk = a
    sl = entry - risk * sd
    tp = entry + 2.0 * a * sd
    so = entry + 1.0 * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * s.cost * a / risk
    n = len(s.c)
    mfe = 0.0
    for k in range(j, min(j + 8, n)):
        if sd > 0:
            if s.l[k] <= sl:
                return k, banked + frac * (sl - entry) / risk - cost_r
            if not so_done and s.h[k] >= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.h[k] >= tp:
                return k, banked + frac * (tp - entry) / risk - cost_r
        else:
            if s.h[k] >= sl:
                return k, banked + frac * (entry - sl) / risk - cost_r
            if not so_done and s.l[k] <= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.l[k] <= tp:
                return k, banked + frac * (entry - tp) / risk - cost_r
        mfe = max(mfe, ((s.h[k] - entry) if sd > 0 else (entry - s.l[k])) / risk)
        if k == j + 3 and mfe < 0.5:
            sl = entry - 0.5 * a * sd
    k = min(j + 8 - 1, n - 1)
    return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r


def resolve_x07(s, j, sd, entry, a):
    """Three-leg ladder: 1/3 @0.75R, 1/3 @1.5R, 1/3 @2.5R; SL 1R; hold 8."""
    risk = a
    sl = entry - risk * sd
    legs = [0.75, 1.5, 2.5]
    filled = [False, False, False]
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * s.cost * a / risk
    n = len(s.c)
    for k in range(j, min(j + 8, n)):
        adverse = s.l[k] if sd > 0 else s.h[k]
        favor = s.h[k] if sd > 0 else s.l[k]
        if (sd > 0 and adverse <= sl) or (sd < 0 and adverse >= sl):
            return k, banked + frac * (sl - entry) * sd / risk - cost_r
        for q, tgt_r in enumerate(legs):
            if filled[q]:
                continue
            tgt = entry + tgt_r * risk * sd
            if (sd > 0 and favor >= tgt) or (sd < 0 and favor <= tgt):
                banked += tgt_r / 3.0
                frac -= 1.0 / 3.0
                filled[q] = True
        if all(filled):
            return k, banked - cost_r
    k = min(j + 8 - 1, n - 1)
    return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r


def resolve_x18(s, j, sd, entry, a):
    """Banked-leg re-entry: after the 50% bank fills at bar kb, one limit at the
    original entry rests for bars kb+1..kb+3; if touched, the banked half
    re-enters (frac 0.5 -> 1.0; +0.5x round-trip cost; bank latch stays done).
    Per-bar order: re-entry limit fill, then SL, then bank, then TP (a falling
    path crosses the limit before the stop -- realistic AND pessimistic)."""
    risk = a
    sl = entry - risk * sd
    tp = entry + 2.0 * a * sd
    so = entry + 1.0 * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    unit_cost = 2.0 * s.cost * a / risk
    cost_r = unit_cost
    n = len(s.c)
    re_from = re_to = -1
    for k in range(j, min(j + 8, n)):
        if re_from <= k <= re_to:
            touched = (s.l[k] <= entry) if sd > 0 else (s.h[k] >= entry)
            if touched:
                frac += 0.5
                cost_r += 0.5 * unit_cost
                re_from = re_to = -1
        if sd > 0:
            if s.l[k] <= sl:
                return k, banked + frac * (sl - entry) / risk - cost_r
            if not so_done and s.h[k] >= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
                re_from, re_to = k + 1, k + 3
            if s.h[k] >= tp:
                return k, banked + frac * (tp - entry) / risk - cost_r
        else:
            if s.h[k] >= sl:
                return k, banked + frac * (entry - sl) / risk - cost_r
            if not so_done and s.l[k] <= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
                re_from, re_to = k + 1, k + 3
            if s.l[k] <= tp:
                return k, banked + frac * (entry - tp) / risk - cost_r
    k = min(j + 8 - 1, n - 1)
    return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r


def resolve_x21(s, j, sd, entry, a):
    """Bar-close stop eval: intrabar stop touches ignored; if a bar CLOSES at or
    beyond the 1R stop the exit fills at the NEXT open.  Bank + TP unchanged
    (intrabar).  Hold-8 time exit unchanged."""
    risk = a
    sl = entry - risk * sd
    tp = entry + 2.0 * a * sd
    so = entry + 1.0 * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * s.cost * a / risk
    n = len(s.c)
    last = min(j + 8, n) - 1
    for k in range(j, last + 1):
        if sd > 0:
            if not so_done and s.h[k] >= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.h[k] >= tp:
                return k, banked + frac * (tp - entry) / risk - cost_r
        else:
            if not so_done and s.l[k] <= so:
                banked += 0.5
                frac -= 0.5
                so_done = True
            if s.l[k] <= tp:
                return k, banked + frac * (entry - tp) / risk - cost_r
        if k < last and (s.c[k] - sl) * sd <= 0:
            if k + 1 < n:
                return k + 1, banked + frac * (s.o[k + 1] - entry) * sd / risk - cost_r
            return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r
    return last, banked + frac * (s.c[last] - entry) * sd / risk - cost_r


def resolve_x22(s, ts, j, sd, entry, a):
    """Uncapped: no TP, no bank; exits on opposite actionable signal at close,
    1R intrabar stop, or the 45-bar cap."""
    risk = a
    sl = entry - risk * sd
    cost_r = 2.0 * s.cost * a / risk
    n = len(s.c)
    last = min(j + 45, n) - 1
    for k in range(j, last + 1):
        if (sd > 0 and s.l[k] <= sl) or (sd < 0 and s.h[k] >= sl):
            return k, (sl - entry) * sd / risk - cost_r
        if ts.sig_dir[k] == -sd:
            return k, (s.c[k] - entry) * sd / risk - cost_r
    return last, (s.c[last] - entry) * sd / risk - cost_r


def resolve_x23(s, ts, j, sd, entry, a):
    """Chandelier trail 3xATR(22) replacing TP on the runner half; 1R bank leg
    kept.  Trail ratchets at bar closes and applies from the NEXT bar intrabar
    (stop-first).  Initial stop = 1R.  45-bar cap (frozen: X22's cap convention
    for unbounded runners; hold-8 would make the trail unreachable).  Gap fills
    at the stop level (house convention, as resolve_v130)."""
    risk = a
    stop = entry - risk * sd
    so = entry + 1.0 * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * s.cost * a / risk
    n = len(s.c)
    last = min(j + 45, n) - 1
    hh = -np.inf
    for k in range(j, last + 1):
        if (sd > 0 and s.l[k] <= stop) or (sd < 0 and s.h[k] >= stop):
            return k, banked + frac * (stop - entry) * sd / risk - cost_r
        if not so_done and ((sd > 0 and s.h[k] >= so) or (sd < 0 and s.l[k] <= so)):
            banked += 0.5
            frac -= 0.5
            so_done = True
        favor = s.h[k] if sd > 0 else -s.l[k]
        hh = max(hh, favor)
        if np.isfinite(ts.atr22[k]):
            cand = (hh - 3.0 * ts.atr22[k]) if sd > 0 else -(hh - 3.0 * ts.atr22[k])
            stop = max(stop, cand) if sd > 0 else min(stop, cand)
    return last, banked + frac * (s.c[last] - entry) * sd / risk - cost_r


def resolve_x24(s, ts, j, sd, entry, a):
    """EMA20-cross exit (close-based) replacing TP on the runner half; 1R bank
    leg kept; 1R intrabar stop; 45-bar cap (same frozen cap as X23)."""
    risk = a
    sl = entry - risk * sd
    so = entry + 1.0 * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * s.cost * a / risk
    n = len(s.c)
    last = min(j + 45, n) - 1
    for k in range(j, last + 1):
        if (sd > 0 and s.l[k] <= sl) or (sd < 0 and s.h[k] >= sl):
            return k, banked + frac * (sl - entry) * sd / risk - cost_r
        if not so_done and ((sd > 0 and s.h[k] >= so) or (sd < 0 and s.l[k] <= so)):
            banked += 0.5
            frac -= 0.5
            so_done = True
        if np.isfinite(ts.ema20[k]) and (s.c[k] - ts.ema20[k]) * sd < 0:
            return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r
    return last, banked + frac * (s.c[last] - entry) * sd / risk - cost_r


# ---------------------------------------------------------------------------
# aux series
# ---------------------------------------------------------------------------
def load_aux(source: str) -> dict:
    raw = pd.read_csv(source_path(source))
    if "spread_price" not in raw.columns:
        raw["spread_price"] = 0.0
    h1 = aggregate_h1_fast(raw)
    ep = epochs(h1)
    c = h1["close"].to_numpy(float)
    h = h1["high"].to_numpy(float)
    l = h1["low"].to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    return dict(ep=ep, c=c, atr=atr, sma200=sma(c, 200),
                atrp=roll_pctile(atr, 500),
                pct_atrp=roll_pctile(np.where(c > 0, atr / c, np.nan), 500),
                logc=np.log(c))


def build_dollar_grid(aux: dict) -> dict:
    """6-leg synthetic dollar factor on the INTERSECTION of the six pairs'
    H1 epochs.  D = cumulative mean signed log return (index level)."""
    eps = None
    for k in DOLLAR_LEGS:
        eps = aux[k]["ep"] if eps is None else np.intersect1d(eps, aux[k]["ep"])
    legs = {}
    for k, sgn in DOLLAR_LEGS.items():
        idx = np.searchsorted(aux[k]["ep"], eps)
        legs[k] = sgn * aux[k]["logc"][idx]
    lc = np.vstack([legs[k] for k in DOLLAR_LEGS])
    ret1 = np.diff(lc, axis=1).mean(axis=0)
    d_level = np.r_[0.0, np.cumsum(ret1)]
    fac6 = np.full(len(eps), np.nan)
    fac6[6:] = lc[:, 6:].mean(axis=0) - lc[:, :-6].mean(axis=0)
    return dict(ep=eps, fac6=fac6, level=d_level, sma200=sma(d_level, 200))


def build_audjpy(aux: dict) -> dict:
    """F13's AUDJPY series.  The spec line says 'synthetic AUDJPY'
    (= AUDUSD x USDJPY), but AUDUSD does not exist on the frozen tape while
    the REAL AUDJPY cross does (derivM15_diverse/AUDJPY.csv).  The real cross
    is economically identical and gives a true-range Wilder ATR(14) instead of
    a close-to-close proxy -- used here and flagged in params/frozen_choices."""
    A = aux["AUDJPY"]
    return dict(ep=A["ep"], c=A["c"], atr=A["atr"])


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def perm_gap_p(r, sym, veto, rng):
    """E2 mean-R gap (kept - vetoed) + one-sided p from N_PERM within-symbol
    permutations of the veto flag (P(perm_gap >= obs), house convention)."""
    kept = ~veto
    nv, nk = int(veto.sum()), int(kept.sum())
    if nv == 0 or nk == 0:
        return None, None
    g_obs = float(r[kept].mean() - r[veto].mean())
    s_v = np.zeros(N_PERM)
    for sname in np.unique(sym):
        m = sym == sname
        rs = r[m]
        k = int(veto[m].sum())
        if k == 0:
            continue
        if k == len(rs):
            s_v += rs.sum()
            continue
        idx = np.argsort(rng.random((N_PERM, len(rs))), axis=1)[:, :k]
        s_v += rs[idx].sum(axis=1)
    tot = r.sum()
    gap_perm = (tot - s_v) / nk - s_v / nv
    p = float((gap_perm >= g_obs - 1e-12).mean())
    return g_obs, p


def boot_p(ctl, var, rng):
    """Paired-by-day block bootstrap of the pooled expectancy delta.
    Estimator: within each symbol, the union of UTC signal-days across both
    arms is resampled with replacement (one draw shared by BOTH arms, so the
    pairing is preserved); each replicate's statistic is
      sum(day R-sums, variant)/sum(day counts, variant)
      - sum(day R-sums, control)/sum(day counts, control)
    pooled across symbols (a full-sample 'draw each day once' reproduces the
    observed trade-pooled delta exactly).  p = fraction of N_BOOT replicates
    with delta <= 0 (one-sided evidence for delta > 0)."""
    vs_tot = np.zeros(N_BOOT)
    vc_tot = np.zeros(N_BOOT)
    cs_tot = np.zeros(N_BOOT)
    cc_tot = np.zeros(N_BOOT)
    for sname in ctl:
        cdays, csum, ccnt = ctl[sname]
        vdays, vsum, vcnt = var[sname]
        days = np.union1d(cdays, vdays)
        D = len(days)
        if D == 0:
            continue
        cs = np.zeros(D)
        cc = np.zeros(D)
        vs = np.zeros(D)
        vc = np.zeros(D)
        cs[np.searchsorted(days, cdays)] = csum
        cc[np.searchsorted(days, cdays)] = ccnt
        vs[np.searchsorted(days, vdays)] = vsum
        vc[np.searchsorted(days, vdays)] = vcnt
        idx = rng.integers(0, D, size=(N_BOOT, D))
        cs_tot += cs[idx].sum(axis=1)
        cc_tot += cc[idx].sum(axis=1)
        vs_tot += vs[idx].sum(axis=1)
        vc_tot += vc[idx].sum(axis=1)
    ok = (cc_tot > 0) & (vc_tot > 0)
    delta_b = np.full(N_BOOT, np.nan)
    delta_b[ok] = vs_tot[ok] / vc_tot[ok] - cs_tot[ok] / cc_tot[ok]
    return float(np.mean(delta_b[ok] <= 0)) if ok.any() else None


def day_table(days: np.ndarray, r: np.ndarray):
    du = np.unique(days)
    dsum = np.zeros(len(du))
    dcnt = np.zeros(len(du))
    pos = np.searchsorted(du, days)
    np.add.at(dsum, pos, r)
    np.add.at(dcnt, pos, 1.0)
    return du, dsum, dcnt


# ---------------------------------------------------------------------------
# overlay veto computation (per traded symbol; returns dict cell -> bool array)
# ---------------------------------------------------------------------------
def overlay_vetoes(ts: TSym, aux: dict, dollar: dict, synja: dict,
                   T: dict) -> dict:
    s = ts.s
    src = ts.source
    ii, sd, ent, a = ts.ti, ts.tside, ts.tentry, ts.ta
    nt = len(ii)
    ep_sig = ts.tep
    dec_day = ts.tdec_day
    c = s.c
    V = {}
    fin = np.isfinite
    is_index = src in INDEX_SOURCES
    is_us = src in US_INDEX_SOURCES
    is_jp = src == "Japan_225"
    is_jpy = src == "USDJPY"

    def aux_at(name):
        A = aux[name]
        t = align_idx(A["ep"], ep_sig)
        return A, t

    # F01 vol ceiling: ATRp > 90
    x = ts.atrp[ii]
    V["F01"] = fin(x) & (x > 90)

    # F02 climax bar: TR(signal) > 3.0 x ATR[i-1]
    atr_prev = np.where(ii >= 1, s.atr[np.maximum(ii - 1, 0)], np.nan)
    V["F02"] = fin(atr_prev) & (ts.tr[ii] > 3.0 * atr_prev)

    # F03 H4 trend align: sign(EMA20_H4 slope over 3 H4 bars) == dir
    t4 = np.searchsorted(ts.h4_end, ep_sig + 3600, side="right") - 1
    ok4 = t4 >= 23
    slope = np.full(nt, np.nan)
    slope[ok4] = ts.h4_ema20[t4[ok4]] - ts.h4_ema20[t4[ok4] - 3]
    V["F03"] = fin(slope) & (np.sign(slope) != sd)

    # daily helpers: index of last COMPLETED day (strictly before decision day)
    dlast = np.searchsorted(ts.d_ord, dec_day, side="left") - 1

    # F04 daily TSMOM align: sign(close_d[y-1] - close_d[y-21]) == dir
    ok = dlast >= 20
    mom = np.full(nt, np.nan)
    mom[ok] = ts.d_c[dlast[ok]] - ts.d_c[dlast[ok] - 20]
    V["F04"] = fin(mom) & (np.sign(mom) != sd)

    # F05 Donchian freshness: extreme of last 20 days printed within last 3
    v = np.zeros(nt, bool)
    for q in range(nt):
        e = dlast[q]
        if e < 19:
            continue
        if sd[q] > 0:
            pos = int(np.argmax(ts.d_h[e - 19:e + 1]))
        else:
            pos = int(np.argmin(ts.d_l[e - 19:e + 1]))
        v[q] = pos < 17          # not within the most recent 3 of the 20
    V["F05"] = v

    # F06 KER(10) >= 0.30
    ker = np.full(nt, np.nan)
    for q in range(nt):
        i0 = ii[q]
        if i0 >= 10:
            num = abs(c[i0] - c[i0 - 10])
            den = np.abs(np.diff(c[i0 - 10:i0 + 1])).sum()
            ker[q] = num / den if den > 0 else np.nan
    V["F06"] = fin(ker) & (ker < 0.30)

    # F07 VR(10) > 1.00 on trailing 250 H1 log returns
    vr = np.full(nt, np.nan)
    for q in range(nt):
        i0 = ii[q]
        if i0 >= 250:
            w = ts.r1[i0 - 249:i0 + 1]
            s10 = np.convolve(w, np.ones(10), mode="valid")
            v1 = w.var()
            if v1 > 0:
                vr[q] = s10.var() / (10.0 * v1)
    V["F07"] = fin(vr) & (vr <= 1.00)

    # F08 benchmark confirm (indices; USDJPY exempt): sign(US500 6-bar) == dir
    v = np.zeros(nt, bool)
    if is_index:
        A, t = aux_at("US_SP_500")
        ok = t >= 6
        m6 = np.full(nt, np.nan)
        m6[ok] = A["c"][t[ok]] - A["c"][t[ok] - 6]
        v = fin(m6) & (np.sign(m6) != sd)
    V["F08"] = v

    # F09 synthetic-dollar gate (USDJPY only): sign(6-leg 6-bar factor) == dir
    v = np.zeros(nt, bool)
    if is_jpy:
        t = align_idx(dollar["ep"], ep_sig)
        ok = t >= 0
        f6 = np.full(nt, np.nan)
        f6[ok] = dollar["fac6"][t[ok]]
        v = fin(f6) & (np.sign(f6) != sd)
    V["F09"] = v

    # F10 risk appetite (US indices): block longs if USDJPY 6-bar < -0.5xATR_JPY
    v = np.zeros(nt, bool)
    if is_us:
        A, t = aux_at("USDJPY_aux")
        ok = t >= 6
        m6 = np.full(nt, np.nan)
        aj = np.full(nt, np.nan)
        m6[ok] = A["c"][t[ok]] - A["c"][t[ok] - 6]
        aj[ok] = A["atr"][t[ok]]
        v = fin(m6) & fin(aj) & (m6 * sd < -0.5 * aj)   # mirrored via *sd
    V["F10"] = v

    # F11 gold safety veto: block risk-dir (longs, all four) when
    # XAUUSD 6-bar > +2.0xATR_XAU.  Risk-dir = long equities / long USDJPY;
    # inherently one-sided (no mirrored short form).
    A, t = aux_at("XAUUSD")
    ok = t >= 6
    m6 = np.full(nt, np.nan)
    ax = np.full(nt, np.nan)
    m6[ok] = A["c"][t[ok]] - A["c"][t[ok] - 6]
    ax[ok] = A["atr"][t[ok]]
    V["F11"] = (sd > 0) & fin(m6) & fin(ax) & (m6 > 2.0 * ax)

    # F12 JP225-yen coupling: JP225 only if sign(USDJPY 6-bar) == dir
    v = np.zeros(nt, bool)
    if is_jp:
        A, t = aux_at("USDJPY_aux")
        ok = t >= 6
        m6 = np.full(nt, np.nan)
        m6[ok] = A["c"][t[ok]] - A["c"][t[ok] - 6]
        v = fin(m6) & (np.sign(m6) != sd)
    V["F12"] = v

    # F13 carry-unwind veto (USDJPY LONGS only, as spec states):
    # synthetic AUDJPY 6-bar < -2.0 x ATR(synthetic, close-to-close Wilder14)
    v = np.zeros(nt, bool)
    if is_jpy:
        t = align_idx(synja["ep"], ep_sig)
        ok = t >= 6
        m6 = np.full(nt, np.nan)
        asy = np.full(nt, np.nan)
        m6[ok] = synja["c"][t[ok]] - synja["c"][t[ok] - 6]
        asy[ok] = synja["atr"][t[ok]]
        v = (sd > 0) & fin(m6) & fin(asy) & (m6 < -2.0 * asy)
    V["F13"] = v

    # F14 cross-index RS: traded index must have the largest |6-bar/ATR| move
    # among the three indices (own sign==dir is implied by the signal itself)
    v = np.zeros(nt, bool)
    if is_index:
        own = np.full(nt, np.nan)
        ok = ii >= 6
        own[ok] = np.abs((c[ii[ok]] - c[ii[ok] - 6]) / s.atr[ii[ok]])
        best = own.copy()
        computable = fin(own)
        for other in INDEX_SOURCES:
            if other == src:
                continue
            A = dict(ep=T[other].s.ep, c=T[other].s.c, atr=T[other].s.atr)
            t = align_idx(A["ep"], ep_sig)
            oko = t >= 6
            z = np.full(nt, np.nan)
            z[oko] = np.abs((A["c"][t[oko]] - A["c"][t[oko] - 6]) / A["atr"][t[oko]])
            computable &= fin(z)
            best = np.fmax(best, z)
        v = computable & (own < best - 1e-12)
    V["F14"] = v

    # F15 spread spike: signal-bar mean M15 spread > 2 x trailing-20 same-hour
    # median (needs 20 prior same-hour observations).  USDJPY has no M15
    # spread series (diverse frame) => feature unavailable => never vetoed.
    v = np.zeros(nt, bool)
    if ts.h1_m15sp is not None:
        cur = ts.h1_m15sp[ii]
        med = ts.f15_med[ii]
        v = fin(cur) & fin(med) & (cur > 2.0 * med)
    V["F15"] = v

    # F16 cost viability: 2 x mean spread(last 4 M15) > 0.10 x ATR (same
    # USDJPY caveat as F15)
    v = np.zeros(nt, bool)
    if ts.h1_m15sp is not None:
        cur = ts.h1_m15sp[ii]
        v = fin(cur) & (2.0 * cur > 0.10 * a)
    V["F16"] = v

    # F17 adverse-selection guard: 0.6xATR > 3.0 x mean M15 TR(8)
    mtr = np.full(nt, np.nan)
    for q in range(nt):
        p = np.searchsorted(ts.m15_ep, ep_sig[q] + 3600)   # bars < decision
        if p >= 9:
            mtr[q] = ts.m15_tr[p - 8:p].mean()
    V["F17"] = fin(mtr) & (0.6 * a > 3.0 * mtr)

    # F18 gap-composed impulse: sum|open gaps| across the signal window
    # (bars i-5..i, the engine's own 6-bar momentum window; 5 internal gaps)
    # >= 0.35 x |engine move c[i]-c[i-5]|
    v = np.zeros(nt, bool)
    for q in range(nt):
        i0 = ii[q]
        if i0 >= 6:
            gaps = np.abs(s.o[i0 - 4:i0 + 1] - c[i0 - 5:i0])
            move = abs(c[i0] - c[i0 - 5])
            v[q] = move > 0 and gaps.sum() >= 0.35 * move
    V["F18"] = v

    # F19 news aftershock: any bar in i-24..i-1 with TR > 4 x ATR@bar
    v = np.zeros(nt, bool)
    for q in range(nt):
        i0 = ii[q]
        lo = max(1, i0 - 24)
        w = slice(lo, i0)
        av = s.atr[w]
        okw = np.isfinite(av)
        v[q] = bool(np.any(ts.tr[w][okw] > 4.0 * av[okw]))
    V["F19"] = v

    # F20 round-number stop guard: stop within 0.10xATR of the round grid
    # (grid = 10^(floor(log10(median close)) - 2): 100 pts indices, 1.00 JPY)
    stop = ent - 1.0 * a * sd
    g = ts.round_grid
    distg = np.abs(stop - g * np.round(stop / g))
    V["F20"] = distg < 0.10 * a

    # F21 room-to-target: prior-day extreme strictly inside the limit->TP path
    v = np.zeros(nt, bool)
    ok = dlast >= 0
    tp_px = ent + 2.0 * a * sd
    ph = np.full(nt, np.nan)
    pl = np.full(nt, np.nan)
    ph[ok] = ts.d_h[dlast[ok]]
    pl[ok] = ts.d_l[dlast[ok]]
    lv = np.where(sd > 0, ph, pl)
    V["F21"] = fin(lv) & ((lv - ent) * sd > 0) & ((tp_px - lv) * sd > 0)

    # F22 structure respect: longs only if limit >= min(low[i-4..i]) (mirror)
    v = np.zeros(nt, bool)
    for q in range(nt):
        i0 = ii[q]
        lo = max(0, i0 - 4)
        if sd[q] > 0:
            v[q] = ent[q] < s.l[lo:i0 + 1].min()
        else:
            v[q] = ent[q] > s.h[lo:i0 + 1].max()
    V["F22"] = v

    # F23 overextension: block longs if close > SMA20 + 3xATR (mirror)
    m20 = ts.sma20[ii]
    V["F23"] = fin(m20) & ((c[ii] - (m20 + 3.0 * a * sd)) * sd > 0)

    # F24 signal freshness: same-dir actionable signal in the prior 8 bars
    v = np.zeros(nt, bool)
    for q in range(nt):
        i0 = ii[q]
        lo = max(0, i0 - 8)
        v[q] = bool(np.any(ts.sig_dir[lo:i0] == sd[q]))
    V["F24"] = v

    # F25 volume climax: signal-bar volume z > 3 vs trailing 100 prior bars
    v = np.zeros(nt, bool)
    for q in range(nt):
        i0 = ii[q]
        if i0 >= 100:
            w = ts.vol[i0 - 100:i0]
            sdv = w.std()
            if sdv > 0:
                v[q] = (ts.vol[i0] - w.mean()) / sdv > 3.0
    V["F25"] = v

    # F26 pre-impulse compression (H1 grain -- the spec's t-17..t-6 window is
    # exactly the 12 bars preceding the 6-bar impulse t-5..t; an M15 reading
    # would place the window inside the impulse, which contradicts the cell
    # name): allow only if mean TR(i-17..i-6) <= 0.90 x ATR[i-6]
    v = np.zeros(nt, bool)
    for q in range(nt):
        i0 = ii[q]
        if i0 >= 18 and np.isfinite(s.atr[i0 - 6]):
            v[q] = ts.tr[i0 - 17:i0 - 5].mean() > 0.90 * s.atr[i0 - 6]
    V["F26"] = v

    # F27 month-turn veto (indices): last + first trading day of month
    v = np.zeros(nt, bool)
    if is_index:
        for q in range(nt):
            cal = ts.cal.get(int(ts.tday[q]))
            if cal is not None:
                v[q] = cal[0] == 1 or cal[1] == 1
    V["F27"] = v

    # F28 weekend truncation: fewer than 3 H1 bars remain to the weekly close
    V["F28"] = (ts.seg_last[ii] - ii) < 3

    # F29 data integrity: M15 grid gap or >2 zero-range bars in the last 24 M15
    v = np.zeros(nt, bool)
    for q in range(nt):
        p = np.searchsorted(ts.m15_ep, ep_sig[q] + 3600)
        if p >= 24:
            w = slice(p - 24, p)
            gaps = np.any(np.diff(ts.m15_ep[w]) != 900)
            zeros = int((ts.m15_h[w] == ts.m15_l[w]).sum())
            v[q] = bool(gaps or zeros > 2)
    V["F29"] = v

    # F30 target congestion: >20 of the last 96 closes within +-0.5xATR of TP
    v = np.zeros(nt, bool)
    for q in range(nt):
        i0 = ii[q]
        if i0 >= 95:
            w = c[i0 - 95:i0 + 1]
            v[q] = int((np.abs(w - tp_px[q]) <= 0.5 * a[q]).sum()) > 20
    V["F30"] = v

    # ---- R family -----------------------------------------------------------
    def cal_row(q):
        return ts.cal.get(int(ts.tday[q]))

    # R01 month-end block (last 2 TD)
    V["R01"] = np.array([bool(cal_row(q) and cal_row(q)[1] <= 2) for q in range(nt)])

    # R02 turn-of-month long window (window = last 1 TD + first 3 TD):
    # longs allowed ONLY inside the window; shorts mirrored (blocked inside)
    in_win = np.array([bool(cal_row(q) and (cal_row(q)[1] == 1 or cal_row(q)[0] <= 3))
                       for q in range(nt)])
    V["R02"] = np.where(sd > 0, ~in_win, in_win)

    # R03 first-week block (TD 1-3)
    V["R03"] = np.array([bool(cal_row(q) and cal_row(q)[0] <= 3) for q in range(nt)])

    # R04 quarter-end block (last 3 TD of Mar/Jun/Sep/Dec)
    V["R04"] = np.array([bool(cal_row(q) and cal_row(q)[1] <= 3
                              and cal_row(q)[2] in (3, 6, 9, 12)) for q in range(nt)])

    # R05 holiday thin-tape block (frozen fixed-date list)
    V["R05"] = np.array([bool(cal_row(q) and (cal_row(q)[2], cal_row(q)[3]) in R05_DATES)
                         for q in range(nt)])

    # R06 JP fiscal half-end USDJPY block (last 3 TD of March and September)
    v = np.zeros(nt, bool)
    if is_jpy:
        v = np.array([bool(cal_row(q) and cal_row(q)[2] in (3, 9) and cal_row(q)[1] <= 3)
                      for q in range(nt)])
    V["R06"] = v

    # R07 dollar-basket confirm (USDJPY, SMA200 regime): longs only if the
    # dollar index level > its SMA200; shorts mirrored
    v = np.zeros(nt, bool)
    if is_jpy:
        t = align_idx(dollar["ep"], ep_sig)
        ok = t >= 0
        lvl = np.full(nt, np.nan)
        m200 = np.full(nt, np.nan)
        lvl[ok] = dollar["level"][t[ok]]
        m200[ok] = dollar["sma200"][t[ok]]
        v = fin(lvl) & fin(m200) & ((lvl - m200) * sd <= 0)
    V["R07"] = v

    # R08 equity risk-on long gate (indices, own SMA200(H1); USDJPY exempt):
    # longs only above SMA200, shorts only below (mirror)
    v = np.zeros(nt, bool)
    if is_index:
        m200 = ts.sma200[ii]
        v = fin(m200) & ((c[ii] - m200) * sd <= 0)
    V["R08"] = v

    # R09 cross-index divergence veto (JP225 trades, both directions):
    # sign(JP225 20-bar) != sign(US100 20-bar)
    v = np.zeros(nt, bool)
    if is_jp:
        A = dict(ep=T["US_Tech_100"].s.ep, c=T["US_Tech_100"].s.c)
        t = align_idx(A["ep"], ep_sig)
        ok = (t >= 20) & (ii >= 20)
        own = np.full(nt, np.nan)
        oth = np.full(nt, np.nan)
        own[ok] = c[ii[ok]] - c[ii[ok] - 20]
        oth[ok] = A["c"][t[ok]] - A["c"][t[ok] - 20]
        v = fin(own) & fin(oth) & (np.sign(own) != np.sign(oth))
    V["R09"] = v

    # R10/R11 portfolio vol ceiling/floor: median ATRp across the four traded
    # symbols (own at bar i, others aligned); requires all four computable
    vals = [ts.atrp[ii]]
    for other in SOURCES:
        if other == src:
            continue
        t = align_idx(T[other].s.ep, ep_sig)
        z = np.full(nt, np.nan)
        ok = t >= 0
        z[ok] = T[other].atrp[t[ok]]
        vals.append(z)
    med = np.median(np.vstack(vals), axis=0)
    all_fin = np.all(np.isfinite(np.vstack(vals)), axis=0)
    V["R10"] = all_fin & (med > 90)
    V["R11"] = all_fin & (med < 10)

    # R12 3-consecutive-red-days long block (mirror: 3 green blocks shorts)
    v = np.zeros(nt, bool)
    for q in range(nt):
        e = dlast[q]
        if e >= 3:
            d3 = np.diff(ts.d_c[e - 3:e + 1])
            if sd[q] > 0:
                v[q] = bool(np.all(d3 < 0))
            else:
                v[q] = bool(np.all(d3 > 0))
    V["R12"] = v

    # R13 yen-vol JP225 block: USDJPY %ATR (atr/close) trailing-500 pctile > 85
    v = np.zeros(nt, bool)
    if is_jp:
        A, t = aux_at("USDJPY_aux")
        ok = t >= 0
        z = np.full(nt, np.nan)
        z[ok] = A["pct_atrp"][t[ok]]
        v = fin(z) & (z > 85)
    V["R13"] = v

    # R14 gold risk-off impulse veto: XAUUSD 20-bar move > +1.5% blocks
    # risk-dir (longs, all four; same risk-dir convention as F11)
    A, t = aux_at("XAUUSD")
    ok = t >= 20
    pct = np.full(nt, np.nan)
    pct[ok] = A["c"][t[ok]] / A["c"][t[ok] - 20] - 1.0
    V["R14"] = (sd > 0) & fin(pct) & (pct > 0.015)

    # R15 breadth-6 long gate: fraction of the fixed 6-basket above SMA200(H1)
    # >= 0.5 required for longs; <= 0.5 for shorts (mirror); all 6 required
    above = []
    ok_all = np.ones(nt, bool)
    for member in BREADTH6:
        if member in T:
            ep_m, c_m, s200 = T[member].s.ep, T[member].s.c, T[member].sma200
        else:
            A = aux[member]
            ep_m, c_m, s200 = A["ep"], A["c"], A["sma200"]
        t = align_idx(ep_m, ep_sig)
        z = np.full(nt, np.nan)
        ok = t >= 0
        z[ok] = np.where(np.isfinite(s200[t[ok]]), (c_m[t[ok]] > s200[t[ok]]).astype(float), np.nan)
        ok_all &= np.isfinite(z)
        above.append(np.nan_to_num(z))
    breadth = np.vstack(above).mean(axis=0)
    V["R15"] = ok_all & np.where(sd > 0, breadth < 0.5, breadth > 0.5)

    # H01 daily IBS conditioning: prior-day IBS > 0.8 blocks longs (mirror <0.2)
    v = np.zeros(nt, bool)
    ok = dlast >= 0
    rng_d = np.full(nt, np.nan)
    ibs = np.full(nt, np.nan)
    rng_d[ok] = ts.d_h[dlast[ok]] - ts.d_l[dlast[ok]]
    good = ok & (rng_d > 0)
    ibs[good] = (ts.d_c[dlast[good]] - ts.d_l[dlast[good]]) / rng_d[good]
    V["H01"] = fin(ibs) & np.where(sd > 0, ibs > 0.8, ibs < 0.2)

    # G14 first armed signal of the server-day (overlay)
    V["G14"] = np.array([int(ts.ti[q]) not in ts.first_attempt for q in range(nt)])

    return V


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
OVERLAY_PARAMS = {
    "F01": "block ATRp(500)>90", "F02": "block TR(sig)>3.0xATR[i-1]",
    "F03": "allow only sign(EMA20_H4 slope over 3 H4)==dir",
    "F04": "allow only sign(dclose[-1]-dclose[-21])==dir",
    "F05": "allow only 20d extreme printed in last 3d (dir side)",
    "F06": "allow only KER(10)>=0.30", "F07": "allow only VR(10)>1.00 (250 H1 log rets)",
    "F08": "indices only: sign(US500 6-bar)==dir; USDJPY exempt",
    "F09": "USDJPY only: sign(6-leg dollar 6-bar factor)==dir",
    "F10": "US idx: block longs if USDJPY 6-bar<-0.5xATR_JPY (mirrored)",
    "F11": "block longs (risk-dir, all 4) when XAUUSD 6-bar>+2.0xATR_XAU",
    "F12": "JP225 only: sign(USDJPY 6-bar)==dir",
    "F13": "USDJPY longs: AUDJPY 6-bar<-2.0xATR14 (real cross used: spec's "
           "synthetic AUDUSDxUSDJPY impossible, no AUDUSD on tape)",
    "F14": "index must own largest |6-bar/ATR| of the 3 indices",
    "F15": "block mean M15 spread(sig hour)>2x trailing-20 same-hour median; USDJPY no spread series -> never vetoed",
    "F16": "block 2xmean spread(last 4 M15)>0.10xATR; USDJPY no spread series -> never vetoed",
    "F17": "block 0.6xATR>3.0xmean M15 TR(8)",
    "F18": "block sum|gaps|(5 internal, bars i-5..i)>=0.35x|c[i]-c[i-5]| (engine move)",
    "F19": "block any TR>4xATR@bar in i-24..i-1",
    "F20": "block stop within 0.10xATR of round grid (grid=10^(floor(log10(med close))-2))",
    "F21": "block prior-day extreme strictly inside limit->TP path",
    "F22": "allow longs only if limit>=min(low[i-4..i]) (mirrored)",
    "F23": "block longs if close>SMA20+3xATR (mirrored)",
    "F24": "block if same-dir actionable signal in prior 8 bars",
    "F25": "block volume z>3 vs trailing 100 prior bars",
    "F26": "H1 grain: allow only mean TR(i-17..i-6)<=0.90xATR[i-6] (window pre-dates the 6-bar impulse; M15 reading would sit inside it)",
    "F27": "indices: block last+first trading day of month",
    "F28": "block if <3 H1 bars to weekly close (gap>24h boundary)",
    "F29": "block if M15 grid gap or >2 zero-range bars in last 24 M15",
    "F30": "block if >20 of 96 closes within +-0.5xATR of TP (mirrored)",
    "R01": "block last 2 TD of month", "R02": "ToM window (last1+first3): longs only inside, shorts only outside",
    "R03": "block TD 1-3", "R04": "block last 3 TD of Mar/Jun/Sep/Dec",
    "R05": f"block fixed dates {R05_DATES}",
    "R06": "USDJPY: block last 3 TD of Mar and Sep",
    "R07": "USDJPY: longs only if dollar index>SMA200 (mirrored)",
    "R08": "indices: longs only above own SMA200(H1) (mirrored); USDJPY exempt",
    "R09": "JP225: block when sign(JP225 20-bar)!=sign(US100 20-bar)",
    "R10": "block when median ATRp of 4 traded symbols>90",
    "R11": "block when median ATRp of 4 traded symbols<10",
    "R12": "block longs after 3 consecutive red days (mirrored)",
    "R13": "JP225: block when USDJPY %ATR pctile(500)>85",
    "R14": "block longs (risk-dir) when XAUUSD 20-bar>+1.5%",
    "R15": f"longs only if breadth(frac>SMA200) of {BREADTH6}>=0.5 (mirrored)",
    "H01": "block longs if prior-day IBS>0.8 (mirror shorts <0.2)",
    "G14": "keep only first armed signal of server-day per symbol",
}

G_CELLS = {
    "G01": dict(depth=0.4), "G02": dict(depth=0.5),
    "G03": dict(depth=0.7), "G04": dict(depth=0.8),
    "G05": dict(window=2), "G06": dict(window=4), "G07": dict(window=5),
    "G08": dict(wick=0.40), "G08d35": dict(wick=0.35),
    "G09": dict(lookback=5), "G10": dict(lookback=7),
    "G12": dict(persist=True), "G15": dict(cooldown=12),
}
GRID_FAMILIES = {
    "depth": dict(cells={"G01": 0.4, "G02": 0.5, "G03": 0.7, "G04": 0.8},
                  control=0.6, order=[0.4, 0.5, 0.6, 0.7, 0.8]),
    "window": dict(cells={"G05": 2, "G06": 4, "G07": 5},
                   control=3, order=[2, 3, 4, 5]),
    "lookback": dict(cells={"G09": 5, "G10": 7},
                     control=6, order=[5, 6, 7]),
}

X_IDS = ["X01", "X02", "X03", "X04", "X05", "X06", "X07", "X10", "X11", "X12",
         "X13", "X15", "X16", "X18", "X20", "X21", "X22", "X23", "X24"]
X_PARAMS = {
    "X01": "exit at close if MAE>=0.6R before MFE>=+0.5R (same-bar tie: MFE disarm wins)",
    "X02": "exit next open if fill bar closes >=0.25xATR past fill price",
    "X03": "if fill-bar penetration>0.4xATR: TP 1.2R + hold 5 from bar j+1",
    "X04": "exit at 2nd consecutive close beyond entry",
    "X05": "at close of bar 4 (j+3): if MFE<+0.5R stop tightens to 0.5xATR",
    "X06": "shorts TP 1.5R hold 6; longs control",
    "X07": "ladder 1/3 @0.75R, 1/3 @1.5R, 1/3 @2.5R; SL 1R; hold 8",
    "X10": "exit at close when ATR14[k]<0.7 x signal ATR",
    "X11": "flatten at close on opposite actionable signal",
    "X12": "close all at last bar with open <= Fri 20:00 UTC",
    "X13": "JP225 exits at last bar with open <= 06:00 UTC (others control)",
    "X15": "structural stop = 20-bar swing extreme, distance clipped at 1.25xATR "
           "(R-units re-based; degenerate non-positive distance -> control 1xATR; "
           "M15-fill-realism caveat binds)",
    "X16": "TP at 20-bar swing extreme, distance clipped to [1.2R, 3.0R]; bank kept",
    "X18": "after bank fills: one limit at original entry for 3 bars re-enters the half",
    "X20": "skip the 50% bank when |signal body|>=0.8xATR",
    "X21": "stop evaluated at bar close only; fill next open; bank+TP unchanged",
    "X22": "no TP/no bank: opposite-signal close, 1R stop, or 45-bar cap",
    "X23": "runner: chandelier 3xATR(22) ratchet replaces TP; bank kept; 45-bar cap (frozen)",
    "X24": "runner: EMA20-cross close exit replaces TP; bank kept; 45-bar cap (frozen)",
}


def variant_stats(ctl_tab, ctl_all_r, ctl_oos_r, var_rows, rng):
    """Pooled E2 delta vs control + paired-by-day bootstrap p (see boot_p)."""
    var_r = np.array([x[1] for sym in SOURCES for x in var_rows[sym]])
    var_oos = np.array([x[1] for sym in SOURCES for x in var_rows[sym] if x[2]])
    if len(var_r) == 0:
        return dict(n=0, oos_n=0, delta_full=None, delta_oos=None, p=None)
    delta_full = float(var_r.mean() - ctl_all_r.mean())
    delta_oos = (float(var_oos.mean() - ctl_oos_r.mean()) if len(var_oos) else None)
    var_tab = {}
    for sym in SOURCES:
        rows = var_rows[sym]
        days = np.array([x[0] // 86400 for x in rows], dtype=np.int64)
        rr = np.array([x[1] for x in rows], dtype=float)
        var_tab[sym] = day_table(days, rr)
    p = boot_p(ctl_tab, var_tab, rng)
    return dict(n=int(len(var_r)), oos_n=int(len(var_oos)),
                delta_full=delta_full, delta_oos=delta_oos, p=p,
                expectancy=float(var_r.mean()))


def main() -> None:
    t_start = time.time()
    print("SPEC_HASH", check_spec_hash(), flush=True)
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    rng = np.random.default_rng(SEED)

    # ---------------- A. control -------------------------------------------
    print("loading traded symbols (E2 = cost_e1 x 2.0, OOS = last 30% of bars)",
          flush=True)
    T = {src: TSym(src, meta) for src in SOURCES}

    # run_variant with control parameters must reproduce run_cell exactly
    for src in SOURCES:
        ref = [(t["ep"], t["r"], t["oos"]) for t in T[src].trades]
        got = run_variant(T[src].s)
        assert got == ref, f"run_variant control-parity break on {src}"
    print("PARITY control extraction + resolve_base + run_variant: PASS", flush=True)

    ctl_all_r = np.concatenate([T[s].tr_r for s in SOURCES])
    ctl_oos_r = np.concatenate([T[s].tr_r[T[s].toos] for s in SOURCES])
    ctl_sym = np.concatenate([np.full(len(T[s].tr_r), s, dtype=object) for s in SOURCES])
    ctl_oos_mask = np.concatenate([T[s].toos for s in SOURCES])
    ctl_tab = {s: day_table(T[s].tday, T[s].tr_r) for s in SOURCES}
    control_summary = {
        s: dict(n=len(T[s].tr_r), expectancy=float(T[s].tr_r.mean()),
                oos_n=int(T[s].toos.sum()),
                oos_expectancy=float(T[s].tr_r[T[s].toos].mean()),
                cost_e1_per_side_atr=T[s].cost_e1,
                h1_bars=int(len(T[s].s.c)))
        for s in SOURCES}
    print(f"CONTROL pooled n={len(ctl_all_r)} exp={ctl_all_r.mean():+.4f} "
          f"oos_n={len(ctl_oos_r)} oos_exp={ctl_oos_r.mean():+.4f}", flush=True)

    # ---------------- aux series -------------------------------------------
    print("building aux H1 series", flush=True)
    aux = {}
    for name in ("US_SP_500", "EURUSD", "GBPUSD", "USDCAD", "USDCHF",
                 "AUDJPY", "NZDUSD", "XAUUSD", "Germany_40", "UK_100"):
        aux[name] = load_aux(name)
    aux["USDJPY_aux"] = dict(ep=T["USDJPY"].s.ep, c=T["USDJPY"].s.c,
                             atr=T["USDJPY"].s.atr,
                             sma200=T["USDJPY"].sma200,
                             atrp=T["USDJPY"].atrp,
                             pct_atrp=roll_pctile(
                                 T["USDJPY"].s.atr / T["USDJPY"].s.c, 500),
                             logc=np.log(T["USDJPY"].s.c))
    # AUDUSD leg of the dollar basket: no AUDUSD on the frozen tape -- the leg
    # is synthesized exactly as AUDJPY / USDJPY (log close = logAUDJPY-logUSDJPY)
    aj, uj = aux["AUDJPY"], aux["USDJPY_aux"]
    eps_a = np.intersect1d(aj["ep"], uj["ep"])
    logc_a = (aj["logc"][np.searchsorted(aj["ep"], eps_a)]
              - uj["logc"][np.searchsorted(uj["ep"], eps_a)])
    aux["AUDUSD"] = dict(ep=eps_a, logc=logc_a, c=np.exp(logc_a))
    dollar = build_dollar_grid(aux)
    synja = build_audjpy(aux)

    cells = {}

    # ---------------- B. overlays ------------------------------------------
    print("computing overlay vetoes", flush=True)
    per_sym_veto = {src: overlay_vetoes(T[src], aux, dollar, synja, T)
                    for src in SOURCES}
    overlay_ids = sorted(OVERLAY_PARAMS)
    for cid in overlay_ids:
        veto = np.concatenate([np.asarray(per_sym_veto[s][cid], dtype=bool)
                               for s in SOURCES])
        kept = ~veto
        gap, p = perm_gap_p(ctl_all_r, ctl_sym, veto, rng)
        mean_all = float(ctl_all_r.mean())
        mean_kept = float(ctl_all_r[kept].mean()) if kept.any() else None
        mean_veto = float(ctl_all_r[veto].mean()) if veto.any() else None
        ko = kept & ctl_oos_mask
        delta_full = (mean_kept - mean_all) if mean_kept is not None else None
        delta_oos = (float(ctl_all_r[ko].mean() - ctl_oos_r.mean())
                     if ko.any() else None)
        fam = cid[0] if cid[0] in "FRH" else "G"
        cells[cid] = dict(
            family=fam, id=cid, kind="overlay", params=OVERLAY_PARAMS[cid],
            n=int(len(veto)), n_kept=int(kept.sum()), n_veto=int(veto.sum()),
            oos_n=int(ko.sum()),
            mean_r_kept=mean_kept, mean_r_veto=mean_veto, gap=gap,
            delta_full=delta_full, delta_oos=delta_oos, p=p)
        print(f"  {cid}: n_veto={int(veto.sum()):5d} gap={fmt(gap)} "
              f"dfull={fmt(delta_full)} doos={fmt(delta_oos)} p={fmt(p)}", flush=True)

    # ---------------- C. geometry variants ---------------------------------
    print("running geometry variant cells", flush=True)
    for cid, kw in G_CELLS.items():
        rows = {}
        for src in SOURCES:
            ts = T[src]
            if "lookback" in kw:
                s2, start_l = reprep_lookback(ts.s, kw["lookback"])
                rows[src] = run_variant(s2, start=start_l)
            else:
                rows[src] = run_variant(ts.s, **kw)
        st = variant_stats(ctl_tab, ctl_all_r, ctl_oos_r, rows, rng)
        kind = "diagnostic" if cid == "G08d35" else "variant"
        cells[cid] = dict(family="G", id=cid, kind=kind, params=str(kw), **st)
        print(f"  {cid}: n={st['n']:5d} dfull={fmt(st['delta_full'])} "
              f"doos={fmt(st['delta_oos'])} p={fmt(st['p'])}", flush=True)

    # ---------------- D. exit variants (entries frozen = control fills) -----
    print("running exit variant cells", flush=True)

    def resolve_for(cid, ts, q):
        s = ts.s
        i0, j = int(ts.ti[q]), int(ts.tj[q])
        sd = int(ts.tside[q])
        entry = float(ts.tentry[q])
        a = float(ts.ta[q])
        if cid == "X01":
            return resolve_close_rule(s, j, sd, entry, a,
                                      lambda k, mfe, mae: mfe < 0.5 and mae >= 0.6)
        if cid == "X02":
            return resolve_close_rule(
                s, j, sd, entry, a,
                lambda k, mfe, mae: k == j and (entry - s.c[k]) * sd >= 0.25 * a,
                exit_next_open=True)
        if cid == "X03":
            return resolve_x03(s, j, sd, entry, a)
        if cid == "X04":
            state = dict(cnt=0)

            def rule04(k, mfe, mae):
                if (s.c[k] - entry) * sd < 0:
                    state["cnt"] += 1
                else:
                    state["cnt"] = 0
                return state["cnt"] >= 2
            return resolve_close_rule(s, j, sd, entry, a, rule04)
        if cid == "X05":
            return resolve_x05(s, j, sd, entry, a)
        if cid == "X06":
            if sd < 0:
                return resolve_base(s, j, sd, entry, a, tp_r=1.5, hold=6)
            return resolve_base(s, j, sd, entry, a)
        if cid == "X07":
            return resolve_x07(s, j, sd, entry, a)
        if cid == "X10":
            return resolve_close_rule(
                s, j, sd, entry, a,
                lambda k, mfe, mae: np.isfinite(s.atr[k]) and s.atr[k] < 0.7 * a)
        if cid == "X11":
            return resolve_close_rule(
                s, j, sd, entry, a, lambda k, mfe, mae: ts.sig_dir[k] == -sd)
        if cid == "X12":
            return resolve_close_rule(
                s, j, sd, entry, a, lambda k, mfe, mae: bool(ts.eow_flat[k]))
        if cid == "X13":
            if ts.source != "Japan_225":
                return int(ts.txb[q]), float(ts.tr_r[q])
            return resolve_close_rule(
                s, j, sd, entry, a, lambda k, mfe, mae: bool(ts.tokyo_flat[k]))
        if cid == "X15":
            lo = max(0, i0 - 19)
            swing = s.l[lo:i0 + 1].min() if sd > 0 else s.h[lo:i0 + 1].max()
            dist = (entry - swing) * sd
            risk = min(dist, 1.25 * a) if dist > 0 else a
            return resolve_base(s, j, sd, entry, a, risk=risk)
        if cid == "X16":
            lo = max(0, i0 - 19)
            ext = s.h[lo:i0 + 1].max() if sd > 0 else s.l[lo:i0 + 1].min()
            dist = float(np.clip((ext - entry) * sd, 1.2 * a, 3.0 * a))
            return resolve_base(s, j, sd, entry, a, tp_price=entry + dist * sd)
        if cid == "X18":
            return resolve_x18(s, j, sd, entry, a)
        if cid == "X20":
            body = abs(s.c[i0] - s.o[i0])
            return resolve_base(s, j, sd, entry, a, bank=body < 0.8 * a)
        if cid == "X21":
            return resolve_x21(s, j, sd, entry, a)
        if cid == "X22":
            return resolve_x22(s, ts, j, sd, entry, a)
        if cid == "X23":
            return resolve_x23(s, ts, j, sd, entry, a)
        if cid == "X24":
            return resolve_x24(s, ts, j, sd, entry, a)
        raise KeyError(cid)

    x_rows_by_cell = {}
    for cid in X_IDS:
        rows = {}
        for src in SOURCES:
            ts = T[src]
            out = []
            for q in range(len(ts.ti)):
                xb, r = resolve_for(cid, ts, q)
                out.append((int(ts.tep[q]), float(r), bool(ts.toos[q]), int(xb)))
            rows[src] = out
        x_rows_by_cell[cid] = rows
        st = variant_stats(ctl_tab, ctl_all_r, ctl_oos_r,
                           {s: [x[:3] for x in rows[s]] for s in SOURCES}, rng)
        cells[cid] = dict(family="X", id=cid, kind="variant",
                          params=X_PARAMS[cid], **st)
        print(f"  {cid}: n={st['n']:5d} dfull={fmt(st['delta_full'])} "
              f"doos={fmt(st['delta_oos'])} p={fmt(st['p'])}", flush=True)

    # ---------------- hand-check examples (F27 calendar, X12 EOW) -----------
    print("\nHAND-CHECK F27 (month-turn veto, indices): 3 vetoed trades")
    shown = 0
    for src in INDEX_SOURCES:
        vet = per_sym_veto[src]["F27"]
        for q in np.flatnonzero(vet):
            cal = T[src].cal[int(T[src].tday[q])]
            when = datetime.fromtimestamp(int(T[src].tep[q]), timezone.utc)
            print(f"  {src} signal {when:%Y-%m-%d %H:%M} UTC td_idx={cal[0]} "
                  f"td_from_end={cal[1]} r={T[src].tr_r[q]:+.3f}")
            shown += 1
            break
        if shown >= 3:
            break
    print("HAND-CHECK X12 (end-of-week flat): 3 changed trades")
    shown = 0
    for src in SOURCES:
        ts = T[src]
        for q in range(len(ts.ti)):
            ep_r, r_v, _, xb_v = x_rows_by_cell["X12"][src][q]
            if abs(r_v - ts.tr_r[q]) > 1e-9:
                sig = datetime.fromtimestamp(int(ts.tep[q]), timezone.utc)
                ex = datetime.fromtimestamp(int(ts.s.ep[xb_v]), timezone.utc)
                print(f"  {src} signal {sig:%Y-%m-%d %H:%M} exit bar "
                      f"{ex:%a %Y-%m-%d %H:%M} UTC r_ctl={ts.tr_r[q]:+.3f} "
                      f"r_x12={r_v:+.3f}")
                shown += 1
                break
        if shown >= 3:
            break

    # ---------------- E. gates, plateau, BH-FDR, survivors ------------------
    for cid, cell in cells.items():
        if cell["kind"] == "diagnostic":
            cell["gates"] = dict(note="non-decisional diagnostic")
            continue
        d_oos, d_full, p = cell["delta_oos"], cell["delta_full"], cell["p"]
        if cell["kind"] == "overlay":
            n_ok = cell["n_veto"] >= MIN_N and cell["n_kept"] >= MIN_N
        else:
            n_ok = cell["n"] >= MIN_N
        cell["gates"] = dict(
            oos_delta_pos=bool(d_oos is not None and d_oos > 0),
            materiality=bool(d_full is not None and d_full >= MATERIALITY),
            n_ok=bool(n_ok),
            p_computable=bool(p is not None))
        cell["gates"]["pre_fdr_pass"] = all(
            cell["gates"][k] for k in
            ("oos_delta_pos", "materiality", "n_ok", "p_computable"))

    # plateau (adapted WFO_SPEC section 4, frozen here): the family candidate
    # (highest OOS delta, taken in descending order) enters FDR only if every
    # one-step grid neighbor's pooled full-sample E2 expectancy (control counts
    # at its own expectancy) is within 20% BELOW the candidate's expectancy.
    ctl_exp = float(ctl_all_r.mean())
    plateau_entrants = {}
    for fam_name, fam in GRID_FAMILIES.items():
        exp_by_val = {fam["control"]: ctl_exp}
        for cid, val in fam["cells"].items():
            exp_by_val[val] = cells[cid].get("expectancy")
        order = fam["order"]
        ranked = sorted(
            fam["cells"].items(),
            key=lambda kv: (-9e9 if cells[kv[0]]["delta_oos"] is None
                            else cells[kv[0]]["delta_oos"]),
            reverse=True)
        entrant = None
        for cid, val in ranked:
            e_c = exp_by_val[val]
            if e_c is None:
                continue
            pos = order.index(val)
            neighbors = [order[pos - 1]] if pos > 0 else []
            if pos + 1 < len(order):
                neighbors.append(order[pos + 1])
            ok = all(exp_by_val.get(nv) is not None
                     and exp_by_val[nv] >= e_c - 0.20 * abs(e_c)
                     for nv in neighbors)
            cells[cid]["plateau"] = dict(family=fam_name, value=val,
                                         neighbors={str(nv): exp_by_val.get(nv)
                                                    for nv in neighbors},
                                         consistent=bool(ok))
            if ok and entrant is None:
                entrant = cid
        for cid in fam["cells"]:
            cells[cid].setdefault("plateau", dict(family=fam_name,
                                                  consistent=False))
            cells[cid]["plateau"]["family_entrant"] = entrant
        plateau_entrants[fam_name] = entrant

    grid_cell_ids = {cid for fam in GRID_FAMILIES.values() for cid in fam["cells"]}
    fdr_set = []
    for cid, cell in cells.items():
        if cell["kind"] == "diagnostic" or cell["p"] is None:
            continue
        if cid in grid_cell_ids and plateau_entrants.get(
                cells[cid]["plateau"]["family"]) != cid:
            continue
        fdr_set.append(cid)
    m = len(fdr_set)
    ranked_p = sorted(fdr_set, key=lambda cid: cells[cid]["p"])
    thresh = 0.0
    for rank, cid in enumerate(ranked_p, start=1):
        if cells[cid]["p"] <= FDR_Q * rank / m:
            thresh = cells[cid]["p"]
    bh_pass = {cid for cid in fdr_set if cells[cid]["p"] <= thresh} if thresh > 0 else set()
    for cid, cell in cells.items():
        cell["fdr"] = dict(in_set=cid in fdr_set, bh_pass=cid in bh_pass)
        cell["survivor_pre_cap"] = bool(
            cell.get("gates", {}).get("pre_fdr_pass") and cid in bh_pass)

    survivors = sorted(
        [cid for cid, c in cells.items() if c.get("survivor_pre_cap")],
        key=lambda cid: cells[cid]["delta_oos"], reverse=True)[:5]
    for cid in cells:
        cells[cid]["stage_a_survivor"] = cid in survivors

    # ---------------- output -------------------------------------------------
    out = dict(
        spec="docs/IMPROVE100_SPEC_2026-07-15.md",
        spec_sha256_check=check_spec_hash(),
        engine_commit="61f42c9+branch",
        seed=SEED, n_permutations=N_PERM, n_bootstraps=N_BOOT,
        statistic_conventions=dict(
            overlay="E2 mean-R gap (kept-vetoed); p=P(within-symbol perm gap>=obs); "
                    "delta_full=mean_kept-mean_all (materiality); "
                    "delta_oos=mean_kept_oos-mean_all_oos; "
                    "n gate = n_veto>=50 AND n_kept>=50",
            variant="E2 pooled expectancy delta vs control; p=frac of 2000 "
                    "paired-by-day (union days, shared draw) bootstrap deltas<=0; "
                    "n gate = variant n>=50",
            feature_unavailable="ALLOW (veto only when computable)",
            alignment="last aux H1 bar with open epoch <= signal bar open epoch",
            plateau="adapted WFO_SPEC sec.4: all one-step neighbors' pooled E2 "
                    "expectancy >= candidate - 20%|candidate|; control counts at "
                    "its own expectancy; candidate = highest OOS delta that is "
                    "plateau-consistent; one entrant per grid family into FDR",
            fdr=f"Benjamini-Hochberg q={FDR_Q} over the {m}-cell run set "
                "(grid families collapsed to their entrant; diagnostics excluded)",
            frozen_choices=[
                "X23/X24 runner cap = 45 bars (X22's cap; hold-8 would make a "
                "3xATR22 trail unreachable) - flagged as a frozen harness choice",
                "F13 uses the REAL AUDJPY cross (no AUDUSD on the frozen tape "
                "so the spec's synthetic AUDUSDxUSDJPY is unbuildable; the "
                "real cross is economically identical with a true-range ATR)",
                "F09/R07 AUDUSD dollar-basket leg synthesized exactly as "
                "AUDJPY/USDJPY (log-return identity)",
                "F26 computed on H1 (spec window t-17..t-6 pre-dates the "
                "impulse only on H1; an M15 reading would sit inside it)",
                "F20 round grid = 10^(floor(log10(median close))-2)",
                "R02 ToM window = last 1 + first 3 trading days",
                "R05 fixed dates = " + str(R05_DATES),
                "R15 breadth = fraction of 6-basket above SMA200(H1)",
                "R14/F11 risk-dir = longs on all four symbols",
                "X15 swing = 20-bar extreme; non-positive distance -> control",
                "X18 re-entry: fill checked before SL within the bar; bank "
                "latch not re-armed; +0.5x round-trip cost",
                "trading-day calendars use the symbol's realized tape days "
                "(ex-ante-knowable market schedule)",
            ]),
        spec_forfeits=dict(
            G11="candle-anatomy clv_dir family closed (inverted sign 3x)",
            G13="adjacent to Q2 re-place + M2-REPLACE recovery nulls",
            X08="conditional-hold fence (cond_hold + VPOF)",
            X09="adaptive_tp do-not-re-propose",
            X14="no live spread series at exit timestamps in tape",
            X17="dominated by construction under E2",
            X19="VPOF/HIGHWATER trailing-family fence"),
        runtime_forfeits={},
        zero_veto_cells=dict(
            F15="verified genuine, not a bug: at SIGNAL bars the max spread /"
                " same-hour-median ratio is 1.13 (US30) / 1.05 (US100) / 1.40"
                " (JP225) vs >2 required; the huge spread spikes (up to 239x)"
                " occur in hours that never produce signals or inflate their"
                " own hour median.  USDJPY has no spread series (noted).",
            F17="structural on this book: 3x mean M15 TR(8) always exceeds"
                " 0.6xATR_H1 at signal bars (max observed ratio 0.73, US30).",
            F22="structural: after a >=2-ATR 6-bar impulse the 0.6-ATR"
                " pullback limit sits far above the 5-bar structure low"
                " (min observed margin +1.45 ATR, US30)."),
        control=dict(pooled_n=int(len(ctl_all_r)),
                     pooled_expectancy=float(ctl_all_r.mean()),
                     pooled_oos_n=int(len(ctl_oos_r)),
                     pooled_oos_expectancy=float(ctl_oos_r.mean()),
                     per_symbol=control_summary),
        plateau_entrants=plateau_entrants,
        fdr=dict(q=FDR_Q, m=m, bh_threshold=thresh,
                 bh_pass=sorted(bh_pass)),
        cells=cells,
        stage_a_survivors=survivors,
        elapsed_s=round(time.time() - t_start, 1),
    )
    RESULT_PATH.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")

    # ---------------- compact table ------------------------------------------
    print("\n" + "=" * 98)
    print(f"{'cell':7s} {'kind':8s} {'n':>6s} {'n_veto':>6s} {'d_full':>8s} "
          f"{'d_oos':>8s} {'p':>7s} {'gates':>6s} {'BH':>3s} {'verdict':>9s}")
    print("-" * 98)
    ordered = sorted([c for c in cells.values() if c["kind"] != "diagnostic"],
                     key=lambda c: (c["delta_oos"] is not None,
                                    c["delta_oos"] if c["delta_oos"] is not None else -9e9),
                     reverse=True)
    for c in ordered:
        verdict = ("SURVIVOR" if c["stage_a_survivor"] else
                   "PASS*cap" if c.get("survivor_pre_cap") else "FAIL")
        print(f"{c['id']:7s} {c['kind']:8s} {c['n']:6d} "
              f"{c.get('n_veto', 0):6d} {fmt(c['delta_full']):>8s} "
              f"{fmt(c['delta_oos']):>8s} {fmt(c['p']):>7s} "
              f"{'Y' if c['gates'].get('pre_fdr_pass') else 'n':>6s} "
              f"{'Y' if c['fdr']['bh_pass'] else 'n':>3s} {verdict:>9s}")
    print("=" * 98)
    print(f"BH-FDR: m={m} threshold={thresh} pass={sorted(bh_pass) or 'NONE'}")
    print(f"PLATEAU entrants: {plateau_entrants}")
    print(f"STAGE_A_SURVIVORS (top-5 cap): {survivors or 'NONE'}")
    print(f"RESULT_FILE {RESULT_PATH}")
    print(f"ELAPSED {time.time() - t_start:.0f}s")


def fmt(x):
    return "None" if x is None else f"{x:+.4f}" if abs(x) < 10 else f"{x:.3g}"


if __name__ == "__main__":
    main()
