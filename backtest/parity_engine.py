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


@dataclass(frozen=True)
class LifecycleMark:
    """One non-final lifecycle cashflow emitted by a custom execution model.

    ``kind`` is intentionally generic, but ``partial_fill`` is the supported
    seat-retaining lifecycle event used by the v1.30 resolver.  ``epoch`` is
    the modeled event time; it need not be the bar-open epoch.
    """
    kind: str
    bar: int
    epoch: int
    price: float
    r_component: float
    reason: str = ""


@dataclass(frozen=True)
class ExecutionPlan:
    """Resolved lifecycle returned by an optional ``run_live`` execution hook."""
    exit_bar: int
    exit_price: float
    reason: str
    total_r: float
    free_epoch: int
    entry_r_component: float = 0.0
    marks: tuple[LifecycleMark, ...] = ()


CASHFLOW_MARK_KINDS = frozenset({"partial_fill"})


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
    active: object | None = None   # pending/lifecycle metadata for event emission


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
             window=EXPIRY, replace_on_signal=False, execution=None,
             event_sink=None, day_key=None):
    """thr: None (no engine W2) | dict name->min adverse wick (pre-entry predicate).
    caps: None (per-symbol only) | dict(global=2, cluster=1, fills_day=8, consec=4).
    window: pending fill window in bars. 3 = validated-engine intent; 4 = live
    as-deployed (FTMO journal ground truth 2026-07-10: order #493361350 placed
    12:00:02, cancelled 13:00:02 -- MQL5 Bars() does NOT count the placement bar,
    so ageBars>3 first fires at the open of i+5).
    ``execution`` is an optional object with two methods::

        find_fill(s, side, entry, w_start, w_end) -> int
        resolve(s, sig_i, entry_bar, side, entry, atr_sig) -> ExecutionPlan

    When omitted, the historical touch/bracket path is used unchanged.
    ``event_sink``, when supplied, is called with deterministic dictionary
    snapshots for signal rejection, pending placement/cancellation, entry fill,
    custom lifecycle marks, and final exit.  With both arguments omitted this
    extension has no externally visible effect.  ``day_key(epoch)`` optionally
    supplies the account-day bucket used by fill and day-stop gates; its default
    remains the historical UTC ``epoch // 86400`` behavior.

    Returns (trades, census)."""
    ns = len(symbols)
    st = [SymState() for _ in range(ns)]
    census = Census()
    trades: list[Trade] = []
    fills_day: dict[object, int] = {}
    consec_day: dict[object, int] = {}
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

    def account_day(epoch):
        epoch = int(epoch)
        return epoch // 86400 if day_key is None else day_key(epoch)

    event_seq = 0

    def state_name(si):
        if st[si].status == FREE:
            return "free"
        return "pending" if st[si].phase == 1 else "position"

    def snapshot(si):
        return {
            "state": state_name(si),
            "global": busy_count(),
            "cluster": cluster_count(symbols[si].cluster),
        }

    def key_for(si, sig_i, side):
        signal_epoch = int(symbols[si].ep[sig_i])
        return f"{symbols[si].name}:{signal_epoch}:{int(side)}"

    def emit(kind, si, *, epoch, bar, sig_i, side, price=None,
             r_component=None, total_r=None, reason="", entry_bar=None,
             exit_bar=None, before=None, after=None, trade_key=None,
             scheduler_epoch=None):
        """Send a normalized immutable-by-convention snapshot to ``event_sink``."""
        nonlocal event_seq
        if event_sink is None:
            return
        event_seq += 1
        before = snapshot(si) if before is None else before
        after = snapshot(si) if after is None else after
        event_sink({
            "sequence": event_seq,
            "kind": str(kind),
            "trade_key": trade_key or key_for(si, sig_i, side),
            "symbol": symbols[si].name,
            "epoch": int(epoch),
            "scheduler_epoch": int(epoch if scheduler_epoch is None else scheduler_epoch),
            "bar": int(bar),
            "signal_bar": int(sig_i),
            "entry_bar": None if entry_bar is None else int(entry_bar),
            "exit_bar": None if exit_bar is None else int(exit_bar),
            "side": int(side),
            "price": None if price is None else float(price),
            "r_component": None if r_component is None else float(r_component),
            "total_r": None if total_r is None else float(total_r),
            "reason": str(reason),
            "state_before": before["state"],
            "state_after": after["state"],
            "global_before": int(before["global"]),
            "global_after": int(after["global"]),
            "cluster_before": int(before["cluster"]),
            "cluster_after": int(after["cluster"]),
        })

    def reject(si, i, reason):
        s = symbols[si]
        side = int(s.side[i])
        a = s.atr[i]
        price = s.c[i] - OFFSET * a * side
        snap = snapshot(si)
        event_ep = s.ep[i + 1] if i + 1 < len(s.ep) else s.ep[i] + BAR_SEC
        emit("signal_rejection", si, epoch=event_ep, bar=i, sig_i=i,
             side=side, price=price, reason=reason, before=snap, after=snap)

    def book(si, tr, modeled_exit_epoch):
        trades.append(tr)
        if caps is not None:
            # Preserve the historical UTC tape exactly when day_key is absent.
            # A custom account calendar owns TIME exits at their next-open event.
            day_epoch = (symbols[si].ep[tr.exit_bar] if day_key is None
                         else modeled_exit_epoch)
            d = account_day(day_epoch)
            if tr.r < 0:
                consec_day[d] = consec_day.get(d, 0) + 1
            elif tr.r > 0 or execution is None:
                # Legacy path historically reset on zero.  Custom/live v1.30
                # mirrors ConsecutiveLossesToday(): zero leaves the streak.
                consec_day[d] = 0

    def place(si, sig_i, side, entry, atr_sig, w_start, queued=False):
        """Arm a pending: schedule fill/exit or cancel. w_start=first fill bar."""
        s = symbols[si]
        before = snapshot(si)
        place_ep = s.ep[w_start] if w_start < len(s.ep) else s.ep[-1] + BAR_SEC
        if st[si].status == BUSY and st[si].phase == 1 and st[si].active is not None:
            old = st[si].active
            emit("pending_cancellation", si, epoch=place_ep, bar=w_start,
                 sig_i=old["sig_i"], side=old["side"], price=old["entry"],
                 reason="replaced", before=before, after=before,
                 trade_key=old["trade_key"])
        st[si].status = BUSY
        st[si].phase = 1
        st[si].pend_token += 1
        tok = st[si].pend_token
        if execution is None:
            j = find_fill(s, side, entry, w_start, sig_i + window)
        else:
            j = execution.find_fill(s, side, entry, w_start, sig_i + window)
        if not isinstance(j, (int, np.integer)):
            raise TypeError("execution.find_fill must return an integer bar or -1")
        j = int(j)
        last_fill = min(sig_i + window, len(s.c) - 1)
        if j >= 0 and not (w_start <= j <= last_fill):
            raise ValueError(
                f"execution fill bar {j} outside [{w_start}, {last_fill}] for {s.name}"
            )
        active = {
            "trade_key": key_for(si, sig_i, side),
            "sig_i": int(sig_i),
            "side": int(side),
            "entry": float(entry),
            "atr_sig": float(atr_sig),
            "queued": bool(queued),
            "fill_bar": j,
            "plan": None,
        }
        st[si].active = active
        emit("pending_placement", si, epoch=place_ep, bar=w_start, sig_i=sig_i,
             side=side, price=entry, reason="queued" if queued else "signal",
             before=before, after=snapshot(si), trade_key=active["trade_key"])
        if j < 0:
            cb = sig_i + window + 1
            cancel_ep = s.ep[cb] if cb < len(s.c) else s.ep[-1] + BAR_SEC
            push(cancel_ep, P_MGMT, 0, "cancel", (si, tok, cb, active))
            return
        # fill happens intrabar of bar j: day-gate visibility from close of j
        if execution is None:
            xb, xp, reason = resolve_bracket(s, j, side, entry, atr_sig)
            total_r = trade_r(s, side, entry, xp, atr_sig)
            if reason == "TIME" and xb + 1 < len(s.c):
                free_ep = s.ep[xb + 1]      # EA closes at next bar's open, seat frees then
            else:
                free_ep = s.ep[xb] + BAR_SEC  # broker exit; seat free by bar close
            plan = ExecutionPlan(xb, xp, reason, total_r, int(free_ep))
        else:
            plan = execution.resolve(s, sig_i, j, side, entry, atr_sig)
            if not isinstance(plan, ExecutionPlan):
                raise TypeError("execution.resolve must return ExecutionPlan")
        if not (j <= plan.exit_bar < len(s.c)):
            raise ValueError(
                f"execution exit bar {plan.exit_bar} outside [{j}, {len(s.c) - 1}] "
                f"for {s.name}"
            )
        fill_scheduler_ep = int(s.ep[j]) + BAR_SEC
        previous_mark = None
        for mark in plan.marks:
            if not isinstance(mark, LifecycleMark):
                raise TypeError("ExecutionPlan.marks must contain LifecycleMark values")
            if not (j <= mark.bar <= plan.exit_bar):
                raise ValueError(
                    f"lifecycle mark bar {mark.bar} outside [{j}, {plan.exit_bar}]"
                )
            bar_open = int(s.ep[mark.bar])
            if not (bar_open <= int(mark.epoch) < bar_open + BAR_SEC):
                raise ValueError("lifecycle mark epoch must fall inside its modeled bar")
            mark_order = (int(mark.bar), int(mark.epoch))
            if previous_mark is not None and mark_order < previous_mark:
                raise ValueError("lifecycle marks must be ordered by bar and epoch")
            previous_mark = mark_order
        last_scheduler_ep = (fill_scheduler_ep if not plan.marks else
                             int(s.ep[plan.marks[-1].bar]) + BAR_SEC)
        if int(plan.free_epoch) < last_scheduler_ep:
            raise ValueError("execution free_epoch precedes its lifecycle")
        active["plan"] = plan
        tr = Trade(s.name, sig_i, j, int(plan.exit_bar), side, plan.total_r,
                   plan.reason, int(s.ep[sig_i]), s.cost, queued=queued)
        push(fill_scheduler_ep, P_MGMT, 0, "fill", (si, j, tok, active))
        for mark in plan.marks:
            mark_scheduler_ep = int(s.ep[mark.bar]) + BAR_SEC
            push(mark_scheduler_ep, P_MGMT, 0, "mark", (si, mark, tok, active))
        push(plan.free_epoch, P_MGMT, 0, "exit", (si, tr, tok, active))

    def try_place_signal(si, i):
        """Scan verdict for signal bar i of symbol si. Returns 'placed'/'blocked_cap'/None."""
        s = symbols[si]
        sd = int(s.side[i])
        if sd == 0:
            return None
        if thr is not None and not (np.isfinite(s.watr[i]) and s.watr[i] >= thr[s.name]):
            census.w2_fail += 1
            reject(si, i, "pre_entry_predicate")
            return None
        if caps is not None:
            d = account_day(s.ep[i + 1])
            if fills_day.get(d, 0) >= caps["fills_day"]:
                census.day_fills += 1
                reject(si, i, "fills_day_cap")
                return None
            if consec_day.get(d, 0) >= caps["consec"]:
                census.day_consec += 1
                reject(si, i, "consecutive_loss_day_stop")
                return None
            if busy_count() >= caps["global"]:
                census.cap_global += 1
                reject(si, i, "global_cap")
                return "blocked_cap"
            if cluster_count(s.cluster) >= caps["cluster"]:
                census.cap_cluster += 1
                reject(si, i, "cluster_cap")
                return "blocked_cap"
        a = s.atr[i]
        place(si, i, sd, s.c[i] - OFFSET * a * sd, a, i + 1)
        return "placed"

    while heap:
        epoch, prio, sub, _, kind, payload = heapq.heappop(heap)
        if kind == "cancel":
            si, tok, cb, active = payload
            if st[si].status == BUSY and st[si].pend_token == tok:
                before = snapshot(si)
                st[si].status = FREE
                st[si].phase = 0
                st[si].active = None
                emit("pending_cancellation", si, epoch=epoch, bar=cb,
                     sig_i=active["sig_i"], side=active["side"],
                     price=active["entry"], reason="unfilled_expiry",
                     before=before, after=snapshot(si),
                     trade_key=active["trade_key"])
        elif kind == "fill":
            si, j, tok, active = payload
            if st[si].pend_token != tok:
                continue                    # pending was replaced before its fill
            before = snapshot(si)
            st[si].phase = 2
            d = account_day(symbols[si].ep[j])
            fills_day[d] = fills_day.get(d, 0) + 1
            modeled_epoch = int(symbols[si].ep[j]) + BAR_SEC - 1
            emit("entry_fill", si, epoch=modeled_epoch, scheduler_epoch=epoch, bar=j,
                 sig_i=active["sig_i"], side=active["side"],
                 price=active["entry"], r_component=active["plan"].entry_r_component,
                 total_r=active["plan"].total_r, reason="limit_fill",
                 entry_bar=j, before=before, after=snapshot(si),
                 trade_key=active["trade_key"])
        elif kind == "mark":
            si, mark, tok, active = payload
            if st[si].pend_token != tok:
                continue                    # lifecycle voided by replacement
            snap = snapshot(si)
            emit(mark.kind, si, epoch=mark.epoch, scheduler_epoch=epoch, bar=mark.bar,
                 sig_i=active["sig_i"], side=active["side"],
                 price=mark.price, r_component=mark.r_component,
                 total_r=active["plan"].total_r, reason=mark.reason,
                 entry_bar=active["fill_bar"], before=snap, after=snap,
                 trade_key=active["trade_key"])
        elif kind == "exit":
            si, tr, tok, active = payload
            if st[si].pend_token != tok:
                continue                    # lifecycle voided by replacement
            before = snapshot(si)
            st[si].status = FREE
            st[si].phase = 0
            st[si].active = None
            st[si].no_sig_upto = max(st[si].no_sig_upto, tr.exit_bar)
            plan = active["plan"]
            modeled_epoch = (int(plan.free_epoch) if plan.reason == "TIME" else
                             int(symbols[si].ep[tr.exit_bar]) + BAR_SEC - 1)
            book(si, tr, modeled_epoch)
            marked_r = sum(float(mark.r_component) for mark in plan.marks
                           if mark.kind in CASHFLOW_MARK_KINDS)
            emit("final_exit", si, epoch=modeled_epoch, scheduler_epoch=epoch,
                 bar=tr.exit_bar,
                 sig_i=active["sig_i"], side=active["side"],
                 price=plan.exit_price,
                 r_component=plan.total_r - plan.entry_r_component - marked_r,
                 total_r=plan.total_r, reason=plan.reason,
                 entry_bar=active["fill_bar"], exit_bar=tr.exit_bar,
                 before=before, after=snapshot(si),
                 trade_key=active["trade_key"])
        elif kind == "open":
            si, b = payload
            s = symbols[si]
            i = b - 1                       # just-closed signal bar (shift 1)
            if st[si].status == BUSY:
                raw_signal = s.side[i] != 0
                fresh = raw_signal and (thr is None or
                                        (np.isfinite(s.watr[i]) and s.watr[i] >= thr[s.name]))
                if (replace_on_signal and fresh and st[si].phase == 1
                        and i > st[si].no_sig_upto):
                    # newest-signal-wins: cancel the working pending, re-anchor.
                    # Capacity unchanged (same slot); day gates still apply.
                    okday = True
                    if caps is not None:
                        d = account_day(s.ep[b])
                        okday = (fills_day.get(d, 0) < caps["fills_day"]
                                 and consec_day.get(d, 0) < caps["consec"])
                    if okday:
                        sd = int(s.side[i])
                        a = s.atr[i]
                        place(si, i, sd, s.c[i] - OFFSET * a * sd, a, i + 1)
                        continue
                if fresh:
                    census.occupied += 1
                    reject(si, i, "symbol_occupied")
                elif raw_signal:
                    reject(si, i, "pre_entry_predicate")
                continue
            if i <= st[si].no_sig_upto:
                if s.side[i] != 0:
                    census.cooldown += 1
                    reject(si, i, "cooldown")
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
                                d = account_day(s.ep[b])
                                okday = (fills_day.get(d, 0) < caps["fills_day"]
                                         and consec_day.get(d, 0) < caps["consec"])
                            if okday and (caps is None or
                                          (busy_count() < caps["global"]
                                           and cluster_count(s.cluster) < caps["cluster"])):
                                st[si].queued = None
                                census.q_released += 1
                                place(si, qi, qsd, qentry, qatr, b, queued=True)
    return trades, census
