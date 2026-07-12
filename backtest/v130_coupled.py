"""Coupled v1.30 execution tape for the preregistered FTMO risk study.

This module contains no policy search.  It adapts the deterministic portfolio
scheduler in :mod:`parity_engine` to the frozen v1.30 geometry and to the
registered D0/F1/F2 execution columns.  Blind FTMO splits are denied by default;
callers must opt in explicitly after the preceding gate has been recorded.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

from freeze_ftmo_v130_blind import verify_manifest as verify_blind_manifest
from parity_engine import (
    BAR_SEC,
    START,
    ExecutionPlan,
    LifecycleMark,
    SymData,
    prep_symbol,
    run_live,
)
from walkforward_dsr import real_cost_per_side


SYMBOLS = ("US30.cash", "US100.cash", "JP225.cash")
CLUSTERS = {"US30.cash": 0, "US100.cash": 0, "JP225.cash": 1}
CAPS = {"global": 2, "cluster": 1, "fills_day": 8, "consec": 4}
W2 = {symbol: 0.30 for symbol in SYMBOLS}
WINDOW = 4
HOLD = 8
STOP_ATR = 1.0
TP_ATR = 2.0
PARTIAL_AT_R = 1.0
PARTIAL_FRACTION = 0.50

D0_TOUCH = "D0_TOUCH"
F1_PER_BAR = "F1_PER_BAR"
F2_STRICT_ASK = "F2_STRICT_ASK"
F2_STRICT_ASK_2X = "F2_STRICT_ASK_2X"
FILL_MODES = (D0_TOUCH, F1_PER_BAR, F2_STRICT_ASK, F2_STRICT_ASK_2X)

BLIND_DIR = HERE / "data" / "ftmoM15_blind_20260711"
SPLIT_SLICES = {
    "holdout": slice(0, 39_999),
    "confirmation": slice(39_999, 69_999),
    "mined": slice(69_999, 99_999),
}
PRAGUE = ZoneInfo("Europe/Prague")
EA_SERVER = ZoneInfo("Europe/Helsinki")


@dataclass(frozen=True)
class FrozenInputs:
    split: str
    symbols: tuple[SymData, ...]
    spreads: dict[str, np.ndarray]
    metadata: dict
    split_metadata: dict


@dataclass(frozen=True)
class CoupledTape:
    mode: str
    trades: tuple
    events: tuple[dict, ...]
    census: object
    normalized_sha256: str


def prague_day(epoch: int) -> str:
    """Stable FTMO account-day key, including CE(S)T daylight saving."""
    return datetime.fromtimestamp(int(epoch), timezone.utc).astimezone(PRAGUE).date().isoformat()


def ea_server_day(epoch: int) -> str:
    """Deployed EA DayStart(TimeCurrent()) calendar (FTMO server EET/EEST)."""
    return datetime.fromtimestamp(int(epoch), timezone.utc).astimezone(EA_SERVER).date().isoformat()


def _load_json(name: str) -> dict:
    return json.loads((BLIND_DIR / name).read_text(encoding="utf-8"))


def load_ftmo_split(split: str, *, authorize_blind: bool = False) -> FrozenInputs:
    """Load one exact frozen split through an NPY mmap.

    ``mined`` is development-only and is always permitted.  Confirmation and
    holdout require an explicit flag so a generic test/import cannot consume a
    blind frame accidentally.  The full manifest is verified before mapping;
    only the selected row slice is materialized into OHLC arrays.
    """
    if split not in SPLIT_SLICES:
        raise ValueError(f"unknown FTMO split: {split!r}")
    if split != "mined" and not authorize_blind:
        raise PermissionError(
            f"{split} is sealed; pass authorize_blind=True only after its prior gate"
        )
    verify_blind_manifest()
    metadata = _load_json("METADATA.json")
    split_metadata = _load_json("SPLIT.json")
    row_slice = SPLIT_SLICES[split]
    symbols: list[SymData] = []
    spreads: dict[str, np.ndarray] = {}

    for symbol in SYMBOLS:
        stem = symbol.replace(".", "_")
        mapped = np.load(
            BLIND_DIR / f"{stem}_M15_99999.npy", mmap_mode="r", allow_pickle=False
        )
        selected = mapped[row_slice]
        registered = split_metadata["symbols"][symbol][split]
        expected_rows = int(registered["rows"])
        if len(selected) != expected_rows:
            raise RuntimeError(
                f"{symbol}/{split}: expected {expected_rows} rows, got {len(selected)}"
            )
        epochs = np.asarray(selected["time"], dtype=np.int64)
        if int(epochs[0]) != int(registered["start_epoch"]):
            raise RuntimeError(f"{symbol}/{split}: start epoch mismatch")
        if int(epochs[-1]) != int(registered["end_epoch"]):
            raise RuntimeError(f"{symbol}/{split}: end epoch mismatch")

        point = float(metadata["symbols"][symbol]["point"])
        spread_price = np.asarray(selected["spread"], dtype=float) * point
        frame = pd.DataFrame(
            {
                "time": pd.to_datetime(epochs, unit="s", utc=True),
                "open": np.asarray(selected["open"], dtype=float),
                "high": np.asarray(selected["high"], dtype=float),
                "low": np.asarray(selected["low"], dtype=float),
                "close": np.asarray(selected["close"], dtype=float),
                "spread_price": spread_price,
            }
        )
        cost = real_cost_per_side(frame)
        if not np.isfinite(cost) or cost < 0:
            raise RuntimeError(f"{symbol}/{split}: invalid registered transaction cost")
        symbols.append(prep_symbol(frame, float(cost), symbol, CLUSTERS[symbol]))
        spreads[symbol] = spread_price.copy()

    return FrozenInputs(split, tuple(symbols), spreads, metadata, split_metadata)


class V130Execution:
    """Observed-spread v1.30 fill and lifecycle semantics."""

    def __init__(self, spreads: dict[str, np.ndarray], mode: str):
        if mode not in FILL_MODES:
            raise ValueError(f"unknown execution mode: {mode!r}")
        missing = set(SYMBOLS) - set(spreads)
        if missing:
            raise ValueError(f"missing spread arrays: {sorted(missing)}")
        self.spreads = spreads
        self.mode = mode
        self.cost_mult = 2.0 if mode == F2_STRICT_ASK_2X else 1.0

    def _spread(self, s: SymData, bar: int) -> float:
        value = float(self.spreads[s.name][bar])
        if not np.isfinite(value) or value < 0:
            raise RuntimeError(f"{s.name} bar {bar}: invalid observed spread {value}")
        return value

    def find_fill(
        self, s: SymData, side: int, entry: float, w_start: int, w_end: int
    ) -> int:
        for bar in range(w_start, min(w_end + 1, len(s.c))):
            if side > 0:
                touched = (
                    s.l[bar] <= entry
                    if self.mode == D0_TOUCH
                    else s.l[bar] + self._spread(s, bar) <= entry
                )
            else:
                touched = s.h[bar] >= entry
            if touched:
                return int(bar)
        return -1

    def resolve(
        self,
        s: SymData,
        sig_i: int,
        entry_bar: int,
        side: int,
        entry: float,
        atr_sig: float,
    ) -> ExecutionPlan:
        del sig_i  # carried by the scheduler/event sink; geometry needs no look-ahead.
        risk = STOP_ATR * float(atr_sig)
        if not np.isfinite(risk) or risk <= 0:
            raise ValueError("signal ATR risk must be positive and finite")
        stop = entry - side * risk
        partial = entry + side * PARTIAL_AT_R * risk
        target = entry + side * TP_ATR * float(atr_sig)
        partial_done = False
        marks: list[LifecycleMark] = []
        exit_bar = None
        exit_price = None
        reason = ""

        for bar in range(entry_bar, min(entry_bar + HOLD, len(s.c))):
            high, low = float(s.h[bar]), float(s.l[bar])
            spread = self._spread(s, bar) if self.mode != D0_TOUCH else 0.0
            if side > 0:
                stop_hit = low <= stop
                partial_hit = high >= partial
                target_hit = high >= target
            else:
                stop_hit = (
                    high + spread >= stop
                    if self.mode in (F2_STRICT_ASK, F2_STRICT_ASK_2X)
                    else high >= stop
                )
                partial_hit = (
                    low <= partial
                    if self.mode == D0_TOUCH
                    else low + spread <= partial
                )
                target_hit = (
                    low <= target
                    if self.mode == D0_TOUCH
                    else low + spread <= target
                )

            # Registered pessimism: stop first, then partial, then target.
            if stop_hit:
                exit_bar, exit_price, reason = bar, stop, "SL"
                break
            if side > 0:
                favorable_price = target if target_hit else high
                adverse_price = low
            else:
                if self.mode == D0_TOUCH:
                    favorable_price = target if target_hit else low
                    adverse_price = high
                else:
                    favorable_price = target if target_hit else low + spread
                    adverse_price = high + spread
            mark_epoch = int(s.ep[bar]) + BAR_SEC - 1

            def append_partial():
                nonlocal partial_done
                partial_done = True
                marks.append(
                    LifecycleMark(
                        "partial_fill",
                        int(bar),
                        mark_epoch,
                        float(partial),
                        PARTIAL_FRACTION * PARTIAL_AT_R,
                        "+1R half:favorable",
                    )
                )

            def append_bar_mark(price, role):
                marks.append(
                    LifecycleMark(
                        "bar_mark", int(bar), mark_epoch, float(price), 0.0,
                        f"coherent_stress:{role}",
                    )
                )

            if target_hit:
                # Coherent target-bar order: adverse excursion first, then the
                # registered partial and target.  No adverse envelope is
                # applied after the position has reached its target.
                append_bar_mark(adverse_price, "adverse")
                if not partial_done and partial_hit:
                    append_partial()
                append_bar_mark(favorable_price, "favorable")
            else:
                if not partial_done and partial_hit:
                    append_partial()
                # With no terminating bracket touch, high/low order is unknown;
                # favorable-then-adverse is the binding conservative stress.
                append_bar_mark(favorable_price, "favorable")
                append_bar_mark(adverse_price, "adverse")
            if target_hit:
                exit_bar, exit_price, reason = bar, target, "TP"
                break

        if exit_bar is None:
            exit_bar = min(entry_bar + HOLD - 1, len(s.c) - 1)
            exit_price = float(s.c[exit_bar])
            reason = "TIME"

        remaining = 1.0 - (PARTIAL_FRACTION if partial_done else 0.0)
        gross_final_r = remaining * (float(exit_price) - entry) * side / risk
        entry_cost_r = -2.0 * float(s.cost) * self.cost_mult / STOP_ATR
        partial_r = sum(mark.r_component for mark in marks)
        total_r = entry_cost_r + partial_r + gross_final_r
        if reason == "TIME" and exit_bar + 1 < len(s.c):
            free_epoch = int(s.ep[exit_bar + 1])
        else:
            free_epoch = int(s.ep[exit_bar]) + BAR_SEC
        return ExecutionPlan(
            int(exit_bar),
            float(exit_price),
            reason,
            float(total_r),
            int(free_epoch),
            entry_r_component=float(entry_cost_r),
            marks=tuple(marks),
        )


def normalized_event_bytes(events: list[dict] | tuple[dict, ...]) -> bytes:
    return (
        json.dumps(
            list(events),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def replay_invariants(events: list[dict] | tuple[dict, ...]) -> dict[str, int]:
    """Replay structural and R-component invariants for a completed tape."""
    active: dict[str, dict] = {}
    completed = 0
    partials = 0
    expected_sequence = 1
    for event in events:
        if int(event["sequence"]) != expected_sequence:
            raise AssertionError("event sequence is not contiguous")
        expected_sequence += 1
        if int(event["global_before"]) > CAPS["global"] or int(event["global_after"]) > CAPS["global"]:
            raise AssertionError("global occupancy exceeded")
        if int(event["cluster_before"]) > CAPS["cluster"] or int(event["cluster_after"]) > CAPS["cluster"]:
            raise AssertionError("cluster occupancy exceeded")

        kind = event["kind"]
        key = event["trade_key"]
        if kind == "pending_placement":
            if key in active:
                raise AssertionError(f"duplicate active trade key: {key}")
            active[key] = {"events": [event], "partial": 0}
        elif kind == "signal_rejection":
            continue
        elif kind == "pending_cancellation":
            if event["reason"] == "replaced":
                # Replacement cancellation is immediately followed by a new
                # placement for a distinct trade key; it never frees capacity.
                active.pop(key, None)
            else:
                if key not in active:
                    raise AssertionError(f"cancellation without placement: {key}")
                active.pop(key)
        elif kind == "entry_fill":
            if key not in active:
                raise AssertionError(f"fill without placement: {key}")
            sig = int(event["signal_bar"])
            fill = int(event["entry_bar"])
            if not (sig + 1 <= fill <= sig + WINDOW):
                raise AssertionError(f"fill outside registered window: {key}")
            active[key]["events"].append(event)
        elif kind == "partial_fill":
            if key not in active:
                raise AssertionError(f"partial without active trade: {key}")
            if active[key]["partial"]:
                raise AssertionError(f"multiple partials: {key}")
            if event["state_before"] != "position" or event["state_after"] != "position":
                raise AssertionError("partial freed or changed its seat")
            if event["global_before"] != event["global_after"]:
                raise AssertionError("partial changed global occupancy")
            if event["cluster_before"] != event["cluster_after"]:
                raise AssertionError("partial changed cluster occupancy")
            active[key]["partial"] = 1
            active[key]["events"].append(event)
            partials += 1
        elif kind == "final_exit":
            if key not in active:
                raise AssertionError(f"exit without active trade: {key}")
            rows = active.pop(key)["events"] + [event]
            components = [
                float(row["r_component"])
                for row in rows
                if row["r_component"] is not None
                and row["kind"] in {"entry_fill", "partial_fill", "final_exit"}
            ]
            if abs(sum(components) - float(event["total_r"])) > 1e-12:
                raise AssertionError(f"R-component mismatch: {key}")
            completed += 1

    if active:
        raise AssertionError(f"orphan active lifecycles: {sorted(active)}")
    return {"events": len(events), "completed": completed, "partials": partials}


def run_coupled(inputs: FrozenInputs, mode: str) -> CoupledTape:
    events: list[dict] = []
    execution = V130Execution(inputs.spreads, mode)
    trades, census = run_live(
        list(inputs.symbols),
        thr=W2,
        caps=CAPS,
        queue=False,
        reverse_scan=False,
        window=WINDOW,
        replace_on_signal=False,
        execution=execution,
        event_sink=events.append,
        day_key=ea_server_day,
    )
    summary = replay_invariants(events)
    if summary["completed"] != len(trades):
        raise AssertionError("event replay and trade tape disagree")
    body = normalized_event_bytes(events)
    return CoupledTape(
        mode,
        tuple(trades),
        tuple(events),
        census,
        hashlib.sha256(body).hexdigest(),
    )


def to_account_tape(inputs: FrozenInputs, tape: CoupledTape):
    """Adapt coupled cashflow events to the pure FTMO account simulator.

    Pending/rejection rows remain in ``CoupledTape`` for fidelity auditing but
    are not account cashflows.  Theoretical entry cost is separated from gross
    price R so policy-dependent lot rounding can be applied exactly at replay.
    """
    from v130_risk_policy import (
        CalendarTape,
        EventKind,
        LifecycleEvent,
        OccupancyInterval,
        SymbolMeta,
    )

    sym_by_name = {symbol.name: symbol for symbol in inputs.symbols}
    account_events: list[LifecycleEvent] = []
    remaining: dict[str, float] = {}
    entry_prices: dict[str, float] = {}
    for row in tape.events:
        kind = row["kind"]
        if kind not in {"entry_fill", "bar_mark", "partial_fill", "final_exit"}:
            continue
        name = str(row["symbol"])
        symbol = sym_by_name[name]
        signal_bar = int(row["signal_bar"])
        signal_atr = float(symbol.atr[signal_bar])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            raise AssertionError(f"{name}: invalid frozen signal ATR")
        trade_id = str(row["trade_key"])
        if kind == "entry_fill":
            event_kind = EventKind.ENTRY
            gross_r = 0.0
            open_r = 0.0
            next_remaining = 1.0
            emitted_cost = float(row["r_component"])
            if emitted_cost > FRACTION_TOL:
                raise AssertionError(f"{trade_id}: entry cost has positive sign")
            entry_cost_r = -emitted_cost
            mark_role = "neutral"
            remaining[trade_id] = 1.0
            entry_prices[trade_id] = float(row["price"])
        elif kind == "bar_mark":
            if trade_id not in remaining:
                raise AssertionError(f"{trade_id}: account mark without entry")
            event_kind = EventKind.MARK
            next_remaining = remaining[trade_id]
            gross_r = 0.0
            entry_price = entry_prices[trade_id]
            price_r = (float(row["price"]) - entry_price) * int(row["side"]) / signal_atr
            open_r = price_r * next_remaining
            entry_cost_r = 0.0
            mark_role = (
                "favorable" if str(row["reason"]).endswith(":favorable") else "adverse"
            )
        elif kind == "partial_fill":
            if trade_id not in remaining:
                raise AssertionError(f"{trade_id}: account partial without entry")
            event_kind = EventKind.PARTIAL
            next_remaining = 0.5
            gross_r = float(row["r_component"])
            entry_price = entry_prices[trade_id]
            price_r = (float(row["price"]) - entry_price) * int(row["side"]) / signal_atr
            open_r = price_r * next_remaining
            entry_cost_r = 0.0
            mark_role = "favorable"
            remaining[trade_id] = next_remaining
        else:
            if trade_id not in remaining:
                raise AssertionError(f"{trade_id}: account final without entry")
            event_kind = EventKind.FINAL
            next_remaining = 0.0
            gross_r = float(row["r_component"])
            open_r = 0.0
            entry_cost_r = 0.0
            mark_role = "neutral"
            remaining.pop(trade_id)
            entry_prices.pop(trade_id)

        account_events.append(
            LifecycleEvent(
                event_id=f"{trade_id}:{int(row['sequence'])}:{event_kind.value}",
                trade_id=trade_id,
                symbol=name,
                cluster=str(CLUSTERS[name]),
                epoch=int(row["epoch"]),
                sequence=int(row["sequence"]),
                kind=event_kind,
                side=int(row["side"]),
                price=float(row["price"]),
                r_component=float(gross_r),
                open_r=float(open_r),
                remaining_fraction=float(next_remaining),
                signal_atr=signal_atr,
                stop_distance=STOP_ATR * signal_atr,
                entry_cost_r=float(entry_cost_r),
                mark_role=mark_role,
            )
        )
    if remaining:
        raise AssertionError(f"orphan account trades: {sorted(remaining)}")

    occupancy_starts: dict[str, tuple[int, str]] = {}
    occupancies: list[OccupancyInterval] = []
    completed_trade_ids = {event.trade_id for event in account_events}
    for row in tape.events:
        key = str(row["trade_key"])
        if row["kind"] == "pending_placement":
            if key in occupancy_starts:
                raise AssertionError(f"duplicate pending occupancy start: {key}")
            occupancy_starts[key] = (int(row["epoch"]), str(row["symbol"]))
        elif row["kind"] in {"pending_cancellation", "final_exit"}:
            if key not in occupancy_starts:
                raise AssertionError(f"occupancy end without placement: {key}")
            start_epoch, symbol_name = occupancy_starts.pop(key)
            occupancies.append(
                OccupancyInterval(
                    occupancy_id=f"{key}:{start_epoch}:{int(row['epoch'])}",
                    trade_id=key if key in completed_trade_ids else None,
                    symbol=symbol_name,
                    cluster=str(CLUSTERS[symbol_name]),
                    start_epoch=start_epoch,
                    end_epoch=int(row["epoch"]),
                )
            )
    if occupancy_starts:
        raise AssertionError(f"orphan pending occupancies: {sorted(occupancy_starts)}")

    first_epoch = min(int(s.ep[0]) for s in inputs.symbols)
    last_epoch = max(int(s.ep[-1]) for s in inputs.symbols)
    first_day = datetime.fromtimestamp(first_epoch, timezone.utc).astimezone(PRAGUE).date()
    last_day = datetime.fromtimestamp(last_epoch, timezone.utc).astimezone(PRAGUE).date()
    calendar = CalendarTape.from_events(
        account_events,
        first_day=first_day,
        last_day=last_day,
        timezone_name="Europe/Prague",
        occupancy_intervals=occupancies,
    )
    metas = {
        name: SymbolMeta(
            symbol=name,
            trade_tick_size=float(inputs.metadata["symbols"][name]["trade_tick_size"]),
            trade_tick_value_loss=float(
                inputs.metadata["symbols"][name]["trade_tick_value_loss"]
            ),
            trade_tick_value_profit=float(
                inputs.metadata["symbols"][name]["trade_tick_value_profit"]
            ),
            volume_min=float(inputs.metadata["symbols"][name]["volume_min"]),
            volume_step=float(inputs.metadata["symbols"][name]["volume_step"]),
            volume_max=float(inputs.metadata["symbols"][name]["volume_max"]),
        )
        for name in SYMBOLS
    }
    return calendar, metas


FRACTION_TOL = 1e-12


def assert_mode_identity(left: CoupledTape, right: CoupledTape) -> None:
    """F2 and F2-2x must differ only in registered transaction-cost cashflow."""
    if len(left.trades) != len(right.trades):
        raise AssertionError("mode trade counts differ")
    for a, b in zip(left.trades, right.trades):
        fields_a = (a.sym, a.sig, a.entry_bar, a.exit_bar, a.side, a.reason, a.ep_sig)
        fields_b = (b.sym, b.sig, b.entry_bar, b.exit_bar, b.side, b.reason, b.ep_sig)
        if fields_a != fields_b:
            raise AssertionError(f"mode lifecycle differs: {fields_a} != {fields_b}")
    cash_fields = {"r_component", "total_r"}
    if len(left.events) != len(right.events):
        raise AssertionError("mode event counts differ")
    for a, b in zip(left.events, right.events):
        aa = {k: v for k, v in a.items() if k not in cash_fields}
        bb = {k: v for k, v in b.items() if k not in cash_fields}
        if aa != bb:
            raise AssertionError("mode event lifecycle differs outside cashflow fields")


def synthetic_symbol(
    name: str,
    highs,
    lows,
    closes=None,
    *,
    spread=0.0,
    cost=0.0,
) -> tuple[SymData, np.ndarray]:
    """Small resolver fixture; no repository data is read."""
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    n = len(highs)
    closes = np.full(n, 100.0) if closes is None else np.asarray(closes, dtype=float)
    s = SymData(
        name=name,
        ep=1_700_000_000 + np.arange(n, dtype=np.int64) * BAR_SEC,
        o=np.full(n, 100.0),
        h=highs,
        l=lows,
        c=closes,
        atr=np.ones(n),
        side=np.zeros(n, dtype=np.int8),
        watr=np.full(n, np.nan),
        cost=float(cost),
        cluster=0,
    )
    return s, np.full(n, float(spread))


def self_test() -> None:
    # Stop before partial on the same bar.
    s, spread = synthetic_symbol("US30.cash", [102.0], [98.0], spread=0.2)
    plan = V130Execution({**{x: spread for x in SYMBOLS}}, F1_PER_BAR).resolve(
        s, 0, 0, 1, 100.0, 1.0
    )
    assert plan.reason == "SL" and not plan.marks and abs(plan.total_r + 1.0) < 1e-12

    # Partial and TP on one bar produces +1.5R gross.
    s, spread = synthetic_symbol("US30.cash", [102.1], [99.9])
    plan = V130Execution({**{x: spread for x in SYMBOLS}}, F1_PER_BAR).resolve(
        s, 0, 0, 1, 100.0, 1.0
    )
    assert plan.reason == "TP"
    assert sum(mark.kind == "partial_fill" for mark in plan.marks) == 1
    assert sum(mark.kind == "bar_mark" for mark in plan.marks) == 2
    assert [mark.kind for mark in plan.marks] == ["bar_mark", "partial_fill", "bar_mark"]
    assert plan.marks[0].reason.endswith(":adverse")
    assert plan.marks[-1].reason.endswith(":favorable")
    assert abs(plan.total_r - 1.5) < 1e-12

    # Partial then stop is zero gross before cost.
    s, spread = synthetic_symbol("US30.cash", [101.1, 100.5], [99.9, 98.9])
    plan = V130Execution({**{x: spread for x in SYMBOLS}}, F1_PER_BAR).resolve(
        s, 0, 0, 1, 100.0, 1.0
    )
    assert plan.reason == "SL"
    assert sum(mark.kind == "partial_fill" for mark in plan.marks) == 1
    assert abs(plan.total_r) < 1e-12

    # F2 sees an ask-side short stop that F1's bid high does not see.
    s, spread = synthetic_symbol("US30.cash", [100.9], [99.5], spread=0.2)
    spread_map = {x: spread for x in SYMBOLS}
    f1 = V130Execution(spread_map, F1_PER_BAR).resolve(s, 0, 0, -1, 100.0, 1.0)
    f2 = V130Execution(spread_map, F2_STRICT_ASK).resolve(s, 0, 0, -1, 100.0, 1.0)
    assert f1.reason == "TIME" and f2.reason == "SL"

    # Long entry needs full ask trade-through in F1.
    s, spread = synthetic_symbol("US30.cash", [100.0], [99.3], spread=0.2)
    assert V130Execution(spread_map, D0_TOUCH).find_fill(s, 1, 99.4, 0, 0) == 0
    assert V130Execution(spread_map, F1_PER_BAR).find_fill(s, 1, 99.4, 0, 0) == -1

    # Prague day mapping covers ordinary time and both DST regimes.
    winter = int(datetime(2026, 1, 1, 22, 59, 59, tzinfo=timezone.utc).timestamp())
    summer = int(datetime(2026, 7, 1, 21, 59, 59, tzinfo=timezone.utc).timestamp())
    assert prague_day(winter) == "2026-01-01"
    assert prague_day(winter + 1) == "2026-01-02"
    assert prague_day(summer) == "2026-07-01"
    assert prague_day(summer + 1) == "2026-07-02"
    # In July the broker server rolls one hour before FTMO Prague.
    server_boundary = int(datetime(2026, 7, 1, 21, 0, 0, tzinfo=timezone.utc).timestamp())
    assert ea_server_day(server_boundary - 1) == "2026-07-01"
    assert ea_server_day(server_boundary) == "2026-07-02"
    assert prague_day(server_boundary) == "2026-07-01"

    def scheduled(name, cluster):
        n = START + 14
        ep = 1_700_000_000 + np.arange(n, dtype=np.int64) * BAR_SEC
        side = np.zeros(n, dtype=np.int8)
        wick = np.full(n, np.nan)
        side[START] = 1
        wick[START] = 0.30
        highs = np.full(n, 100.1)
        lows = np.full(n, 99.9)
        lows[START + 1] = 99.0
        highs[START + 2] = 102.1
        return SymData(
            name, ep, np.full(n, 100.0), highs, lows, np.full(n, 100.0),
            np.ones(n), side, wick, 0.0, cluster,
        )

    scheduled_symbols = (
        scheduled("US30.cash", 0),
        scheduled("US100.cash", 0),
        scheduled("JP225.cash", 1),
    )
    zero_spreads = {symbol.name: np.zeros(len(symbol.c)) for symbol in scheduled_symbols}
    symbol_meta = {
        name: {
            "trade_tick_size": 0.01,
            "trade_tick_value_loss": 0.01,
            "trade_tick_value_profit": 0.01,
            "volume_min": 0.01,
            "volume_step": 0.01,
            "volume_max": 1000.0,
        }
        for name in SYMBOLS
    }
    inputs = FrozenInputs(
        "synthetic", scheduled_symbols, zero_spreads, {"symbols": symbol_meta}, {}
    )
    coupled = run_coupled(inputs, F1_PER_BAR)
    calendar, metas = to_account_tape(inputs, coupled)
    assert len(coupled.trades) == 2  # shared US cluster seat + independent JP seat
    assert len(calendar.trades) == 2 and len(calendar.occupancies) == 2
    assert any(event.kind.value == "mark" for event in calendar.events)
    assert set(metas) == set(SYMBOLS)
    print("v130 coupled synthetic checks: 7 passed")


if __name__ == "__main__":
    self_test()
