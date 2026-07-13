"""Build the preregistered derived H1 PassTape for account testing."""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from parity_engine import prep_symbol, START
from session_study import TRIO
from walkforward_dsr import real_cost_per_side
from v130_pass_policy import AccountEvent, PassTape

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "derivM15_spreadgated")
PRAGUE = ZoneInfo("Europe/Prague")
MAP = {"Wall_Street_30": "US30.cash", "US_Tech_100": "US100.cash", "Japan_225": "JP225.cash"}


def aggregate_h1(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    dt = pd.to_datetime(df["time"])
    df["_dt"] = dt
    df["_hour"] = dt.dt.floor("h")
    rows = []
    for hour, g in df.groupby("_hour", sort=True):
        g = g.sort_values("_dt")
        expected = [hour + pd.Timedelta(minutes=15 * k) for k in range(4)]
        if len(g) != 4 or list(g["_dt"]) != expected:
            continue
        rows.append({"time": hour, "open": float(g.iloc[0]["open"]),
                     "high": float(g["high"].max()), "low": float(g["low"].min()),
                     "close": float(g.iloc[-1]["close"]), "volume": float(g["volume"].sum()),
                     "spread_price": float(g["spread_price"].max())})
    return pd.DataFrame(rows)


def _epoch(value) -> int:
    return int(pd.Timestamp(value).timestamp())


def _event(event_id, trade_id, symbol, cluster, side, epoch, sequence, kind, **kwargs):
    return AccountEvent(event_id=event_id, trade_id=trade_id, symbol=symbol,
                        cluster=cluster, epoch=int(epoch), sequence=int(sequence),
                        kind=kind, side=int(side), **kwargs)


def build_h1_tape(*, stress: bool = False) -> tuple[PassTape, dict[str, object]]:
    events = []
    seq = 0
    first_epoch = None
    last_epoch = None
    counts = {}
    for source_symbol in TRIO:
        raw = pd.read_csv(os.path.join(DATA, source_symbol + ".csv"))
        h1 = aggregate_h1(raw)
        cost = real_cost_per_side(h1) * (2.0 if stress else 1.0)
        s = prep_symbol(h1, cost, source_symbol)
        symbol = MAP[source_symbol]
        cluster = "0" if symbol in {"US30.cash", "US100.cash"} else "1"
        s.oos = np.arange(len(h1)) >= int(len(h1) * 0.7)
        i = START
        n_trades = 0
        while i < len(s.c) - 5:
            side = int(s.side[i])
            if side == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < 0.30:
                i += 1
                continue
            trade_id = f"H1:{symbol}:{i}"
            signal_atr = float(s.atr[i])
            entry = float(s.c[i] - 0.6 * signal_atr * side)
            fill = -1
            for b in range(i + 1, min(i + 4, len(s.c))):
                if (side > 0 and s.l[b] <= entry) or (side < 0 and s.h[b] >= entry):
                    fill = b
                    break
            open_epoch = _epoch(h1.iloc[i]["time"]) + 3599
            seq += 1
            events.append(_event(f"{trade_id}:open", trade_id, symbol, cluster, side,
                                 open_epoch, seq, "pending_open", price=entry,
                                 stop_distance=signal_atr, fixed_slippage_r=0.0,
                                 remaining_fraction=1.0, mark_role="neutral"))
            first_epoch = open_epoch if first_epoch is None else min(first_epoch, open_epoch)
            if fill < 0:
                cancel_epoch = _epoch(h1.iloc[i + 4]["time"])
                seq += 1
                events.append(_event(f"{trade_id}:cancel", trade_id, symbol, cluster, side,
                                     cancel_epoch, seq, "pending_cancel", price=entry,
                                     stop_distance=signal_atr, fixed_slippage_r=0.0,
                                     remaining_fraction=1.0, mark_role="neutral"))
                last_epoch = cancel_epoch if last_epoch is None else max(last_epoch, cancel_epoch)
                i += 4
                continue
            sl = entry - signal_atr * side
            tp = entry + 2.0 * signal_atr * side
            partial = None
            exit_bar = None
            exit_price = None
            for k in range(fill, min(fill + 8, len(s.c))):
                if side > 0:
                    if s.l[k] <= sl:
                        exit_bar, exit_price = k, sl
                        break
                    if partial is None and s.h[k] >= entry + signal_atr:
                        partial = k
                    if s.h[k] >= tp:
                        exit_bar, exit_price = k, tp
                        break
                else:
                    if s.h[k] >= sl:
                        exit_bar, exit_price = k, sl
                        break
                    if partial is None and s.l[k] <= entry - signal_atr:
                        partial = k
                    if s.l[k] <= tp:
                        exit_bar, exit_price = k, tp
                        break
            if exit_bar is None:
                exit_bar = min(fill + 7, len(s.c) - 1)
                exit_price = float(s.c[exit_bar])
            entry_epoch = _epoch(h1.iloc[fill]["time"])
            seq += 1
            events.append(_event(f"{trade_id}:entry", trade_id, symbol, cluster, side,
                                 entry_epoch, seq, "entry", price=entry,
                                 stop_distance=signal_atr, fixed_slippage_r=cost,
                                 remaining_fraction=1.0, mark_role="neutral"))
            for k in range(fill, exit_bar):
                if partial == k:
                    p_epoch = _epoch(h1.iloc[k]["time"]) + 3599
                    seq += 1
                    events.append(_event(f"{trade_id}:partial", trade_id, symbol, cluster, side,
                                         p_epoch, seq, "partial", price=entry + side * signal_atr,
                                         stop_distance=signal_atr, fixed_slippage_r=0.0,
                                         remaining_fraction=0.5, mark_role="favorable"))
                    continue
                mark_epoch = _epoch(h1.iloc[k]["time"]) + 3599
                mark_price = float(s.c[k])
                role = "favorable" if (mark_price - entry) * side > 0 else "adverse"
                seq += 1
                events.append(_event(f"{trade_id}:mark:{k}", trade_id, symbol, cluster, side,
                                     mark_epoch, seq, "mark", price=mark_price,
                                     stop_distance=signal_atr, fixed_slippage_r=0.0,
                                     remaining_fraction=0.5 if partial is not None and k > partial else 1.0,
                                     mark_role=role))
            final_epoch = _epoch(h1.iloc[exit_bar]["time"]) + 3599
            seq += 1
            events.append(_event(f"{trade_id}:final", trade_id, symbol, cluster, side,
                                 final_epoch, seq, "final", price=float(exit_price),
                                 stop_distance=signal_atr, fixed_slippage_r=0.0,
                                 remaining_fraction=0.0, mark_role="neutral"))
            last_epoch = final_epoch if last_epoch is None else max(last_epoch, final_epoch)
            n_trades += 1
            i = exit_bar + 1
        counts[symbol] = n_trades
    # Apply the live portfolio seats after the per-symbol H1 enumeration.  The
    # screen is per-symbol; the account tape must enforce one US-index cluster
    # seat and two global seats in deterministic whitelist order.
    grouped = {}
    for event in events:
        grouped.setdefault(event.trade_id, []).append(event)
    order = {"US30.cash": 0, "US100.cash": 1, "JP225.cash": 2}
    intervals = []
    for trade_id, rows in grouped.items():
        opening = next(row for row in rows if row.kind == "pending_open")
        ending = max(row.epoch for row in rows if row.kind in {"pending_cancel", "final"})
        intervals.append((opening.epoch, order[opening.symbol], trade_id, opening.symbol, opening.cluster, ending))
    active = []
    accepted = set()
    for placement, _, trade_id, symbol, cluster, ending in sorted(intervals):
        # Equality remains occupied: source event ordering can place a new
        # pending before a same-epoch final, so free only after the terminal
        # epoch has strictly passed the placement epoch.
        active = [x for x in active if x[5] >= placement]
        if any(x[3] == symbol for x in active) or any(x[4] == cluster for x in active) or len(active) >= 2:
            continue
        accepted.add(trade_id)
        active.append((placement, 0, trade_id, symbol, cluster, ending))
    events = [event for event in events if event.trade_id in accepted]
    counts = {symbol: sum(1 for trade_id in accepted if trade_id.startswith(f"H1:{symbol}:")) for symbol in MAP.values()}
    first_day = datetime.fromtimestamp(first_epoch, timezone.utc).astimezone(PRAGUE).date()
    last_day = datetime.fromtimestamp(last_epoch, timezone.utc).astimezone(PRAGUE).date()
    tape = PassTape.from_events(events, first_day=first_day, last_day=last_day)
    return tape, counts


if __name__ == "__main__":
    tape, counts = build_h1_tape()
    print("H1_TAPE", tape.n_days, len(tape.events), len(tape.trades), counts)
