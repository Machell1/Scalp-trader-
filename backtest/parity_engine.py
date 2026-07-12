"""Live-parity replay engine.

Pre-registered: docs/W2_PARITY_SPEC_2026-07-12.md
  (SHA256 03b9967a8eba3d0e366f78a62fb2b156f59a06d19b47e90570fce13cb1cc9a90)

Replays the exact validated bracket rules under the LIVE EA's enumeration
semantics (MomentumPullbackEA v1.29.1, source-cited in the spec):
  R1 every closed bar is evaluated exactly once; blocked signals never revisited
  R2 W2 wick predicate applied pre-entry (non-W2 signals never occupy)
  R3 an unfilled pending occupies bars i+1..i+3 and is cancelled at the open of
     bar i+4 BEFORE that pass's scan -> first eligible signal bar = i+3
  R4 symbol occupied by pending OR position (cap 1, both count)
  R5 post-exit cooldown: exit bar blocked, resume at exit_bar+1 (already matched
     the validated engine -- v1.27 parity holds)
  R6/R7 cluster cap + global cap count positions+pendings; scans in whitelist order
  R9 fills/day cap and 4-consecutive-loss day stop (never modeled before)

`scalper_backtest.py` is deliberately NOT modified. Mode M0 re-implements its
(non-causal) enumeration on shared numeric primitives; parity_regression.py
asserts trade-for-trade identity on every manifest CSV before anything else runs.
"""
import heapq
import os
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr

MB = 6              # momentum lookback bars
MOM_ATR = 2.0       # momentum threshold (ATR units)
ATR_P = 14
OFFSET = 0.6        # pullback limit offset (ATR)
EXPIRY = 3          # pending expiry (bars) -> fill window i+1..i+3
STOP_ATR = 1.0
TP_ATR = 3.0
HOLD = 8            # max holding bars
START = MB + ATR_P + 1   # first evaluable signal bar (== simulate_symbol)
BAR_SEC = 900       # M15


@dataclass
class SymData:
    name: str
    ep: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    atr: np.ndarray
    side: np.ndarray     # +1/-1/0 momentum signal at each bar's close (pre-W2)
    watr: np.ndarray     # adverse-side wick / ATR where side != 0, else nan
    cost: float          # per-side cost, ATR fraction
    cluster: int = 0


def prep_symbol(raw: pd.DataFrame, cost: float, name: str, cluster: int = 0) -> SymData:
    nmap = {col.lower(): col for col in raw.columns}
    df = raw.rename(columns={nmap[k]: k for k in ("time", "open", "high", "low", "close") if k in nmap})
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, ATR_P)
    n = len(c)
    dt = pd.to_datetime(df["time"])
    if getattr(dt.dt, "tz", None) is not None:
        dt = dt.dt.tz_convert("UTC").dt.tz_localize(None)
    ep = ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy().astype(np.int64)

    move = np.full(n, np.nan)
    move[MB - 1:] = c[:n - (MB - 1)] - c[MB - 1:]        # c[i-(MB-1)] - c[i]
    with np.errstate(invalid="ignore", divide="ignore"):
        ma = move / atr
    valid = np.isfinite(atr) & (atr > 0) & (np.arange(n) >= START)
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
    return SymData(name, ep, o, h, l, c, atr, side, watr, cost, cluster)


def find_fill(s: SymData, side: int, entry: float, w_start: int, w_end: int) -> int:
    """First bar in [w_start, w_end] where the limit touches; -1 if none.
    Window semantics identical to simulate_symbol: range(i+1, min(i+1+EXPIRY, n))."""
    for j in range(w_start, min(w_end + 1, len(s.c))):
        if side > 0:
            if s.l[j] <= entry:
                return j
        else:
            if s.h[j] >= entry:
                return j
    return -1


def resolve_bracket(s: SymData, entry_bar: int, side: int, entry: float, atr_sig: float):
    """(exit_bar, exit_price, reason) under the sim's pessimistic rules:
    SL checked before TP each bar, fill bar included, time exit at close of
    entry_bar+HOLD-1. Lock/trail off (pure bracket)."""
    risk = STOP_ATR * atr_sig
    if side > 0:
        sl, tp = entry - risk, entry + TP_ATR * atr_sig
    else:
        sl, tp = entry + risk, entry - TP_ATR * atr_sig
    n = len(s.c)
    for k in range(entry_bar, min(entry_bar + HOLD, n)):
        if side > 0:
            if s.l[k] <= sl:
                return k, sl, "SL"
            if s.h[k] >= tp:
                return k, tp, "TP"
        else:
            if s.h[k] >= sl:
                return k, sl, "SL"
            if s.l[k] <= tp:
                return k, tp, "TP"
    k = min(entry_bar + HOLD - 1, n - 1)
    return k, s.c[k], "TIME"


def trade_r(s: SymData, side: int, entry: float, exit_price: float, atr_sig: float,
            cost_mult: float = 1.0) -> float:
    gross = (exit_price - entry) * side
    net = gross - 2.0 * s.cost * cost_mult * atr_sig
    return net / (STOP_ATR * atr_sig)


