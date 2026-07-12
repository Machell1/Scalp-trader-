"""Deterministic FTMO v1.30 account and risk-policy simulator.

This module is the pure account/Monte-Carlo layer registered in
``docs/V130_RISK_POLICY_SPEC_2026-07-11.md``.  It deliberately does not load
broker or research data.  A coupled execution runner must adapt its
chronological lifecycle rows to :class:`LifecycleEvent` first.

The adapter contract is intentionally explicit:

* one ENTRY, at most one PARTIAL, zero or more MARKs, and one FINAL per trade;
* every row carries a globally deterministic ``sequence`` for equal epochs;
* ``r_component`` is gross price R realised by that row (cost is separate);
* ``open_r`` is gross, cumulative unrealised price R on the remaining size;
* ``remaining_fraction`` is the execution model's nominal remaining fraction;
* ``price`` is the modeled executable/mark price and ``side`` is +1/-1.

Lot rounding is deferred until account replay because current-balance risk is
policy dependent.  Gross cash is calculated from event price distance and the
broker's profit/loss tick values; entry cost is charged once on original
realised stop risk.  This matters when ``trade_tick_value_profit`` and
``trade_tick_value_loss`` differ.

Moving blocks are sampled only from caller-supplied or independently derived
starts that are flat at both Prague-midnight boundaries.  Any orphan lifecycle,
ambiguous replay order, or capacity overlap at a stitch is a hard error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from statistics import NormalDist
from typing import Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np


PRAGUE = "Europe/Prague"
EA_SERVER_TIMEZONE = "Europe/Helsinki"
Z95_ONE_SIDED = NormalDist().inv_cdf(0.95)
MONEY_EPS = 1e-9
FRACTION_EPS = 1e-12


class InputInvariantError(ValueError):
    """Lifecycle rows or broker metadata violate the adapter contract."""


class BootstrapOverlapError(RuntimeError):
    """A sampled block stitch creates an orphan, overlap, or ambiguous order."""


class EventKind(str, Enum):
    ENTRY = "entry"
    MARK = "mark"
    PARTIAL = "partial"
    FINAL = "final"
    SWAP = "swap"


class EquityMode(str, Enum):
    MARKS = "marks"
    TWO_STOP = "two_stop"
    GAP_2X_STOP = "gap_2x_stop"


class PhaseStatus(str, Enum):
    PASS = "pass"
    FIRM_BREACH = "firm_breach"
    HARD_HALT = "hard_halt"
    TIMEOUT = "timeout"
    NOT_RUN = "not_run"


_KIND_ALIASES = {
    "entry": EventKind.ENTRY,
    "entry_fill": EventKind.ENTRY,
    "fill": EventKind.ENTRY,
    "mark": EventKind.MARK,
    "bar_mark": EventKind.MARK,
    "partial": EventKind.PARTIAL,
    "partial_fill": EventKind.PARTIAL,
    "final": EventKind.FINAL,
    "final_exit": EventKind.FINAL,
    "exit": EventKind.FINAL,
    "swap": EventKind.SWAP,
    "swap_charge": EventKind.SWAP,
}


def _kind(value: EventKind | str) -> EventKind:
    if isinstance(value, EventKind):
        return value
    try:
        return _KIND_ALIASES[str(value).strip().lower()]
    except KeyError as exc:
        raise InputInvariantError(f"unsupported lifecycle kind: {value!r}") from exc


@dataclass(frozen=True)
class LifecycleEvent:
    event_id: str
    trade_id: str
    symbol: str
    cluster: str
    epoch: int
    sequence: int
    kind: EventKind
    side: int
    price: float
    r_component: float
    open_r: float
    remaining_fraction: float
    signal_atr: float
    stop_distance: float
    entry_cost_r: float = 0.0
    mark_role: str = "neutral"
    cash_adjustment_r: float = 0.0
    classification_r_component: float | None = None

    @property
    def classifier_r(self) -> float:
        """Exit-deal R used by the deployed server-day loss classifier.

        Legacy callers omit this field; their gross partial/final R is the
        classifier component.  Cost-aware callers provide the exit-fraction
        slippage-adjusted component explicitly.  Timed swap is kept separate
        and attached to the final deal at account replay.
        """
        if self.classification_r_component is None:
            return float(self.r_component)
        return float(self.classification_r_component)

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "LifecycleEvent":
        """Create an event from a coupled-engine dictionary.

        A few descriptive aliases are accepted so the adapter can stay small;
        missing fields are never guessed.
        """

        def required(*names: str) -> object:
            for name in names:
                if name in row:
                    return row[name]
            raise InputInvariantError(f"missing lifecycle field: {'/'.join(names)}")

        return cls(
            event_id=str(required("event_id")),
            trade_id=str(required("trade_id")),
            symbol=str(required("symbol")),
            cluster=str(required("cluster")),
            epoch=int(required("epoch")),
            sequence=int(required("sequence")),
            kind=_kind(required("kind")),
            side=int(required("side")),
            price=float(required("price", "modeled_price")),
            r_component=float(required("r_component", "gross_r_component")),
            open_r=float(required("open_r", "cumulative_open_r")),
            remaining_fraction=float(required("remaining_fraction")),
            signal_atr=float(required("signal_atr")),
            stop_distance=float(required("stop_distance")),
            entry_cost_r=float(required("entry_cost_r")),
            mark_role=str(row.get("mark_role", "neutral")),
            cash_adjustment_r=float(row.get("cash_adjustment_r", 0.0)),
            classification_r_component=(
                None
                if row.get("classification_r_component") is None
                else float(row["classification_r_component"])
            ),
        )


@dataclass(frozen=True)
class SymbolMeta:
    symbol: str
    trade_tick_size: float
    trade_tick_value_loss: float
    trade_tick_value_profit: float
    volume_min: float
    volume_step: float
    volume_max: float

    def __post_init__(self) -> None:
        values = (
            self.trade_tick_size,
            self.trade_tick_value_loss,
            self.trade_tick_value_profit,
            self.volume_min,
            self.volume_step,
            self.volume_max,
        )
        if not self.symbol or not all(math.isfinite(x) and x > 0.0 for x in values):
            raise InputInvariantError(f"invalid broker metadata for {self.symbol!r}")
        if self.volume_max + FRACTION_EPS < self.volume_min:
            raise InputInvariantError(f"volume_max < volume_min for {self.symbol}")


@dataclass(frozen=True)
class TemplateEvent:
    event: LifecycleEvent
    day_offset: int
    second_of_day: int
    ea_day_offset: int


@dataclass(frozen=True)
class OccupancyInterval:
    occupancy_id: str
    trade_id: str | None
    symbol: str
    cluster: str
    start_epoch: int
    end_epoch: int

    def __post_init__(self) -> None:
        if not self.occupancy_id or not self.symbol or not self.cluster:
            raise InputInvariantError("occupancy ids/symbol/cluster must be non-empty")
        if int(self.end_epoch) < int(self.start_epoch):
            raise InputInvariantError(f"{self.occupancy_id}: occupancy ends before it starts")


@dataclass(frozen=True)
class TradeTemplate:
    trade_id: str
    symbol: str
    cluster: str
    owner_day: date
    entry_epoch: int
    final_epoch: int
    events: tuple[TemplateEvent, ...]


@dataclass(frozen=True)
class DayTemplate:
    source_day: date
    trades: tuple[TradeTemplate, ...] = ()


def _as_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _local_parts(epoch: int, zone: ZoneInfo) -> tuple[date, int]:
    dt = datetime.fromtimestamp(int(epoch), timezone.utc).astimezone(zone)
    local_day = dt.date()
    # Epoch distance from local midnight preserves the repeated autumn hour
    # instead of collapsing both 02:xx folds onto the same wall-clock second.
    seconds = int(epoch) - _local_midnight_epoch(local_day, zone)
    return local_day, seconds


def _local_midnight_epoch(day: date, zone: ZoneInfo) -> int:
    return int(datetime.combine(day, time.min, zone).timestamp())


def _validate_lifecycle_events(
    events: Iterable[LifecycleEvent | Mapping[str, object]],
) -> tuple[LifecycleEvent, ...]:
    normalized = tuple(
        event if isinstance(event, LifecycleEvent) else LifecycleEvent.from_mapping(event)
        for event in events
    )
    if not normalized:
        return ()

    event_ids: set[str] = set()
    order_keys: set[tuple[int, int]] = set()
    by_trade: dict[str, list[LifecycleEvent]] = {}
    for event in normalized:
        if not event.event_id or not event.trade_id or not event.symbol or not event.cluster:
            raise InputInvariantError("event/trade/symbol/cluster ids must be non-empty")
        if event.event_id in event_ids:
            raise InputInvariantError(f"duplicate event_id: {event.event_id}")
        event_ids.add(event.event_id)
        key = (int(event.epoch), int(event.sequence))
        if key in order_keys:
            raise InputInvariantError(
                f"ambiguous source ordering at epoch/sequence {key}; sequence must be global"
            )
        order_keys.add(key)
        if event.side not in (-1, 1):
            raise InputInvariantError(f"{event.event_id}: side must be +1 or -1")
        numeric = (
            event.price,
            event.r_component,
            event.open_r,
            event.remaining_fraction,
            event.signal_atr,
            event.stop_distance,
            event.entry_cost_r,
            event.cash_adjustment_r,
        )
        if not all(math.isfinite(x) for x in numeric):
            raise InputInvariantError(f"{event.event_id}: non-finite numeric field")
        if event.price <= 0.0 or event.signal_atr <= 0.0 or event.stop_distance <= 0.0:
            raise InputInvariantError(f"{event.event_id}: price/ATR/stop must be positive")
        if not -FRACTION_EPS <= event.remaining_fraction <= 1.0 + FRACTION_EPS:
            raise InputInvariantError(f"{event.event_id}: invalid remaining fraction")
        if event.entry_cost_r < 0.0:
            raise InputInvariantError(f"{event.event_id}: entry cost cannot be negative")
        if (
            event.classification_r_component is not None
            and not math.isfinite(event.classification_r_component)
        ):
            raise InputInvariantError(f"{event.event_id}: non-finite classifier R")
        if event.mark_role not in {"neutral", "favorable", "adverse"}:
            raise InputInvariantError(f"{event.event_id}: invalid mark role")
        by_trade.setdefault(event.trade_id, []).append(event)

    for trade_id, rows in by_trade.items():
        rows.sort(key=lambda x: (x.epoch, x.sequence))
        entries = [x for x in rows if _kind(x.kind) is EventKind.ENTRY]
        finals = [x for x in rows if _kind(x.kind) is EventKind.FINAL]
        partials = [x for x in rows if _kind(x.kind) is EventKind.PARTIAL]
        if len(entries) != 1 or len(finals) != 1 or len(partials) > 1:
            raise InputInvariantError(
                f"{trade_id}: require one entry, one final, and at most one partial"
            )
        if rows[0] is not entries[0] or rows[-1] is not finals[0]:
            raise InputInvariantError(f"{trade_id}: entry must be first and final last")
        identity = {(x.symbol, x.cluster, x.side) for x in rows}
        if len(identity) != 1:
            raise InputInvariantError(f"{trade_id}: symbol/cluster/side changed in lifecycle")
        geometry = {(x.signal_atr, x.stop_distance) for x in rows}
        if len(geometry) != 1:
            raise InputInvariantError(f"{trade_id}: frozen ATR/stop changed in lifecycle")

        nominal = 1.0
        entry_price = entries[0].price
        for row in rows:
            kind = _kind(row.kind)
            nominal_before = nominal
            price_r = (row.price - entry_price) * row.side / row.stop_distance
            if kind is EventKind.ENTRY:
                if abs(row.remaining_fraction - 1.0) > FRACTION_EPS:
                    raise InputInvariantError(f"{trade_id}: entry remaining fraction != 1")
                if abs(row.r_component) > FRACTION_EPS or abs(row.open_r) > FRACTION_EPS:
                    raise InputInvariantError(f"{trade_id}: entry gross/open R must be zero")
                if abs(row.cash_adjustment_r) > FRACTION_EPS:
                    raise InputInvariantError(f"{trade_id}: entry cash adjustment must be zero")
            elif kind is EventKind.MARK:
                if abs(row.r_component) > FRACTION_EPS:
                    raise InputInvariantError(f"{trade_id}: mark cannot realise R")
                if abs(row.remaining_fraction - nominal) > FRACTION_EPS:
                    raise InputInvariantError(f"{trade_id}: mark changed nominal size")
                if abs(row.open_r - price_r * nominal) > 1e-9:
                    raise InputInvariantError(f"{trade_id}: open_r inconsistent with mark price")
                if abs(row.cash_adjustment_r) > FRACTION_EPS:
                    raise InputInvariantError(f"{trade_id}: mark cash adjustment must be zero")
            elif kind is EventKind.PARTIAL:
                if not 0.0 < row.remaining_fraction < nominal - FRACTION_EPS:
                    raise InputInvariantError(f"{trade_id}: partial did not reduce nominal size")
                nominal_close = nominal - row.remaining_fraction
                if abs(row.r_component - price_r * nominal_close) > 1e-9:
                    raise InputInvariantError(f"{trade_id}: partial R inconsistent with price/size")
                if abs(row.open_r - price_r * row.remaining_fraction) > 1e-9:
                    raise InputInvariantError(f"{trade_id}: partial open_r inconsistent with price/size")
                nominal = row.remaining_fraction
            elif kind is EventKind.FINAL:
                if abs(row.remaining_fraction) > FRACTION_EPS or abs(row.open_r) > FRACTION_EPS:
                    raise InputInvariantError(f"{trade_id}: final must be flat with open_r=0")
                if abs(row.r_component - price_r * nominal_before) > 1e-9:
                    raise InputInvariantError(f"{trade_id}: final R inconsistent with price/size")
                nominal = 0.0
            elif kind is EventKind.SWAP:
                if abs(row.r_component) > FRACTION_EPS or abs(row.open_r) > 1e-9:
                    raise InputInvariantError(f"{trade_id}: swap must not realise price/open R")
                if abs(row.remaining_fraction - nominal) > FRACTION_EPS:
                    raise InputInvariantError(f"{trade_id}: swap changed nominal size")
                if abs(row.entry_cost_r) > FRACTION_EPS:
                    raise InputInvariantError(f"{trade_id}: swap entry cost must be zero")
            if kind is not EventKind.ENTRY and row.entry_cost_r > FRACTION_EPS:
                raise InputInvariantError(f"{trade_id}: cost may only appear on entry")

    return tuple(sorted(normalized, key=lambda x: (x.epoch, x.sequence)))


@dataclass(frozen=True)
class CalendarTape:
    """Complete lifecycle templates on an explicit Prague calendar frame."""

    first_day: date
    last_day: date
    timezone_name: str
    events: tuple[LifecycleEvent, ...]
    occupancies: tuple[OccupancyInterval, ...]
    days: tuple[DayTemplate, ...]
    trades: tuple[TradeTemplate, ...]

    @classmethod
    def from_events(
        cls,
        events: Iterable[LifecycleEvent | Mapping[str, object]],
        *,
        first_day: date | str,
        last_day: date | str,
        timezone_name: str = PRAGUE,
        occupancy_intervals: Iterable[OccupancyInterval] = (),
    ) -> "CalendarTape":
        first = _as_date(first_day)
        last = _as_date(last_day)
        if last < first:
            raise InputInvariantError("calendar frame ends before it starts")
        zone = ZoneInfo(timezone_name)
        ea_zone = ZoneInfo(EA_SERVER_TIMEZONE)
        rows = _validate_lifecycle_events(events)
        occupancies = tuple(occupancy_intervals)
        occupancy_ids = [item.occupancy_id for item in occupancies]
        if len(set(occupancy_ids)) != len(occupancy_ids):
            raise InputInvariantError("duplicate occupancy interval id")
        grouped: dict[str, list[LifecycleEvent]] = {}
        for row in rows:
            grouped.setdefault(row.trade_id, []).append(row)

        templates: list[TradeTemplate] = []
        by_owner: dict[date, list[TradeTemplate]] = {}
        for trade_id, trade_rows in grouped.items():
            trade_rows.sort(key=lambda x: (x.epoch, x.sequence))
            owner, _ = _local_parts(trade_rows[0].epoch, zone)
            if owner < first or owner > last:
                raise InputInvariantError(f"{trade_id}: entry owner day outside calendar frame")
            t_events: list[TemplateEvent] = []
            for row in trade_rows:
                local_day, seconds = _local_parts(row.epoch, zone)
                offset = (local_day - owner).days
                if offset < 0:
                    raise InputInvariantError(f"{trade_id}: event precedes entry owner day")
                ea_day, _ = _local_parts(row.epoch, ea_zone)
                ea_offset = (ea_day - owner).days
                t_events.append(TemplateEvent(row, offset, seconds, ea_offset))
            template = TradeTemplate(
                trade_id=trade_id,
                symbol=trade_rows[0].symbol,
                cluster=trade_rows[0].cluster,
                owner_day=owner,
                entry_epoch=trade_rows[0].epoch,
                final_epoch=trade_rows[-1].epoch,
                events=tuple(t_events),
            )
            templates.append(template)
            by_owner.setdefault(owner, []).append(template)

        all_days: list[DayTemplate] = []
        day = first
        while day <= last:
            owned = tuple(sorted(by_owner.get(day, ()), key=lambda x: (x.entry_epoch, x.trade_id)))
            all_days.append(DayTemplate(day, owned))
            day += timedelta(days=1)
        return cls(
            first_day=first,
            last_day=last,
            timezone_name=timezone_name,
            events=rows,
            occupancies=occupancies,
            days=tuple(all_days),
            trades=tuple(sorted(templates, key=lambda x: (x.entry_epoch, x.trade_id))),
        )

    @property
    def n_days(self) -> int:
        return len(self.days)

    def _flat_at_boundary(self, boundary: date) -> bool:
        zone = ZoneInfo(self.timezone_name)
        epoch = _local_midnight_epoch(boundary, zone)
        if self.occupancies:
            return not any(
                int(item.start_epoch) < epoch < int(item.end_epoch)
                for item in self.occupancies
            )
        return not any(t.entry_epoch < epoch < t.final_epoch for t in self.trades)

    def flat_boundary_at_index(self, boundary_index: int) -> bool:
        """Whether the source account is flat at a calendar-day boundary.

        Boundary 0 is the start of ``first_day`` and boundary ``n_days`` is the
        midnight immediately following ``last_day``.
        """
        if not 0 <= boundary_index <= self.n_days:
            raise InputInvariantError("calendar boundary index out of range")
        boundary = self.first_day + timedelta(days=boundary_index)
        return self._flat_at_boundary(boundary)

    def eligible_flat_block_starts(self, block_length: int) -> tuple[int, ...]:
        if block_length <= 0 or block_length > self.n_days:
            raise InputInvariantError("invalid block length")
        eligible: list[int] = []
        for start in range(0, self.n_days - block_length + 1):
            if self.flat_boundary_at_index(start) and self.flat_boundary_at_index(
                start + block_length
            ):
                eligible.append(start)
        return tuple(eligible)

    def filter_symbols(self, symbols: Iterable[str]) -> "CalendarTape":
        keep = set(symbols)
        return CalendarTape.from_events(
            (event for event in self.events if event.symbol in keep),
            first_day=self.first_day,
            last_day=self.last_day,
            timezone_name=self.timezone_name,
            occupancy_intervals=(x for x in self.occupancies if x.symbol in keep),
        )

    def without_owner_quarter(self, year: int, quarter: int) -> "CalendarTape":
        if quarter not in (1, 2, 3, 4):
            raise InputInvariantError("quarter must be 1..4")
        zone = ZoneInfo(self.timezone_name)
        removed: set[str] = set()
        for trade in self.trades:
            owner, _ = _local_parts(trade.entry_epoch, zone)
            q = (owner.month - 1) // 3 + 1
            if owner.year == year and q == quarter:
                removed.add(trade.trade_id)
        return CalendarTape.from_events(
            (event for event in self.events if event.trade_id not in removed),
            first_day=self.first_day,
            last_day=self.last_day,
            timezone_name=self.timezone_name,
            occupancy_intervals=(
                interval
                for interval in self.occupancies
                if interval.trade_id not in removed
                and not (
                    datetime.fromtimestamp(interval.start_epoch, timezone.utc)
                    .astimezone(zone)
                    .year
                    == year
                    and (datetime.fromtimestamp(interval.start_epoch, timezone.utc)
                         .astimezone(zone).month - 1) // 3 + 1
                    == quarter
                )
            ),
        )


@dataclass(frozen=True)
class BootstrapSpec:
    seed: int = 13020260711
    block_length: int = 20
    mode: str = "moving_block"
    eligible_block_starts: tuple[int, ...] | None = None

    def source_indices(self, tape: CalendarTape, path_id: int, total_days: int) -> np.ndarray:
        if path_id < 0 or total_days <= 0:
            raise InputInvariantError("path_id must be nonnegative and total_days positive")
        rng = np.random.default_rng(np.random.SeedSequence([int(self.seed), int(path_id)]))
        if self.mode == "moving_block":
            length = self.block_length
        elif self.mode == "iid_calendar_day":
            length = 1
        else:
            raise InputInvariantError(f"unsupported bootstrap mode: {self.mode}")

        derived = tape.eligible_flat_block_starts(length)
        eligible = derived if self.eligible_block_starts is None else self.eligible_block_starts
        if not eligible:
            raise InputInvariantError(f"no flat {length}-day bootstrap blocks")
        if any(start not in derived for start in eligible):
            raise InputInvariantError("supplied block start is not flat at both boundaries")
        blocks = math.ceil(total_days / length)
        choices = rng.integers(0, len(eligible), size=blocks)
        out = np.empty(blocks * length, dtype=np.int32)
        cursor = 0
        for choice in choices:
            start = int(eligible[int(choice)])
            out[cursor : cursor + length] = np.arange(start, start + length, dtype=np.int32)
            cursor += length
        return out[:total_days]


def _volume_digits(step: float) -> int:
    text = f"{step:.12f}".rstrip("0")
    return len(text.partition(".")[2])


def floor_volume(volume: float, step: float) -> float:
    """EA partial-close floor (the partial helper intentionally adds epsilon)."""
    if volume <= 0.0 or step <= 0.0:
        return 0.0
    units = math.floor((volume + 1e-12) / step)
    return round(units * step, _volume_digits(step))


def floor_risk_volume(volume: float, step: float) -> float:
    """Exact CalculateLotSize floor: raw MathFloor with no partial epsilon."""
    if volume <= 0.0 or step <= 0.0:
        return 0.0
    return math.floor(volume / step) * step


@dataclass(frozen=True)
class LotDecision:
    requested_risk_cash: float
    loss_per_lot: float
    raw_volume: float
    volume: float
    actual_risk_cash: float
    min_substitution: bool
    rejection: str = ""


def size_for_risk(
    balance: float,
    risk_fraction: float,
    stop_distance: float,
    meta: SymbolMeta,
    *,
    min_budget_multiple: float = 1.5,
) -> LotDecision:
    if balance <= 0.0 or not 0.0 < risk_fraction < 1.0 or stop_distance <= 0.0:
        raise InputInvariantError("invalid balance/risk/stop for lot sizing")
    requested = balance * risk_fraction
    loss_per_lot = stop_distance / meta.trade_tick_size * meta.trade_tick_value_loss
    raw = requested / loss_per_lot
    volume = floor_risk_volume(raw, meta.volume_step)
    substituted = False
    if volume + FRACTION_EPS < meta.volume_min:
        min_risk = loss_per_lot * meta.volume_min
        if min_risk > requested * min_budget_multiple + MONEY_EPS:
            return LotDecision(requested, loss_per_lot, raw, 0.0, 0.0, False, "min_lot_overrisk")
        volume = meta.volume_min
        substituted = True
    if volume > meta.volume_max:
        volume = meta.volume_max
    if volume + FRACTION_EPS < meta.volume_min:
        return LotDecision(requested, loss_per_lot, raw, 0.0, 0.0, False, "invalid_volume")
    return LotDecision(
        requested,
        loss_per_lot,
        raw,
        volume,
        loss_per_lot * volume,
        substituted,
        "",
    )


def partial_close_volume(initial_volume: float, requested_fraction: float, meta: SymbolMeta) -> float:
    if initial_volume <= 0.0 or not 0.0 < requested_fraction < 1.0:
        return 0.0
    raw = initial_volume * requested_fraction
    if raw + FRACTION_EPS < meta.volume_min:
        return 0.0
    target = floor_volume(raw, meta.volume_step)
    if target + FRACTION_EPS < meta.volume_min:
        return 0.0
    if initial_volume - target + FRACTION_EPS < meta.volume_min:
        return 0.0
    return target


def cash_from_price(
    entry_price: float,
    event_price: float,
    side: int,
    volume: float,
    meta: SymbolMeta,
) -> float:
    move = (event_price - entry_price) * side
    if abs(move) <= MONEY_EPS or volume <= 0.0:
        return 0.0
    tick_value = meta.trade_tick_value_profit if move > 0.0 else meta.trade_tick_value_loss
    return math.copysign(abs(move) / meta.trade_tick_size * tick_value * volume, move)


@dataclass(frozen=True)
class ReplayEvent:
    replay_day: int
    ea_day: int
    second_of_day: int
    source_index: int
    owner_replay_day: int
    replay_trade_id: str
    replay_event_id: str
    event: LifecycleEvent

    @property
    def sort_key(self) -> tuple[int, int, str]:
        return (self.second_of_day, self.event.sequence, self.replay_event_id)


class ReplayCursor:
    def __init__(self, tape: CalendarTape) -> None:
        self.tape = tape
        self.pending: dict[int, list[ReplayEvent]] = {}

    def events_for_day(self, replay_day: int, source_index: int) -> list[ReplayEvent]:
        if not 0 <= source_index < self.tape.n_days:
            raise InputInvariantError(f"source day index out of range: {source_index}")
        template = self.tape.days[source_index]
        for trade in template.trades:
            replay_trade_id = f"d{replay_day}:s{source_index}:{trade.trade_id}"
            for item in trade.events:
                target_day = replay_day + item.day_offset
                replay_event_id = f"{replay_trade_id}:{item.event.event_id}"
                self.pending.setdefault(target_day, []).append(
                    ReplayEvent(
                        target_day,
                        replay_day + item.ea_day_offset,
                        item.second_of_day,
                        source_index,
                        replay_day,
                        replay_trade_id,
                        replay_event_id,
                        item.event,
                    )
                )
        rows = self.pending.pop(replay_day, [])
        seen_order: set[tuple[int, int]] = set()
        for row in rows:
            key = (row.second_of_day, row.event.sequence)
            if key in seen_order:
                raise BootstrapOverlapError(
                    f"ambiguous stitched ordering on replay day {replay_day}: {key}"
                )
            seen_order.add(key)
        rows.sort(key=lambda row: row.sort_key)
        return rows

    def discard_pending(self) -> int:
        count = sum(len(rows) for rows in self.pending.values())
        self.pending.clear()
        return count


class RawCapacityTracker:
    """Checks pre-account coupled lifecycle invariants across block stitches."""

    def __init__(self, global_cap: int, cluster_cap: int) -> None:
        self.global_cap = global_cap
        self.cluster_cap = cluster_cap
        self.active: dict[str, tuple[str, str]] = {}

    def process(self, row: ReplayEvent) -> None:
        event = row.event
        kind = _kind(event.kind)
        if kind is EventKind.ENTRY:
            if row.replay_trade_id in self.active:
                raise BootstrapOverlapError(f"duplicate replay entry {row.replay_trade_id}")
            if any(symbol == event.symbol for symbol, _ in self.active.values()):
                raise BootstrapOverlapError(
                    f"symbol overlap at block stitch: {event.symbol} day={row.replay_day}"
                )
            if sum(cluster == event.cluster for _, cluster in self.active.values()) >= self.cluster_cap:
                raise BootstrapOverlapError(
                    f"cluster overlap at block stitch: {event.cluster} day={row.replay_day}"
                )
            if len(self.active) >= self.global_cap:
                raise BootstrapOverlapError(f"global overlap at block stitch day={row.replay_day}")
            self.active[row.replay_trade_id] = (event.symbol, event.cluster)
        else:
            if row.replay_trade_id not in self.active:
                raise BootstrapOverlapError(
                    f"orphan {kind.value} for {row.replay_trade_id} day={row.replay_day}"
                )
            if kind is EventKind.FINAL:
                self.active.pop(row.replay_trade_id)

    def reset_phase_boundary(self) -> int:
        count = len(self.active)
        self.active.clear()
        return count


@dataclass(frozen=True)
class RiskPolicy:
    name: str
    phase1_risk: float
    phase2_risk: float
    # Optional immutable symbol overrides.  An empty tuple preserves the
    # historical scalar policy byte-for-byte.
    symbol_risks: tuple[tuple[str, float, float], ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not 0.0 < self.phase1_risk < 1.0 or not 0.0 < self.phase2_risk < 1.0:
            raise InputInvariantError("invalid risk policy")
        names: set[str] = set()
        for symbol, phase1, phase2 in self.symbol_risks:
            if not symbol or symbol in names or not 0.0 < phase1 < 1.0 or not 0.0 < phase2 < 1.0:
                raise InputInvariantError("invalid symbol risk policy")
            names.add(symbol)

    def for_phase(self, phase: int) -> float:
        if phase == 1:
            return self.phase1_risk
        if phase == 2:
            return self.phase2_risk
        raise InputInvariantError(f"invalid FTMO phase: {phase}")

    def for_phase_symbol(self, phase: int, symbol: str) -> float:
        if phase not in (1, 2):
            raise InputInvariantError(f"invalid FTMO phase: {phase}")
        for name, phase1, phase2 in self.symbol_risks:
            if name == symbol:
                return phase1 if phase == 1 else phase2
        return self.for_phase(phase)


@dataclass(frozen=True)
class SimulationConfig:
    initial_balance: float = 100_000.0
    phase1_target_pct: float = 10.0
    phase2_target_pct: float = 5.0
    firm_daily_loss_pct: float = 5.0
    firm_static_loss_pct: float = 10.0
    minimum_trading_days: int = 4
    max_calendar_days_per_phase: int = 3650
    ea_daily_halt_pct: float = 4.0
    ea_peak_drawdown_pct: float = 8.0
    ea_static_halt_pct: float = 9.0
    ea_fills_per_day: int = 8
    ea_consecutive_losses: int = 4
    global_cap: int = 2
    cluster_cap: int = 1
    min_lot_budget_multiple: float = 1.5
    cost_multiplier: float = 1.0
    equity_mode: EquityMode = EquityMode.MARKS

    def __post_init__(self) -> None:
        positive = (
            self.initial_balance,
            self.phase1_target_pct,
            self.phase2_target_pct,
            self.firm_daily_loss_pct,
            self.firm_static_loss_pct,
            self.ea_daily_halt_pct,
            self.ea_peak_drawdown_pct,
            self.ea_static_halt_pct,
            self.min_lot_budget_multiple,
            self.cost_multiplier,
        )
        if not all(math.isfinite(x) and x > 0.0 for x in positive):
            raise InputInvariantError("simulation percentages/amounts must be positive")
        integers = (
            self.minimum_trading_days,
            self.max_calendar_days_per_phase,
            self.ea_fills_per_day,
            self.ea_consecutive_losses,
            self.global_cap,
            self.cluster_cap,
        )
        if any(x <= 0 for x in integers):
            raise InputInvariantError("simulation count limits must be positive")


@dataclass
class AccountCounters:
    entries: int = 0
    completed: int = 0
    partial_executed: int = 0
    partial_skipped_rounding: int = 0
    min_lot_rejections: int = 0
    min_lot_substitutions: int = 0
    skipped_daily_halt: int = 0
    skipped_fill_cap: int = 0
    skipped_consecutive: int = 0
    ignored_lifecycle: int = 0
    daily_halts: int = 0
    sign_mismatches: int = 0
    max_active: int = 0


@dataclass
class TradeRuntime:
    replay_trade_id: str
    symbol: str
    cluster: str
    side: int
    entry_price: float
    stop_distance: float
    volume: float
    current_volume: float
    actual_risk_cash: float
    nominal_remaining: float
    mark_price: float
    cumulative_net_cash: float
    theoretical_net_r: float
    entry_cost_r: float = 0.0
    classifier_by_ea_day: dict[int, float] = field(default_factory=dict)
    accrued_swap_cash: float = 0.0


class PhaseAccount:
    def __init__(
        self,
        phase: int,
        risk_fraction: float,
        metas: Mapping[str, SymbolMeta],
        config: SimulationConfig,
        risk_policy: RiskPolicy | None = None,
    ) -> None:
        self.phase = phase
        self.risk_fraction = risk_fraction
        self.metas = metas
        self.config = config
        self.risk_policy = risk_policy
        self.balance = config.initial_balance
        self.peak_equity = config.initial_balance
        self.min_equity = config.initial_balance
        self.max_equity = config.initial_balance
        self.positions: dict[str, TradeRuntime] = {}
        self.trading_days: set[int] = set()
        self.phase_days = 0
        self.current_replay_day: int | None = None
        self.current_ea_day: int | None = None
        self.day_start_balance = config.initial_balance
        self.ea_day_start_balance = config.initial_balance
        self.fills_today = 0
        self.consecutive_losses_today = 0
        self.daily_halted = False
        self.last_event_role = "neutral"
        self.counters = AccountCounters()

    @property
    def target_pct(self) -> float:
        return self.config.phase1_target_pct if self.phase == 1 else self.config.phase2_target_pct

    def begin_day(self, replay_day: int) -> None:
        if self.current_replay_day is not None:
            raise InputInvariantError("begin_day called before end_day")
        self.current_replay_day = replay_day
        self.phase_days += 1
        self.day_start_balance = self.balance

    def ensure_ea_day(self, ea_day: int) -> None:
        """Reset EA-only rails on the broker server day, not the FTMO day."""
        if self.current_ea_day == int(ea_day):
            return
        if self.current_ea_day is not None and int(ea_day) < self.current_ea_day:
            raise BootstrapOverlapError("EA server-day token moved backwards")
        self.current_ea_day = int(ea_day)
        self.ea_day_start_balance = self.balance
        self.fills_today = 0
        self.consecutive_losses_today = 0
        self.daily_halted = False

    def end_day(self) -> None:
        self.current_replay_day = None

    def _meta(self, symbol: str) -> SymbolMeta:
        try:
            meta = self.metas[symbol]
        except KeyError as exc:
            raise InputInvariantError(f"missing SymbolMeta for {symbol}") from exc
        if meta.symbol != symbol:
            raise InputInvariantError(f"SymbolMeta key/name mismatch for {symbol}")
        return meta

    def _position_open_cash(self, runtime: TradeRuntime) -> float:
        meta = self._meta(runtime.symbol)
        if self.config.equity_mode is EquityMode.MARKS:
            return cash_from_price(
                runtime.entry_price,
                runtime.mark_price,
                runtime.side,
                runtime.current_volume,
                meta,
            )
        multiple = 1.0 if self.config.equity_mode is EquityMode.TWO_STOP else 2.0
        envelope = -(
            runtime.stop_distance
            / meta.trade_tick_size
            * meta.trade_tick_value_loss
            * runtime.current_volume
            * multiple
        )
        marked = cash_from_price(
            runtime.entry_price,
            runtime.mark_price,
            runtime.side,
            runtime.current_volume,
            meta,
        )
        return min(marked, envelope)

    def _position_mark_cash(self, runtime: TradeRuntime) -> float:
        meta = self._meta(runtime.symbol)
        return cash_from_price(
            runtime.entry_price,
            runtime.mark_price,
            runtime.side,
            runtime.current_volume,
            meta,
        )

    def marked_equity(self) -> float:
        return self.balance + sum(self._position_mark_cash(x) for x in self.positions.values())

    def equity(self) -> float:
        return self.balance + sum(self._position_open_cash(x) for x in self.positions.values())

    def _capacity_assert(self, event: LifecycleEvent) -> None:
        if any(x.symbol == event.symbol for x in self.positions.values()):
            raise BootstrapOverlapError(f"account symbol overlap: {event.symbol}")
        if sum(x.cluster == event.cluster for x in self.positions.values()) >= self.config.cluster_cap:
            raise BootstrapOverlapError(f"account cluster overlap: {event.cluster}")
        if len(self.positions) >= self.config.global_cap:
            raise BootstrapOverlapError("account global capacity overlap")

    def process(self, row: ReplayEvent) -> None:
        if self.current_replay_day is None:
            raise InputInvariantError("lifecycle event processed outside a calendar day")
        event = row.event
        kind = _kind(event.kind)
        self.last_event_role = event.mark_role
        runtime = self.positions.get(row.replay_trade_id)

        if kind is EventKind.ENTRY:
            if runtime is not None:
                raise BootstrapOverlapError(f"duplicate account entry {row.replay_trade_id}")
            if self.daily_halted:
                self.counters.skipped_daily_halt += 1
                return
            if self.fills_today >= self.config.ea_fills_per_day:
                self.counters.skipped_fill_cap += 1
                return
            if self.consecutive_losses_today >= self.config.ea_consecutive_losses:
                self.counters.skipped_consecutive += 1
                return
            self._capacity_assert(event)
            meta = self._meta(event.symbol)
            risk_fraction = (
                self.risk_policy.for_phase_symbol(self.phase, event.symbol)
                if self.risk_policy is not None
                else self.risk_fraction
            )
            lot = size_for_risk(
                self.balance,
                risk_fraction,
                event.stop_distance,
                meta,
                min_budget_multiple=self.config.min_lot_budget_multiple,
            )
            if lot.rejection:
                self.counters.min_lot_rejections += 1
                return
            if lot.min_substitution:
                self.counters.min_lot_substitutions += 1
            entry_cost = event.entry_cost_r * self.config.cost_multiplier * lot.actual_risk_cash
            self.balance -= entry_cost
            runtime = TradeRuntime(
                replay_trade_id=row.replay_trade_id,
                symbol=event.symbol,
                cluster=event.cluster,
                side=event.side,
                entry_price=event.price,
                stop_distance=event.stop_distance,
                volume=lot.volume,
                current_volume=lot.volume,
                actual_risk_cash=lot.actual_risk_cash,
                nominal_remaining=1.0,
                mark_price=event.price,
                cumulative_net_cash=-entry_cost,
                theoretical_net_r=-event.entry_cost_r * self.config.cost_multiplier,
                entry_cost_r=event.entry_cost_r * self.config.cost_multiplier,
            )
            self.positions[row.replay_trade_id] = runtime
            self.fills_today += 1
            self.trading_days.add(self.phase_days)
            self.counters.entries += 1
            self.counters.max_active = max(self.counters.max_active, len(self.positions))
            return

        if runtime is None:
            self.counters.ignored_lifecycle += 1
            return
        meta = self._meta(runtime.symbol)
        if kind is EventKind.MARK:
            runtime.mark_price = event.price
            return

        if kind is EventKind.SWAP:
            cash = event.cash_adjustment_r * runtime.actual_risk_cash
            self.balance += cash
            runtime.cumulative_net_cash += cash
            runtime.theoretical_net_r += event.cash_adjustment_r
            runtime.accrued_swap_cash += cash
            return

        if kind is EventKind.PARTIAL:
            runtime.theoretical_net_r += event.r_component
            nominal_close = runtime.nominal_remaining - event.remaining_fraction
            if nominal_close <= FRACTION_EPS:
                raise InputInvariantError(f"{row.replay_trade_id}: non-reducing partial")
            close_volume = partial_close_volume(runtime.volume, nominal_close, meta)
            if close_volume <= 0.0:
                self.counters.partial_skipped_rounding += 1
            else:
                cash = cash_from_price(
                    runtime.entry_price,
                    event.price,
                    runtime.side,
                    close_volume,
                    meta,
                )
                self.balance += cash
                runtime.cumulative_net_cash += cash
                classifier_cash = cash - runtime.entry_cost_r * (
                    close_volume / runtime.volume
                )
                runtime.classifier_by_ea_day[row.ea_day] = (
                    runtime.classifier_by_ea_day.get(row.ea_day, 0.0) + classifier_cash
                )
                runtime.current_volume -= close_volume
                self.counters.partial_executed += 1
            runtime.nominal_remaining = event.remaining_fraction
            runtime.mark_price = event.price
            return

        if kind is EventKind.FINAL:
            runtime.theoretical_net_r += event.r_component
            cash = cash_from_price(
                runtime.entry_price,
                event.price,
                runtime.side,
                runtime.current_volume,
                meta,
            )
            self.balance += cash
            runtime.cumulative_net_cash += cash
            net = runtime.cumulative_net_cash
            actual_sign = -1 if net < -MONEY_EPS else 1 if net > MONEY_EPS else 0
            theoretical_sign = (
                -1
                if runtime.theoretical_net_r < -FRACTION_EPS
                else 1
                if runtime.theoretical_net_r > FRACTION_EPS
                else 0
            )
            if actual_sign != theoretical_sign:
                self.counters.sign_mismatches += 1
            final_classifier_cash = cash - runtime.entry_cost_r * (
                runtime.current_volume / runtime.volume
            ) + runtime.accrued_swap_cash
            classifier_cash = (
                runtime.classifier_by_ea_day.get(row.ea_day, 0.0)
                + final_classifier_cash
            )
            self.positions.pop(row.replay_trade_id)
            self.counters.completed += 1
            if classifier_cash < -MONEY_EPS:
                self.consecutive_losses_today += 1
            elif classifier_cash > MONEY_EPS:
                self.consecutive_losses_today = 0
            # Exact zero leaves the current streak unchanged, matching the
            # EA's three-way loss/win/flat ledger rule.
            return
        raise InputInvariantError(f"unsupported lifecycle kind: {kind}")

    def check_rails(self) -> tuple[PhaseStatus, str] | None:
        marked_equity = self.marked_equity()
        equity = marked_equity if self.last_event_role == "favorable" else self.equity()
        # Favorable bar marks update the live EA peak; the separate conservative
        # envelope is then used for floor and drawdown tests.
        self.peak_equity = max(self.peak_equity, marked_equity)
        self.min_equity = min(self.min_equity, equity)
        self.max_equity = max(self.max_equity, marked_equity)

        # Equality is conservatively a failure for both FTMO limits.
        daily_floor = self.day_start_balance - self.config.initial_balance * (
            self.config.firm_daily_loss_pct / 100.0
        )
        static_floor = self.config.initial_balance * (
            1.0 - self.config.firm_static_loss_pct / 100.0
        )
        if equity <= daily_floor + MONEY_EPS:
            return PhaseStatus.FIRM_BREACH, "FTMO_DAILY_LOSS"
        if equity <= static_floor + MONEY_EPS:
            return PhaseStatus.FIRM_BREACH, "FTMO_STATIC_LOSS"

        peak_floor = self.peak_equity * (1.0 - self.config.ea_peak_drawdown_pct / 100.0)
        ea_static = self.config.initial_balance * (1.0 - self.config.ea_static_halt_pct / 100.0)
        if equity <= peak_floor + MONEY_EPS:
            return PhaseStatus.HARD_HALT, "EA_PEAK_DRAWDOWN"
        if equity <= ea_static + MONEY_EPS:
            return PhaseStatus.HARD_HALT, "EA_STATIC_FLOOR"

        ea_daily_floor = self.ea_day_start_balance * (
            1.0 - self.config.ea_daily_halt_pct / 100.0
        )
        if not self.daily_halted and equity <= ea_daily_floor + MONEY_EPS:
            self.daily_halted = True
            self.counters.daily_halts += 1
        return None

    def can_pass(self) -> bool:
        target = self.config.initial_balance * (1.0 + self.target_pct / 100.0)
        return (
            not self.positions
            and self.balance + MONEY_EPS >= target
            and len(self.trading_days) >= self.config.minimum_trading_days
        )

    def result(
        self,
        status: PhaseStatus,
        reason: str,
        *,
        discarded_tail_events: int = 0,
        discarded_raw_active: int = 0,
    ) -> "PhaseResult":
        return PhaseResult(
            phase=self.phase,
            status=status,
            reason=reason,
            calendar_days=self.phase_days,
            trading_days=len(self.trading_days),
            ending_balance=self.balance,
            ending_equity=self.equity(),
            min_equity=self.min_equity,
            max_equity=self.max_equity,
            peak_equity=self.peak_equity,
            counters=replace(self.counters),
            discarded_tail_events=discarded_tail_events,
            discarded_raw_active=discarded_raw_active,
        )


@dataclass(frozen=True)
class PhaseResult:
    phase: int
    status: PhaseStatus
    reason: str
    calendar_days: int
    trading_days: int
    ending_balance: float
    ending_equity: float
    min_equity: float
    max_equity: float
    peak_equity: float
    counters: AccountCounters
    discarded_tail_events: int = 0
    discarded_raw_active: int = 0


def _not_run_phase(phase: int) -> PhaseResult:
    return PhaseResult(
        phase,
        PhaseStatus.NOT_RUN,
        "PHASE_NOT_REACHED",
        0,
        0,
        math.nan,
        math.nan,
        math.nan,
        math.nan,
        math.nan,
        AccountCounters(),
    )


@dataclass(frozen=True)
class PathOutcome:
    path_id: int
    policy: str
    phase1: PhaseResult
    phase2: PhaseResult

    @property
    def both_pass(self) -> bool:
        return self.phase1.status is PhaseStatus.PASS and self.phase2.status is PhaseStatus.PASS

    @property
    def total_days(self) -> int:
        return self.phase1.calendar_days + self.phase2.calendar_days

    def normalized_dict(self) -> dict[str, object]:
        def phase(result: PhaseResult) -> dict[str, object]:
            return {
                "phase": result.phase,
                "status": result.status.value,
                "reason": result.reason,
                "calendar_days": result.calendar_days,
                "trading_days": result.trading_days,
                "ending_balance": result.ending_balance,
                "ending_equity": result.ending_equity,
                "min_equity": result.min_equity,
                "max_equity": result.max_equity,
                "peak_equity": result.peak_equity,
                "counters": asdict(result.counters),
                "discarded_tail_events": result.discarded_tail_events,
                "discarded_raw_active": result.discarded_raw_active,
            }

        return {
            "path_id": self.path_id,
            "policy": self.policy,
            "phase1": phase(self.phase1),
            "phase2": phase(self.phase2),
        }


def simulate_two_phase_path(
    tape: CalendarTape,
    metas: Mapping[str, SymbolMeta],
    policy: RiskPolicy,
    source_indices: Sequence[int],
    *,
    config: SimulationConfig = SimulationConfig(),
    path_id: int = 0,
) -> PathOutcome:
    required = 2 * config.max_calendar_days_per_phase
    if len(source_indices) < required:
        raise InputInvariantError(f"source stream needs at least {required} calendar days")

    cursor = ReplayCursor(tape)
    raw = RawCapacityTracker(config.global_cap, config.cluster_cap)
    account = PhaseAccount(1, policy.phase1_risk, metas, config, risk_policy=policy)
    phase1: PhaseResult | None = None
    previous_source_index: int | None = None

    for replay_day, source_index in enumerate(source_indices):
        source_index = int(source_index)
        if not 0 <= source_index < tape.n_days:
            raise InputInvariantError(f"source day index out of range: {source_index}")
        if previous_source_index is not None and source_index != previous_source_index + 1:
            if (
                raw.active
                or cursor.pending
                or not tape.flat_boundary_at_index(previous_source_index + 1)
                or not tape.flat_boundary_at_index(source_index)
            ):
                raise BootstrapOverlapError(
                    "non-flat or occupied lifecycle at sampled block boundary"
                )
        previous_source_index = source_index
        account.begin_day(replay_day)
        boundary_terminal = account.check_rails()
        if boundary_terminal is not None:
            status, reason = boundary_terminal
            failed = account.result(status, reason)
            account.end_day()
            if account.phase == 1:
                return PathOutcome(path_id, policy.name, failed, _not_run_phase(2))
            assert phase1 is not None
            return PathOutcome(path_id, policy.name, phase1, failed)
        rows = cursor.events_for_day(replay_day, source_index)
        transition = False
        for row in rows:
            raw.process(row)
            account.ensure_ea_day(row.ea_day)
            account.process(row)
            terminal = account.check_rails()
            if terminal is not None:
                status, reason = terminal
                failed = account.result(status, reason)
                account.end_day()
                if account.phase == 1:
                    return PathOutcome(path_id, policy.name, failed, _not_run_phase(2))
                assert phase1 is not None
                return PathOutcome(path_id, policy.name, phase1, failed)

        # Recognise a target only at the end of a source calendar day and only
        # when the source tape is flat at the following Prague midnight.  This
        # prevents a working pending from being treated as a passed phase.
        if account.can_pass() and tape.flat_boundary_at_index(source_index + 1):
            discarded = cursor.discard_pending()
            raw_active = raw.reset_phase_boundary()
            passed = account.result(
                PhaseStatus.PASS,
                "TARGET_AND_MIN_DAYS",
                discarded_tail_events=discarded,
                discarded_raw_active=raw_active,
            )
            account.end_day()
            if account.phase == 1:
                phase1 = passed
                account = PhaseAccount(2, policy.phase2_risk, metas, config, risk_policy=policy)
                transition = True
            else:
                assert phase1 is not None
                return PathOutcome(path_id, policy.name, phase1, passed)

        if transition:
            continue
        account.end_day()
        if account.phase_days >= config.max_calendar_days_per_phase:
            timeout = account.result(PhaseStatus.TIMEOUT, "CALENDAR_CEILING")
            if account.phase == 1:
                return PathOutcome(path_id, policy.name, timeout, _not_run_phase(2))
            assert phase1 is not None
            return PathOutcome(path_id, policy.name, phase1, timeout)

    raise InputInvariantError("source stream exhausted unexpectedly")


def wilson_one_sided(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    if total <= 0 or successes < 0 or successes > total:
        raise InputInvariantError("invalid Wilson counts")
    if not 0.5 < confidence < 1.0:
        raise InputInvariantError("confidence must be between 0.5 and 1")
    z = NormalDist().inv_cdf(confidence)
    p = successes / total
    z2 = z * z
    den = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / den
    half = z / den * math.sqrt(p * (1.0 - p) / total + z2 / (4.0 * total * total))
    return max(0.0, center - half), min(1.0, center + half)


def exact_paired_delta_lower(
    candidate: Sequence[bool],
    control: Sequence[bool],
    confidence: float = 0.95,
) -> tuple[float, int, int, float, float]:
    """Coverage-valid lower bound for the unconditional paired pass delta.

    ``P(candidate pass)-P(control pass)`` equals ``p10-p01`` for the two
    discordant multinomial cells.  Bonferroni-adjusted one-sided exact
    Clopper-Pearson marginal bounds give a conservative joint 95% lower bound
    ``p10_lower-p01_upper`` without treating the discordant fraction as fixed.
    """

    if len(candidate) != len(control) or len(candidate) == 0:
        raise InputInvariantError("paired outcomes must be non-empty and equal length")
    if not 0.5 < confidence < 1.0:
        raise InputInvariantError("confidence must be between 0.5 and 1")
    n10 = sum(bool(a) and not bool(b) for a, b in zip(candidate, control))
    n01 = sum(not bool(a) and bool(b) for a, b in zip(candidate, control))
    alpha = 1.0 - confidence
    try:
        from scipy.stats import beta as beta_distribution
    except ImportError as exc:  # pragma: no cover - project dependency is binding
        raise RuntimeError("scipy is required for exact Clopper-Pearson bounds") from exc
    total = len(candidate)
    tail = alpha / 2.0
    p10_lower = (
        0.0
        if n10 == 0
        else float(beta_distribution.ppf(tail, n10, total - n10 + 1))
    )
    p01_upper = (
        1.0
        if n01 == total
        else float(beta_distribution.ppf(1.0 - tail, n01 + 1, total - n01))
    )
    return p10_lower - p01_upper, n10, n01, p10_lower, p01_upper


@dataclass(frozen=True)
class MonteCarloSummary:
    paths: int
    both_passes: int
    both_probability: float
    both_wilson_lower: float
    both_wilson_upper: float
    phase1_probability: float
    phase2_conditional_probability: float
    firm_breach_probability: float
    firm_breach_wilson_upper: float
    hard_halt_probability: float
    hard_halt_wilson_upper: float
    timeout_probability: float
    timeout_wilson_upper: float
    median_total_days_success: float
    p90_total_days_success: float


@dataclass(frozen=True)
class MonteCarloRun:
    policy: RiskPolicy
    outcomes: tuple[PathOutcome, ...]

    def normalized_bytes(self) -> bytes:
        payload = [outcome.normalized_dict() for outcome in self.outcomes]
        return (json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=True) + "\n").encode(
            "utf-8"
        )

    def sha256(self) -> str:
        return hashlib.sha256(self.normalized_bytes()).hexdigest()

    def summary(self) -> MonteCarloSummary:
        n = len(self.outcomes)
        if n == 0:
            raise InputInvariantError("cannot summarize zero paths")
        both = np.asarray([x.both_pass for x in self.outcomes], dtype=bool)
        p1 = np.asarray([x.phase1.status is PhaseStatus.PASS for x in self.outcomes], dtype=bool)
        p2 = np.asarray([x.phase2.status is PhaseStatus.PASS for x in self.outcomes], dtype=bool)
        firm = np.asarray(
            [
                x.phase1.status is PhaseStatus.FIRM_BREACH
                or x.phase2.status is PhaseStatus.FIRM_BREACH
                for x in self.outcomes
            ],
            dtype=bool,
        )
        hard = np.asarray(
            [
                x.phase1.status is PhaseStatus.HARD_HALT
                or x.phase2.status is PhaseStatus.HARD_HALT
                for x in self.outcomes
            ],
            dtype=bool,
        )
        timeout = np.asarray(
            [
                x.phase1.status is PhaseStatus.TIMEOUT
                or x.phase2.status is PhaseStatus.TIMEOUT
                for x in self.outcomes
            ],
            dtype=bool,
        )
        both_n = int(both.sum())
        both_lo, both_hi = wilson_one_sided(both_n, n)
        _, firm_hi = wilson_one_sided(int(firm.sum()), n)
        _, hard_hi = wilson_one_sided(int(hard.sum()), n)
        _, timeout_hi = wilson_one_sided(int(timeout.sum()), n)
        successful_days = np.asarray(
            [outcome.total_days for outcome in self.outcomes if outcome.both_pass], dtype=float
        )
        if successful_days.size:
            median = float(np.median(successful_days))
            p90 = float(np.quantile(successful_days, 0.90, method="higher"))
        else:
            median = math.nan
            p90 = math.nan
        p1_n = int(p1.sum())
        return MonteCarloSummary(
            paths=n,
            both_passes=both_n,
            both_probability=both_n / n,
            both_wilson_lower=both_lo,
            both_wilson_upper=both_hi,
            phase1_probability=p1_n / n,
            phase2_conditional_probability=float(p2.sum() / p1_n) if p1_n else math.nan,
            firm_breach_probability=float(firm.mean()),
            firm_breach_wilson_upper=firm_hi,
            hard_halt_probability=float(hard.mean()),
            hard_halt_wilson_upper=hard_hi,
            timeout_probability=float(timeout.mean()),
            timeout_wilson_upper=timeout_hi,
            median_total_days_success=median,
            p90_total_days_success=p90,
        )


def run_monte_carlo(
    tape: CalendarTape,
    metas: Mapping[str, SymbolMeta],
    policies: Sequence[RiskPolicy],
    *,
    paths: int,
    bootstrap: BootstrapSpec = BootstrapSpec(),
    config: SimulationConfig = SimulationConfig(),
) -> dict[str, MonteCarloRun]:
    if paths <= 0 or not policies:
        raise InputInvariantError("Monte Carlo requires positive paths and at least one policy")
    if len({policy.name for policy in policies}) != len(policies):
        raise InputInvariantError("policy names must be unique")
    gathered: dict[str, list[PathOutcome]] = {policy.name: [] for policy in policies}
    stream_days = 2 * config.max_calendar_days_per_phase
    for path_id in range(paths):
        indices = bootstrap.source_indices(tape, path_id, stream_days)
        for policy in policies:
            outcome = simulate_two_phase_path(
                tape,
                metas,
                policy,
                indices,
                config=config,
                path_id=path_id,
            )
            gathered[policy.name].append(outcome)
    return {
        policy.name: MonteCarloRun(policy, tuple(gathered[policy.name])) for policy in policies
    }


def paired_run_delta_lower(
    candidate: MonteCarloRun,
    control: MonteCarloRun,
    confidence: float = 0.95,
) -> tuple[float, int, int, float, float]:
    candidate_ids = [x.path_id for x in candidate.outcomes]
    control_ids = [x.path_id for x in control.outcomes]
    if candidate_ids != control_ids:
        raise InputInvariantError("paired runs do not share ordered path ids")
    return exact_paired_delta_lower(
        [x.both_pass for x in candidate.outcomes],
        [x.both_pass for x in control.outcomes],
        confidence,
    )


# ---------------------------------------------------------------------------
# Seeded synthetic fidelity checks only.  No frozen or live data is loaded.
# ---------------------------------------------------------------------------


def _utc_epoch(text: str) -> int:
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def _event(
    event_id: str,
    trade_id: str,
    epoch: int,
    sequence: int,
    kind: EventKind,
    *,
    symbol: str = "SYN",
    cluster: str = "C1",
    side: int = 1,
    price: float = 100.0,
    r_component: float = 0.0,
    open_r: float = 0.0,
    remaining: float = 1.0,
    cost_r: float = 0.0,
    mark_role: str = "neutral",
) -> LifecycleEvent:
    return LifecycleEvent(
        event_id,
        trade_id,
        symbol,
        cluster,
        epoch,
        sequence,
        kind,
        side,
        price,
        r_component,
        open_r,
        remaining,
        10.0,
        10.0,
        cost_r,
        mark_role,
    )


def _replay(event: LifecycleEvent, trade_id: str | None = None, day: int = 0) -> ReplayEvent:
    rid = trade_id or event.trade_id
    return ReplayEvent(day, day, 0, 0, day, rid, f"r:{event.event_id}", event)


def _benign_config(**changes: object) -> SimulationConfig:
    base = SimulationConfig(
        initial_balance=100.0,
        phase1_target_pct=10.0,
        phase2_target_pct=5.0,
        firm_daily_loss_pct=99.0,
        firm_static_loss_pct=99.0,
        minimum_trading_days=1,
        max_calendar_days_per_phase=20,
        ea_daily_halt_pct=99.0,
        ea_peak_drawdown_pct=99.0,
        ea_static_halt_pct=99.0,
        ea_fills_per_day=8,
        ea_consecutive_losses=4,
        global_cap=2,
        cluster_cap=1,
        min_lot_budget_multiple=1.5,
        cost_multiplier=1.0,
        equity_mode=EquityMode.MARKS,
    )
    return replace(base, **changes)


def synthetic_fidelity_tests() -> tuple[str, ...]:
    passed: list[str] = []
    meta = SymbolMeta("SYN", 1.0, 10.0, 12.0, 0.1, 0.1, 100.0)

    lot = size_for_risk(100_000.0, 0.002, 10.0, meta)
    assert lot.volume == 2.0 and lot.actual_risk_cash == 200.0
    min_meta = SymbolMeta("MIN", 1.0, 10.0, 10.0, 1.0, 1.0, 100.0)
    assert size_for_risk(100.0, 0.07, 1.0, min_meta).min_substitution
    assert size_for_risk(100.0, 0.06, 1.0, min_meta).rejection == "min_lot_overrisk"
    assert floor_risk_volume(0.2999999999995, 0.1) == 0.2
    assert floor_volume(0.2999999999995, 0.1) == 0.3
    passed.append("lot_sizing_floor_min_1p5x_max")

    assert partial_close_volume(0.3, 0.5, meta) == 0.1
    assert partial_close_volume(0.1, 0.5, meta) == 0.0
    passed.append("partial_floor_and_skip")

    # 0.3 lots: partial floors to 0.1. Profit tick value is deliberately 20%
    # above loss tick value, proving gross cash uses the side-specific metadata.
    account = PhaseAccount(1, 0.31, {"SYN": meta}, _benign_config())
    account.begin_day(0)
    e0 = _event("e0", "t0", 1, 1, EventKind.ENTRY, cost_r=0.1)
    ep = _event(
        "ep", "t0", 2, 2, EventKind.PARTIAL, price=110.0, r_component=0.5,
        open_r=0.5, remaining=0.5,
    )
    ef = _event(
        "ef", "t0", 3, 3, EventKind.FINAL, price=120.0, r_component=1.0,
        open_r=0.0, remaining=0.0,
    )
    account.process(_replay(e0, "t0"))
    account.process(_replay(ep, "t0"))
    account.process(_replay(ef, "t0"))
    # risk=30; cost=3; profits=(10 ticks*12*0.1)+(20*12*0.2)=60
    assert abs(account.balance - 157.0) < 1e-12
    assert account.counters.partial_executed == 1
    passed.append("entry_cost_partial_final_tick_cash")

    streak = PhaseAccount(1, 0.20, {"SYN": meta}, _benign_config())
    streak.begin_day(0)
    for idx in range(4):
        tid = f"loss{idx}"
        entry = _event(f"{tid}e", tid, 10 + idx * 3, idx * 3, EventKind.ENTRY)
        partial = _event(
            f"{tid}p", tid, 11 + idx * 3, idx * 3 + 1, EventKind.PARTIAL,
            price=110.0, r_component=0.5, open_r=0.5, remaining=0.5,
        )
        final = _event(
            f"{tid}f", tid, 12 + idx * 3, idx * 3 + 2, EventKind.FINAL,
            price=80.0, r_component=-1.0, open_r=0.0, remaining=0.0,
        )
        streak.process(_replay(entry, tid))
        before = streak.consecutive_losses_today
        streak.process(_replay(partial, tid))
        assert streak.consecutive_losses_today == before
        streak.process(_replay(final, tid))
    assert streak.consecutive_losses_today == 4
    fifth = _event("fifth", "fifth", 99, 99, EventKind.ENTRY)
    streak.process(_replay(fifth, "fifth"))
    assert streak.counters.skipped_consecutive == 1
    passed.append("final_only_loss_streak")

    three_way = PhaseAccount(1, 0.20, {"SYN": meta}, _benign_config())
    three_way.begin_day(0)
    for idx, exit_price in enumerate((90.0, 100.0, 110.0)):
        tid = f"three{idx}"
        three_way.process(
            _replay(_event(f"{tid}e", tid, 200 + idx * 2, 200 + idx * 2,
                           EventKind.ENTRY), tid)
        )
        three_way.process(
            _replay(_event(f"{tid}f", tid, 201 + idx * 2, 201 + idx * 2,
                           EventKind.FINAL, price=exit_price,
                           r_component=(exit_price - 100.0) / 10.0,
                           open_r=0.0, remaining=0.0), tid)
        )
        expected = (1, 1, 0)[idx]
        assert three_way.consecutive_losses_today == expected
    passed.append("loss_flat_win_streak_three_way")

    zone = ZoneInfo(PRAGUE)
    before_day, _ = _local_parts(_utc_epoch("2026-01-01T22:59:00Z"), zone)
    after_day, _ = _local_parts(_utc_epoch("2026-01-01T23:01:00Z"), zone)
    assert before_day.isoformat() == "2026-01-01"
    assert after_day.isoformat() == "2026-01-02"
    summer_before, _ = _local_parts(_utc_epoch("2026-07-01T21:59:00Z"), zone)
    summer_after, _ = _local_parts(_utc_epoch("2026-07-01T22:01:00Z"), zone)
    assert summer_before.isoformat() == "2026-07-01"
    assert summer_after.isoformat() == "2026-07-02"
    fold_day_a, fold_second_a = _local_parts(_utc_epoch("2026-10-25T00:30:00Z"), zone)
    fold_day_b, fold_second_b = _local_parts(_utc_epoch("2026-10-25T01:30:00Z"), zone)
    assert fold_day_a == fold_day_b and fold_second_b - fold_second_a == 3600
    passed.append("prague_dst_day_boundary")

    dual_clock = PhaseAccount(1, 0.01, {"SYN": meta}, _benign_config())
    dual_clock.begin_day(0)
    dual_clock.ensure_ea_day(0)
    dual_clock.daily_halted = True
    dual_clock.end_day()
    dual_clock.begin_day(1)  # FTMO Prague rollover alone must not reset EA rails.
    assert dual_clock.daily_halted
    dual_clock.ensure_ea_day(1)
    assert not dual_clock.daily_halted
    passed.append("dual_ftmo_and_ea_day_resets")

    # Explicit frame keeps four zero-event calendar days around one lifecycle.
    base = _utc_epoch("2026-01-05T10:00:00Z")
    tape_events = (
        _event("te", "tt", base, 1, EventKind.ENTRY),
        _event("tm", "tt", base + 900, 2, EventKind.MARK, price=105.0, open_r=0.5),
        _event(
            "tf", "tt", base + 1800, 3, EventKind.FINAL, price=110.0,
            r_component=1.0, open_r=0.0, remaining=0.0,
        ),
    )
    tape = CalendarTape.from_events(
        tape_events, first_day="2026-01-03", last_day="2026-01-07"
    )
    assert tape.n_days == 5 and sum(bool(day.trades) for day in tape.days) == 1
    occupied = CalendarTape.from_events(
        (),
        first_day="2026-01-05",
        last_day="2026-01-07",
        occupancy_intervals=(
            OccupancyInterval(
                "pending-cross-midnight",
                None,
                "SYN",
                "C1",
                _utc_epoch("2026-01-05T22:30:00Z"),
                _utc_epoch("2026-01-06T00:30:00Z"),
            ),
        ),
    )
    assert not occupied.flat_boundary_at_index(1)
    passed.append("pending_occupancy_blocks_bootstrap_boundary")
    starts = tape.eligible_flat_block_starts(2)
    bootstrap = BootstrapSpec(seed=123, block_length=2, eligible_block_starts=starts)
    a = bootstrap.source_indices(tape, 7, 9)
    b = bootstrap.source_indices(tape, 7, 9)
    assert np.array_equal(a, b)
    assert all(a[i + 1] == a[i] + 1 for i in range(0, 8, 2))
    passed.append("zero_days_flat_mbb_determinism")

    # A hand-built non-flat stitch is rejected instead of clipping the trade.
    cross_base = _utc_epoch("2026-01-05T22:30:00Z")  # 23:30 Prague
    y_base = _utc_epoch("2026-01-06T23:15:00Z")      # Jan 7, 00:15 Prague
    cross = CalendarTape.from_events(
        (
            _event("x0", "x", cross_base, 10, EventKind.ENTRY),
            _event("x1", "x", cross_base + 3600, 11, EventKind.FINAL,
                   price=90.0, r_component=-1.0, remaining=0.0),
            _event("y0", "y", y_base, 20, EventKind.ENTRY),
            _event("y1", "y", y_base + 900, 21, EventKind.FINAL,
                   price=90.0, r_component=-1.0, remaining=0.0),
        ),
        first_day="2026-01-05",
        last_day="2026-01-07",
    )
    cursor = ReplayCursor(cross)
    tracker = RawCapacityTracker(2, 1)
    tracker.process(cursor.events_for_day(0, 0)[0])
    rejected = False
    try:
        for row in cursor.events_for_day(1, 2):
            tracker.process(row)
    except BootstrapOverlapError:
        rejected = True
    assert rejected
    passed.append("cross_day_stitch_overlap_fails")

    lo, hi = wilson_one_sided(88_000, 100_000)
    assert lo < 0.88 < hi and abs(Z95_ONE_SIDED - 1.6448536269514715) < 1e-12
    delta, n10, n01, p10_lower, p01_upper = exact_paired_delta_lower(
        [True] * 90 + [False] * 10,
        [False] * 90 + [True] * 2 + [False] * 8,
    )
    assert (n10, n01) == (90, 2)
    assert 0.0 < p10_lower < 1.0 and 0.0 < p01_upper < 1.0 and delta > 0.0
    zero = exact_paired_delta_lower([True, False], [True, False])
    assert zero[0] < 0.0 and zero[1:3] == (0, 0)
    passed.append("wilson_and_exact_paired_bounds")

    phase_meta = SymbolMeta("SYN", 1.0, 1.0, 1.0, 0.01, 0.01, 100.0)
    equality = PhaseAccount(1, 0.05, {"SYN": phase_meta}, SimulationConfig(
        initial_balance=100.0,
        minimum_trading_days=1,
        max_calendar_days_per_phase=5,
    ))
    equality.begin_day(0)
    equality_entry = _event("eqe", "eq", 1, 1, EventKind.ENTRY, cost_r=1.0)
    equality.process(_replay(equality_entry, "eq"))
    terminal = equality.check_rails()
    assert terminal == (PhaseStatus.FIRM_BREACH, "FTMO_DAILY_LOSS")
    passed.append("ftmo_daily_equality_is_failure")

    daily = PhaseAccount(1, 0.04, {"SYN": phase_meta}, SimulationConfig(
        initial_balance=100.0,
        minimum_trading_days=1,
        max_calendar_days_per_phase=5,
    ))
    daily.begin_day(0)
    daily_entry = _event("dhe", "dh", 1, 1, EventKind.ENTRY, cost_r=1.0)
    daily.process(_replay(daily_entry, "dh"))
    assert daily.check_rails() is None and daily.daily_halted
    daily.process(_replay(_event("dh2", "dh2", 2, 2, EventKind.ENTRY), "dh2"))
    assert daily.counters.skipped_daily_halt == 1
    passed.append("ea_daily_halt_blocks_fresh_risk")

    envelope_entry = _event("ove", "ov", 1, 1, EventKind.ENTRY)
    equities: dict[EquityMode, float] = {}
    for mode in (EquityMode.MARKS, EquityMode.TWO_STOP, EquityMode.GAP_2X_STOP):
        cfg = _benign_config(equity_mode=mode)
        state = PhaseAccount(1, 0.01, {"SYN": phase_meta}, cfg)
        state.begin_day(0)
        state.process(_replay(envelope_entry, "ov"))
        equities[mode] = state.equity()
    assert equities == {
        EquityMode.MARKS: 100.0,
        EquityMode.TWO_STOP: 99.0,
        EquityMode.GAP_2X_STOP: 98.0,
    }
    peak_state = PhaseAccount(
        1, 0.01, {"SYN": phase_meta}, _benign_config(equity_mode=EquityMode.TWO_STOP)
    )
    peak_state.begin_day(0)
    peak_state.process(_replay(envelope_entry, "ov"))
    favorable = _event(
        "ovm1", "ov", 2, 2, EventKind.MARK, price=110.0, open_r=1.0,
        mark_role="favorable",
    )
    peak_state.process(_replay(favorable, "ov"))
    assert peak_state.check_rails() is None
    assert abs(peak_state.peak_equity - 101.0) < 1e-12
    adverse = _event(
        "ovm2", "ov", 3, 3, EventKind.MARK, price=99.0, open_r=-0.1,
        mark_role="adverse",
    )
    peak_state.process(_replay(adverse, "ov"))
    assert peak_state.check_rails() is None
    assert abs(peak_state.min_equity - 99.0) < 1e-12
    passed.append("mark_two_stop_and_gap_equity")

    # One +1R completed trade is replayed each sampled calendar day.  The 10%
    # and 5% targets are crossed early, but each phase is held until four
    # distinct entry-days.  Phase 2 begins on the next replay day, using the
    # same pre-generated stream rather than an independent draw.
    win_base = _utc_epoch("2026-02-02T10:00:00Z")
    win_tape = CalendarTape.from_events(
        (
            _event("we", "win", win_base, 1, EventKind.ENTRY),
            _event(
                "wf", "win", win_base + 900, 2, EventKind.FINAL,
                price=110.0, r_component=1.0, open_r=0.0, remaining=0.0,
            ),
        ),
        first_day="2026-02-02",
        last_day="2026-02-02",
    )
    phase_cfg = SimulationConfig(
        initial_balance=100.0,
        minimum_trading_days=4,
        max_calendar_days_per_phase=5,
        equity_mode=EquityMode.MARKS,
    )
    phase_policy = RiskPolicy("SYN_POLICY", 0.03, 0.03)
    outcome = simulate_two_phase_path(
        win_tape,
        {"SYN": phase_meta},
        phase_policy,
        np.zeros(10, dtype=np.int32),
        config=phase_cfg,
        path_id=7,
    )
    assert outcome.both_pass
    assert outcome.phase1.calendar_days == 4 and outcome.phase2.calendar_days == 4
    assert outcome.total_days == 8
    assert outcome.phase1.trading_days == 4 and outcome.phase2.trading_days == 4
    passed.append("sequential_two_phase_min_days_reset")

    one_day_bootstrap = BootstrapSpec(seed=99, block_length=1, eligible_block_starts=(0,))
    run1 = run_monte_carlo(
        win_tape,
        {"SYN": phase_meta},
        (phase_policy,),
        paths=3,
        bootstrap=one_day_bootstrap,
        config=phase_cfg,
    )[phase_policy.name]
    run2 = run_monte_carlo(
        win_tape,
        {"SYN": phase_meta},
        (phase_policy,),
        paths=3,
        bootstrap=one_day_bootstrap,
        config=phase_cfg,
    )[phase_policy.name]
    summary = run1.summary()
    assert run1.normalized_bytes() == run2.normalized_bytes() and run1.sha256() == run2.sha256()
    assert summary.both_passes == 3 and summary.p90_total_days_success == 8.0
    passed.append("monte_carlo_bytes_and_success_p90_deterministic")

    return tuple(passed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run seeded synthetic fidelity tests only (never loads research data)",
    )
    args = parser.parse_args()
    if not args.self_test:
        parser.error("this pure module has no research-data CLI; use --self-test")
    passed = synthetic_fidelity_tests()
    print("V130_RISK_POLICY_SYNTHETIC")
    for name in passed:
        print(f"PASS {name}")
    print(f"PASS total={len(passed)}")


if __name__ == "__main__":
    main()