@dataclass
class Trade:
    sym: str
    sig: int
    entry_bar: int
    exit_bar: int
    side: int
    r: float
    reason: str
    ep_sig: int
    cost: float           # per-side cost (for 2x stress: r2x = r - 2*cost)
    queued: bool = False


# ---------------------------------------------------------------------------
# M0 -- sim-parity enumeration (golden-regression target).
# Identical to simulate_symbol: unfilled pending -> rewind to i+1 (non-causal);
# no pre-entry W2; no occupancy beyond one-trade-at-a-time.
# ---------------------------------------------------------------------------

def run_m0(s: SymData) -> list:
    trades = []
    n = len(s.c)
    i = START
    end = n - 1
    while i < end:
        sd = int(s.side[i])
        if sd == 0:
            i += 1
            continue
        a = s.atr[i]
        entry = s.c[i] - OFFSET * a * sd
        j = find_fill(s, sd, entry, i + 1, i + EXPIRY)
        if j < 0:
            i += 1
            continue
        xb, xp, reason = resolve_bracket(s, j, sd, entry, a)
        trades.append(Trade(s.name, i, j, xb, sd, trade_r(s, sd, entry, xp, a),
                            reason, int(s.ep[i]), s.cost))
        i = max(xb + 1, i + 1)
    return trades


# ---------------------------------------------------------------------------
# Causal live-parity engine (M1 single-symbol, M2 coupled, M2q queue, M3 mixed)
# ---------------------------------------------------------------------------

FREE, BUSY = 0, 1

# event priorities within an epoch: management/frees (0) before opens/scans (1)
# -- mirrors ManageAll() running before ScanAllOnNewBars() in the same heartbeat.
P_MGMT, P_OPEN = 0, 1


@dataclass
class SymState:
    status: int = FREE
    phase: int = 0                 # 0 none, 1 pending working, 2 position open
    no_sig_upto: int = -1          # signal bars <= this are cooldown-blocked
    pend_token: int = 0            # invalidates stale scheduled lifecycle events
    queued: tuple | None = None    # (sig_i, side, entry, atr_sig)


@dataclass
class Census:
    occupied: int = 0
    cooldown: int = 0
    w2_fail: int = 0
    cap_global: int = 0
    cap_cluster: int = 0
    day_fills: int = 0
    day_consec: int = 0
    q_stashed: int = 0
    q_released: int = 0
    q_expired: int = 0
    q_stale: int = 0
    q_replaced: int = 0


def run_live(symbols: list, thr=None, caps=None, queue=False, reverse_scan=False,
             window=EXPIRY, replace_on_signal=False):
    """thr: None (no engine W2) | dict name->min adverse wick (pre-entry predicate).
    caps: None (per-symbol only) | dict(global=2, cluster=1, fills_day=8, consec=4).
    window: pending fill window in bars. 3 = validated-engine intent; 4 = live
    as-deployed (FTMO journal ground truth 2026-07-10: order #493361350 placed
    12:00:02, cancelled 13:00:02 -- MQL5 Bars() does NOT count the placement bar,
    so ageBars>3 first fires at the open of i+5).
    Returns (trades, census)."""
    ns = len(symbols)
    st = [SymState() for _ in range(ns)]
    census = Census()
    trades: list[Trade] = []
    fills_day: dict[int, int] = {}
    consec_day: dict[int, int] = {}
    scan_pos = {si: (ns - 1 - si if reverse_scan else si) for si in range(ns)}

    seq = 0
    heap: list = []

    def push(epoch, prio, sub, kind, payload):
        nonlocal seq
        seq += 1
        heapq.heappush(heap, (int(epoch), prio, sub, seq, kind, payload))

    for si, s in enumerate(symbols):
        for b in range(START + 1, len(s.c)):
            push(s.ep[b], P_OPEN, scan_pos[si], "open", (si, b))

    def busy_count():
        return sum(1 for x in st if x.status == BUSY)

    def cluster_count(cl):
        return sum(1 for si2, x in enumerate(st) if x.status == BUSY and symbols[si2].cluster == cl)

    def book(si, tr):
        trades.append(tr)
        if caps is not None:
            d = int(symbols[si].ep[tr.exit_bar]) // 86400
            if tr.r < 0:
                consec_day[d] = consec_day.get(d, 0) + 1
            else:
                consec_day[d] = 0

    def place(si, sig_i, side, entry, atr_sig, w_start, queued=False):
        """Arm a pending: schedule fill/exit or cancel. w_start=first fill bar."""
        s = symbols[si]
        st[si].status = BUSY
        st[si].phase = 1
        st[si].pend_token += 1
        tok = st[si].pend_token
        j = find_fill(s, side, entry, w_start, sig_i + window)
        if j < 0:
            cb = sig_i + window + 1
            cancel_ep = s.ep[cb] if cb < len(s.c) else s.ep[-1] + BAR_SEC
            push(cancel_ep, P_MGMT, 0, "cancel", (si, tok))
            return
        # fill happens intrabar of bar j: day-gate visibility from close of j
        push(s.ep[j] + BAR_SEC, P_MGMT, 0, "fill", (si, j, tok))
        xb, xp, reason = resolve_bracket(s, j, side, entry, atr_sig)
        tr = Trade(s.name, sig_i, j, xb, side, trade_r(s, side, entry, xp, atr_sig),
                   reason, int(s.ep[sig_i]), s.cost, queued=queued)
        if reason == "TIME" and xb + 1 < len(s.c):
            free_ep = s.ep[xb + 1]          # EA closes at next bar's open, seat frees then
        else:
            free_ep = s.ep[xb] + BAR_SEC    # broker-side intrabar exit, seat free by bar close
        push(free_ep, P_MGMT, 0, "exit", (si, tr, tok))

    def try_place_signal(si, i):
        """Scan verdict for signal bar i of symbol si. Returns 'placed'/'blocked_cap'/None."""
        s = symbols[si]
        sd = int(s.side[i])
        if sd == 0:
            return None
        if thr is not None and not (np.isfinite(s.watr[i]) and s.watr[i] >= thr[s.name]):
            census.w2_fail += 1
            return None
        if caps is not None:
            d = int(s.ep[i + 1]) // 86400
            if fills_day.get(d, 0) >= caps["fills_day"]:
                census.day_fills += 1
                return None
            if consec_day.get(d, 0) >= caps["consec"]:
                census.day_consec += 1
                return None
            if busy_count() >= caps["global"]:
                census.cap_global += 1
                return "blocked_cap"
            if cluster_count(s.cluster) >= caps["cluster"]:
                census.cap_cluster += 1
                return "blocked_cap"
        a = s.atr[i]
        place(si, i, sd, s.c[i] - OFFSET * a * sd, a, i + 1)
        return "placed"

    while heap:
        epoch, prio, sub, _, kind, payload = heapq.heappop(heap)
        if kind == "cancel":
            si, tok = payload
            if st[si].status == BUSY and st[si].pend_token == tok:
                st[si].status = FREE
                st[si].phase = 0
        elif kind == "fill":
            si, j, tok = payload
            if st[si].pend_token != tok:
                continue                    # pending was replaced before its fill
            st[si].phase = 2
            d = int(symbols[si].ep[j]) // 86400
            fills_day[d] = fills_day.get(d, 0) + 1
        elif kind == "exit":
            si, tr, tok = payload
            if st[si].pend_token != tok:
                continue                    # lifecycle voided by replacement
            st[si].status = FREE
            st[si].phase = 0
            st[si].no_sig_upto = max(st[si].no_sig_upto, tr.exit_bar)
            book(si, tr)
        elif kind == "open":
            si, b = payload
            s = symbols[si]
            i = b - 1                       # just-closed signal bar (shift 1)
            if st[si].status == BUSY:
                fresh = s.side[i] != 0 and (thr is None or
                                            (np.isfinite(s.watr[i]) and s.watr[i] >= thr[s.name]))
                if (replace_on_signal and fresh and st[si].phase == 1
                        and i > st[si].no_sig_upto):
                    # newest-signal-wins: cancel the working pending, re-anchor.
                    # Capacity unchanged (same slot); day gates still apply.
                    okday = True
                    if caps is not None:
                        d = int(s.ep[b]) // 86400
                        okday = (fills_day.get(d, 0) < caps["fills_day"]
                                 and consec_day.get(d, 0) < caps["consec"])
                    if okday:
                        sd = int(s.side[i])
                        a = s.atr[i]
                        place(si, i, sd, s.c[i] - OFFSET * a * sd, a, i + 1)
                        continue
                if fresh:
                    census.occupied += 1
                continue
            if i <= st[si].no_sig_upto:
                if s.side[i] != 0:
                    census.cooldown += 1
                continue
            verdict = try_place_signal(si, i)
            if queue:
                if verdict == "placed":
                    st[si].queued = None
                elif verdict == "blocked_cap":
                    if st[si].queued is not None:
                        census.q_replaced += 1
                    st[si].queued = (i, int(s.side[i]),
                                     s.c[i] - OFFSET * s.atr[i] * int(s.side[i]), s.atr[i])
                    census.q_stashed += 1
                elif st[si].queued is not None:
                    qi, qsd, qentry, qatr = st[si].queued
                    if b > qi + window:
                        st[si].queued = None
                        census.q_expired += 1
                    else:
                        touched = False
                        for jj in range(qi + 1, b):
                            if (qsd > 0 and s.l[jj] <= qentry) or (qsd < 0 and s.h[jj] >= qentry):
                                touched = True
                                break
                        if touched:
                            st[si].queued = None
                            census.q_stale += 1
                        else:
                            okday = True
                            if caps is not None:
                                d = int(s.ep[b]) // 86400
                                okday = (fills_day.get(d, 0) < caps["fills_day"]
                                         and consec_day.get(d, 0) < caps["consec"])
                            if okday and (caps is None or
                                          (busy_count() < caps["global"]
                                           and cluster_count(s.cluster) < caps["cluster"])):
                                st[si].queued = None
                                census.q_released += 1
                                place(si, qi, qsd, qentry, qatr, b, queued=True)
    return trades, census
