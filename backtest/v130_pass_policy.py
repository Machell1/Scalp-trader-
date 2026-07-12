"""Pure deterministic FTMO v1.30 pass-policy account engine.

This module implements the account-only layer registered in
``docs/V130_FTMO_PASS_POLICY_SPEC_2026-07-12.md``.  It deliberately performs
no data loading.  A caller must first regenerate one policy-independent E1 or
E2 causal tape and adapt its pending, position, mark, partial, swap, and final
events to :class:`AccountEvent`.

The model keeps three ledgers separate:

* closed balance, used for current-balance lot sizing and FTMO day anchors;
* open marked equity, including broker-midnight swap accrual;
* exit-deal cash by Helsinki day, used only by the deployed EA's four-loss
  classifier.

Fixed slippage is debited from balance at entry.  Its classifier allocation is
deferred pro rata to actual partial/final closed volume, so it is never charged
to balance twice.  Swap accrues against open equity on actual remaining volume
and is realized into closed balance only at the final exit.

Only :func:`self_test` creates data, and all of its fixtures are synthetic.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum, IntEnum
from typing import Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np

try:  # Support both ``python backtest/...`` and package imports.
    from .v130_risk_policy import (
        BootstrapOverlapError,
        InputInvariantError,
        SymbolMeta,
        cash_from_price,
        exact_paired_delta_lower,
        partial_close_volume,
        size_for_risk,
        wilson_one_sided,
    )
except ImportError:  # pragma: no cover - exercised by script-style runners.
    from v130_risk_policy import (
        BootstrapOverlapError,
        InputInvariantError,
        SymbolMeta,
        cash_from_price,
        exact_paired_delta_lower,
        partial_close_volume,
        size_for_risk,
        wilson_one_sided,
    )


SYMBOLS = ("US30.cash", "US100.cash", "JP225.cash")
PRAGUE_NAME = "Europe/Prague"
EA_SERVER_NAME = "Europe/Helsinki"
PRAGUE = ZoneInfo(PRAGUE_NAME)
EA_SERVER = ZoneInfo(EA_SERVER_NAME)
MONEY_EPS = 1e-9
FRACTION_EPS = 1e-12


class AccountEventKind(str, Enum):
    PENDING_OPEN = "pending_open"
    PENDING_CANCEL = "pending_cancel"
    ENTRY = "entry"
    MARK = "mark"
    SWAP = "swap"
    PARTIAL = "partial"
    FINAL = "final"


class EquityMode(str, Enum):
    MARKS = "marks"
    TWO_STOP = "two_stop"
    GAP_2X_STOP = "gap_2x_stop"


class PhaseStatus(IntEnum):
    PASS = 1
    FIRM_BREACH = 2
    HARD_HALT = 3
    TIMEOUT = 4
    NOT_RUN = 5


class ResultReason(IntEnum):
    TARGET_AND_MIN_DAYS = 1
    FTMO_DAILY_LOSS = 2
    FTMO_STATIC_LOSS = 3
    EA_PEAK_DRAWDOWN = 4
    EA_STATIC_FLOOR = 5
    CALENDAR_CEILING = 6
    PHASE_NOT_REACHED = 7


_KIND_ALIASES = {
    "pending_open": AccountEventKind.PENDING_OPEN,
    "pending_placement": AccountEventKind.PENDING_OPEN,
    "pending_cancel": AccountEventKind.PENDING_CANCEL,
    "pending_cancellation": AccountEventKind.PENDING_CANCEL,
    "entry": AccountEventKind.ENTRY,
    "entry_fill": AccountEventKind.ENTRY,
    "mark": AccountEventKind.MARK,
    "bar_mark": AccountEventKind.MARK,
    "swap": AccountEventKind.SWAP,
    "partial": AccountEventKind.PARTIAL,
    "partial_fill": AccountEventKind.PARTIAL,
    "final": AccountEventKind.FINAL,
    "final_exit": AccountEventKind.FINAL,
}


def _kind(value: AccountEventKind | str) -> AccountEventKind:
    if isinstance(value, AccountEventKind):
        return value
    try:
        return _KIND_ALIASES[str(value).strip().lower()]
    except KeyError as exc:
        raise InputInvariantError(f"unsupported account event kind: {value!r}") from exc


def _as_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _local_midnight_epoch(day: date, zone: ZoneInfo) -> int:
    return int(datetime.combine(day, time.min, zone).timestamp())


def _local_parts(epoch: int, zone: ZoneInfo) -> tuple[date, int]:
    local = datetime.fromtimestamp(int(epoch), timezone.utc).astimezone(zone)
    day = local.date()
    # Epoch distance preserves the repeated autumn hour rather than collapsing
    # the two 02:xx wall-clock folds.
    return day, int(epoch) - _local_midnight_epoch(day, zone)


@dataclass(frozen=True)
class AccountEvent:
    """One immutable policy-independent account event.

    ``swap_cash_per_lot`` is the raw one-day broker cash value per lot before
    positive-credit suppression, Friday multiplication, and E1/E2 stress.
    ``swap_days`` is normally 1 or 3 and ``swap_multiplier`` is normally 1 or
    2.  The account applies the resulting debit to actual open volume.

    ``remaining_fraction`` is used only by PARTIAL/FINAL.  The partial helper
    applies the requested reduction to original volume and may skip it when
    broker lot rules make either leg invalid.
    """

    event_id: str
    trade_id: str
    symbol: str
    cluster: str
    epoch: int
    sequence: int
    kind: AccountEventKind | str
    side: int
    price: float = 0.0
    stop_distance: float = 0.0
    fixed_slippage_r: float = 0.0
    remaining_fraction: float = 1.0
    swap_cash_per_lot: float = 0.0
    swap_days: int = 1
    swap_multiplier: float = 1.0
    mark_role: str = "neutral"

    def normalized_kind(self) -> AccountEventKind:
        return _kind(self.kind)


@dataclass(frozen=True)
class TemplateEvent:
    event: AccountEvent
    day_offset: int
    second_of_day: int
    ea_day_offset: int


@dataclass(frozen=True)
class TradeTemplate:
    trade_id: str
    symbol: str
    cluster: str
    owner_day: date
    start_epoch: int
    end_epoch: int
    events: tuple[TemplateEvent, ...]


@dataclass(frozen=True)
class DayTemplate:
    source_day: date
    trades: tuple[TradeTemplate, ...] = ()


def _validate_events(events: Iterable[AccountEvent]) -> tuple[AccountEvent, ...]:
    rows = tuple(events)
    if not rows:
        return ()
    event_ids: set[str] = set()
    order_keys: set[tuple[int, int]] = set()
    by_trade: dict[str, list[AccountEvent]] = {}
    for row in rows:
        kind = row.normalized_kind()
        if not row.event_id or not row.trade_id or not row.symbol or not row.cluster:
            raise InputInvariantError("event/trade/symbol/cluster identifiers must be non-empty")
        if row.event_id in event_ids:
            raise InputInvariantError(f"duplicate event_id: {row.event_id}")
        event_ids.add(row.event_id)
        order_key = (int(row.epoch), int(row.sequence))
        if order_key in order_keys:
            raise InputInvariantError(f"ambiguous epoch/sequence: {order_key}")
        order_keys.add(order_key)
        if row.side not in (-1, 1):
            raise InputInvariantError(f"{row.event_id}: side must be +1 or -1")
        numeric = (
            row.price,
            row.stop_distance,
            row.fixed_slippage_r,
            row.remaining_fraction,
            row.swap_cash_per_lot,
            row.swap_multiplier,
        )
        if not all(math.isfinite(float(value)) for value in numeric):
            raise InputInvariantError(f"{row.event_id}: non-finite numeric field")
        if row.fixed_slippage_r < 0.0:
            raise InputInvariantError(f"{row.event_id}: fixed slippage R must be nonnegative")
        if row.swap_days not in (1, 3) or row.swap_multiplier < 0.0:
            raise InputInvariantError(f"{row.event_id}: invalid swap cadence/multiplier")
        if row.mark_role not in {"neutral", "favorable", "adverse"}:
            raise InputInvariantError(f"{row.event_id}: invalid mark role")
        if kind in {
            AccountEventKind.PENDING_OPEN,
            AccountEventKind.ENTRY,
            AccountEventKind.MARK,
            AccountEventKind.PARTIAL,
            AccountEventKind.FINAL,
        } and row.price <= 0.0:
            raise InputInvariantError(f"{row.event_id}: executable/mark price must be positive")
        if kind is AccountEventKind.PENDING_OPEN and row.stop_distance <= 0.0:
            raise InputInvariantError(f"{row.event_id}: pending stop distance must be positive")
        if kind is AccountEventKind.ENTRY:
            if row.fixed_slippage_r < 0.0:
                raise InputInvariantError(f"{row.event_id}: invalid entry slippage")
        elif row.fixed_slippage_r != 0.0:
            raise InputInvariantError(f"{row.event_id}: slippage may appear only at entry")
        if kind is not AccountEventKind.SWAP:
            if row.swap_cash_per_lot != 0.0 or row.swap_days != 1 or row.swap_multiplier != 1.0:
                raise InputInvariantError(f"{row.event_id}: swap fields on non-swap event")
        if kind is AccountEventKind.PARTIAL and not 0.0 < row.remaining_fraction < 1.0:
            raise InputInvariantError(f"{row.event_id}: partial remaining fraction must be in (0,1)")
        if kind is AccountEventKind.FINAL and abs(row.remaining_fraction) > FRACTION_EPS:
            raise InputInvariantError(f"{row.event_id}: final remaining fraction must be zero")
        by_trade.setdefault(row.trade_id, []).append(row)

    for trade_id, trade_rows in by_trade.items():
        trade_rows.sort(key=lambda item: (item.epoch, item.sequence))
        kinds = [row.normalized_kind() for row in trade_rows]
        if kinds[0] is not AccountEventKind.PENDING_OPEN:
            raise InputInvariantError(f"{trade_id}: pending_open must be first")
        if kinds.count(AccountEventKind.PENDING_OPEN) != 1:
            raise InputInvariantError(f"{trade_id}: require exactly one pending_open")
        entries = kinds.count(AccountEventKind.ENTRY)
        cancels = kinds.count(AccountEventKind.PENDING_CANCEL)
        finals = kinds.count(AccountEventKind.FINAL)
        partials = kinds.count(AccountEventKind.PARTIAL)
        if partials > 1:
            raise InputInvariantError(f"{trade_id}: at most one partial is allowed")
        if entries == 0:
            if cancels != 1 or finals != 0 or kinds[-1] is not AccountEventKind.PENDING_CANCEL:
                raise InputInvariantError(f"{trade_id}: unfilled pending must end in one cancellation")
            if any(kind not in {AccountEventKind.PENDING_OPEN, AccountEventKind.PENDING_CANCEL}
                   for kind in kinds):
                raise InputInvariantError(f"{trade_id}: unfilled pending has position events")
        else:
            if entries != 1 or cancels != 0 or finals != 1:
                raise InputInvariantError(f"{trade_id}: filled trade needs one entry/final and no cancel")
            entry_pos = kinds.index(AccountEventKind.ENTRY)
            final_pos = kinds.index(AccountEventKind.FINAL)
            if entry_pos == 0 or final_pos != len(kinds) - 1 or entry_pos >= final_pos:
                raise InputInvariantError(f"{trade_id}: invalid filled lifecycle order")
            for kind in kinds[entry_pos + 1 : final_pos]:
                if kind not in {
                    AccountEventKind.MARK,
                    AccountEventKind.SWAP,
                    AccountEventKind.PARTIAL,
                }:
                    raise InputInvariantError(f"{trade_id}: invalid in-position event {kind.value}")
        identity = {(row.symbol, row.cluster, row.side) for row in trade_rows}
        if len(identity) != 1:
            raise InputInvariantError(f"{trade_id}: symbol/cluster/side changed")

    return tuple(sorted(rows, key=lambda item: (item.epoch, item.sequence)))


@dataclass(frozen=True)
class PassTape:
    """Complete pending/position templates on an explicit Prague frame."""

    first_day: date
    last_day: date
    events: tuple[AccountEvent, ...]
    days: tuple[DayTemplate, ...]
    trades: tuple[TradeTemplate, ...]

    @classmethod
    def from_events(
        cls,
        events: Iterable[AccountEvent],
        *,
        first_day: date | str,
        last_day: date | str,
    ) -> "PassTape":
        first = _as_date(first_day)
        last = _as_date(last_day)
        if last < first:
            raise InputInvariantError("calendar frame ends before it starts")
        rows = _validate_events(events)
        grouped: dict[str, list[AccountEvent]] = {}
        for row in rows:
            grouped.setdefault(row.trade_id, []).append(row)

        templates: list[TradeTemplate] = []
        by_owner: dict[date, list[TradeTemplate]] = {}
        for trade_id, trade_rows in grouped.items():
            trade_rows.sort(key=lambda item: (item.epoch, item.sequence))
            owner, _ = _local_parts(trade_rows[0].epoch, PRAGUE)
            if owner < first or owner > last:
                raise InputInvariantError(f"{trade_id}: owner day outside frame")
            templated: list[TemplateEvent] = []
            for row in trade_rows:
                local_day, seconds = _local_parts(row.epoch, PRAGUE)
                ea_day, _ = _local_parts(row.epoch, EA_SERVER)
                offset = (local_day - owner).days
                ea_offset = (ea_day - owner).days
                if offset < 0:
                    raise InputInvariantError(f"{trade_id}: event precedes owner day")
                templated.append(TemplateEvent(row, offset, seconds, ea_offset))
            template = TradeTemplate(
                trade_id,
                trade_rows[0].symbol,
                trade_rows[0].cluster,
                owner,
                int(trade_rows[0].epoch),
                int(trade_rows[-1].epoch),
                tuple(templated),
            )
            templates.append(template)
            by_owner.setdefault(owner, []).append(template)

        days: list[DayTemplate] = []
        cursor = first
        while cursor <= last:
            owned = tuple(sorted(by_owner.get(cursor, ()), key=lambda x: (x.start_epoch, x.trade_id)))
            days.append(DayTemplate(cursor, owned))
            cursor += timedelta(days=1)
        return cls(
            first,
            last,
            rows,
            tuple(days),
            tuple(sorted(templates, key=lambda x: (x.start_epoch, x.trade_id))),
        )

    @property
    def n_days(self) -> int:
        return len(self.days)

    def flat_boundary_at_index(self, boundary_index: int) -> bool:
        if not 0 <= boundary_index <= self.n_days:
            raise InputInvariantError("calendar boundary index out of range")
        boundary = self.first_day + timedelta(days=boundary_index)
        epoch = _local_midnight_epoch(boundary, PRAGUE)
        return not any(trade.start_epoch < epoch < trade.end_epoch for trade in self.trades)

    def eligible_flat_block_starts(self, block_length: int) -> tuple[int, ...]:
        if block_length <= 0 or block_length > self.n_days:
            raise InputInvariantError("invalid block length")
        return tuple(
            start
            for start in range(self.n_days - block_length + 1)
            if self.flat_boundary_at_index(start)
            and self.flat_boundary_at_index(start + block_length)
        )


@dataclass(frozen=True)
class ReplayEvent:
    replay_day: int
    ea_day: int
    second_of_day: int
    source_index: int
    owner_replay_day: int
    replay_trade_id: str
    replay_event_id: str
    event: AccountEvent

    @property
    def time_key(self) -> tuple[int, int]:
        return self.replay_day, self.second_of_day

    @property
    def sort_key(self) -> tuple[int, int, str]:
        return self.second_of_day, int(self.event.sequence), self.replay_event_id


class ReplayCursor:
    def __init__(self, tape: PassTape) -> None:
        self.tape = tape
        self.pending: dict[int, list[ReplayEvent]] = {}

    def events_for_day(self, replay_day: int, source_index: int) -> list[ReplayEvent]:
        if not 0 <= source_index < self.tape.n_days:
            raise InputInvariantError(f"source day out of range: {source_index}")
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
        seen: set[tuple[int, int]] = set()
        for row in rows:
            key = (row.second_of_day, int(row.event.sequence))
            if key in seen:
                raise BootstrapOverlapError(
                    f"ambiguous stitched order on replay day {replay_day}: {key}"
                )
            seen.add(key)
        rows.sort(key=lambda row: row.sort_key)
        return rows

    def discard_pending(self) -> int:
        count = sum(len(rows) for rows in self.pending.values())
        self.pending.clear()
        return count


class RawCapacityTracker:
    """Validate the policy-independent pending/position tape after stitching."""

    def __init__(self, global_cap: int, cluster_cap: int) -> None:
        self.global_cap = global_cap
        self.cluster_cap = cluster_cap
        self.active: dict[str, tuple[str, str, str]] = {}

    def process(self, row: ReplayEvent) -> None:
        event = row.event
        kind = event.normalized_kind()
        key = row.replay_trade_id
        if kind is AccountEventKind.PENDING_OPEN:
            if key in self.active:
                raise BootstrapOverlapError(f"duplicate source pending: {key}")
            if any(symbol == event.symbol for symbol, _, _ in self.active.values()):
                raise BootstrapOverlapError(f"source symbol overlap: {event.symbol}")
            if sum(cluster == event.cluster for _, cluster, _ in self.active.values()) >= self.cluster_cap:
                raise BootstrapOverlapError(f"source cluster overlap: {event.cluster}")
            if len(self.active) >= self.global_cap:
                raise BootstrapOverlapError("source global capacity overlap")
            self.active[key] = (event.symbol, event.cluster, "pending")
            return
        if key not in self.active:
            raise BootstrapOverlapError(f"orphan source {kind.value}: {key}")
        symbol, cluster, state = self.active[key]
        if kind is AccountEventKind.PENDING_CANCEL:
            if state != "pending":
                raise BootstrapOverlapError(f"cancel for non-pending source trade: {key}")
            self.active.pop(key)
        elif kind is AccountEventKind.ENTRY:
            if state != "pending":
                raise BootstrapOverlapError(f"entry for non-pending source trade: {key}")
            self.active[key] = (symbol, cluster, "position")
        elif kind is AccountEventKind.FINAL:
            if state != "position":
                raise BootstrapOverlapError(f"final for non-position source trade: {key}")
            self.active.pop(key)
        elif state != "position":
            raise BootstrapOverlapError(f"{kind.value} for source pending: {key}")

    def reset_phase_boundary(self) -> int:
        count = len(self.active)
        self.active.clear()
        return count


def _canonical_risk_map(value: float | Mapping[str, float]) -> tuple[tuple[str, float], ...]:
    if isinstance(value, Mapping):
        keys = set(value)
        if keys != set(SYMBOLS):
            missing = sorted(set(SYMBOLS) - keys)
            extra = sorted(keys - set(SYMBOLS))
            raise InputInvariantError(f"risk map mismatch: missing={missing} extra={extra}")
        pairs = tuple((symbol, float(value[symbol])) for symbol in SYMBOLS)
    else:
        scalar = float(value)
        pairs = tuple((symbol, scalar) for symbol in SYMBOLS)
    if any(not math.isfinite(risk) or not 0.0 < risk < 1.0 for _, risk in pairs):
        raise InputInvariantError("risk fractions must be finite and in (0,1)")
    return pairs


@dataclass(frozen=True, init=False)
class RiskPolicy:
    """Complete immutable phase/symbol risk policy.

    Scalar construction remains supported and expands to the exact registered
    symbol set; lookup still rejects unknown symbols and has no fallback.
    """

    name: str
    phase1: tuple[tuple[str, float], ...]
    phase2: tuple[tuple[str, float], ...]

    def __init__(
        self,
        name: str,
        phase1: float | Mapping[str, float],
        phase2: float | Mapping[str, float],
    ) -> None:
        if not str(name):
            raise InputInvariantError("policy name must be non-empty")
        object.__setattr__(self, "name", str(name))
        object.__setattr__(self, "phase1", _canonical_risk_map(phase1))
        object.__setattr__(self, "phase2", _canonical_risk_map(phase2))

    def risk_for(self, phase: int, symbol: str) -> float:
        if symbol not in SYMBOLS:
            raise InputInvariantError(f"unregistered policy symbol: {symbol}")
        pairs = self.phase1 if phase == 1 else self.phase2 if phase == 2 else None
        if pairs is None:
            raise InputInvariantError(f"invalid FTMO phase: {phase}")
        return dict(pairs)[symbol]

    def normalized_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "phase1": dict(self.phase1),
            "phase2": dict(self.phase2),
        }


C0 = RiskPolicy("C0", 0.0030, 0.0030)
C1 = RiskPolicy("C1", 0.0020, 0.0010)
P1 = RiskPolicy(
    "P1",
    {"US30.cash": 0.0004, "US100.cash": 0.0020, "JP225.cash": 0.0020},
    {"US30.cash": 0.0002, "US100.cash": 0.0010, "JP225.cash": 0.0010},
)
POLICIES = (C0, C1, P1)


@dataclass(frozen=True)
class BootstrapSpec:
    seed: int = 13020260711
    block_length: int = 20
    mode: str = "moving_block"
    eligible_block_starts: tuple[int, ...] | None = None


@dataclass(frozen=True)
class CompiledBootstrap:
    seed: int
    block_length: int
    mode: str
    eligible: tuple[int, ...]

    @classmethod
    def compile(cls, tape: PassTape, spec: BootstrapSpec = BootstrapSpec()) -> "CompiledBootstrap":
        length = spec.block_length if spec.mode == "moving_block" else 1
        if spec.mode not in {"moving_block", "iid_calendar_day"}:
            raise InputInvariantError(f"unsupported bootstrap mode: {spec.mode}")
        derived = tape.eligible_flat_block_starts(length)
        eligible = derived if spec.eligible_block_starts is None else tuple(spec.eligible_block_starts)
        if not eligible:
            raise InputInvariantError(f"no flat {length}-day bootstrap blocks")
        if any(start not in derived for start in eligible):
            raise InputInvariantError("supplied bootstrap start is not flat at both ends")
        return cls(int(spec.seed), int(length), str(spec.mode), tuple(int(x) for x in eligible))

    def source_indices(self, path_id: int, total_days: int) -> np.ndarray:
        if path_id < 0 or total_days <= 0:
            raise InputInvariantError("path_id must be nonnegative and total_days positive")
        rng = np.random.default_rng(np.random.SeedSequence([self.seed, int(path_id)]))
        blocks = math.ceil(total_days / self.block_length)
        choices = rng.integers(0, len(self.eligible), size=blocks)
        out = np.empty(blocks * self.block_length, dtype="<i4")
        cursor = 0
        for choice in choices:
            start = self.eligible[int(choice)]
            out[cursor : cursor + self.block_length] = np.arange(
                start, start + self.block_length, dtype="<i4"
            )
            cursor += self.block_length
        return out[:total_days]


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
    equity_mode: EquityMode = EquityMode.TWO_STOP

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
        )
        if not all(math.isfinite(x) and x > 0.0 for x in positive):
            raise InputInvariantError("invalid account percentages/amounts")
        counts = (
            self.minimum_trading_days,
            self.max_calendar_days_per_phase,
            self.ea_fills_per_day,
            self.ea_consecutive_losses,
            self.global_cap,
            self.cluster_cap,
        )
        if any(int(value) <= 0 for value in counts):
            raise InputInvariantError("account limits must be positive integers")


@dataclass
class AccountCounters:
    pending_admitted: int = 0
    pending_cancel_source: int = 0
    pending_cancel_target: int = 0
    pending_cancel_daily_halt: int = 0
    entries: int = 0
    completed: int = 0
    partial_executed: int = 0
    partial_skipped_rounding: int = 0
    min_lot_rejections: int = 0
    min_lot_substitutions: int = 0
    skipped_target_freeze: int = 0
    skipped_daily_halt: int = 0
    skipped_fill_cap: int = 0
    skipped_consecutive: int = 0
    ignored_lifecycle: int = 0
    daily_halts: int = 0
    swap_events: int = 0
    positive_swap_suppressed: int = 0
    max_active: int = 0


@dataclass
class PendingRuntime:
    trade_id: str
    symbol: str
    cluster: str
    side: int
    intended_entry: float
    stop_distance: float
    volume: float
    actual_risk_cash: float


@dataclass
class PositionRuntime:
    trade_id: str
    symbol: str
    cluster: str
    side: int
    entry_price: float
    stop_distance: float
    volume: float
    current_volume: float
    actual_risk_cash: float
    mark_price: float
    fixed_slippage_cash: float
    classifier_slippage_used: float = 0.0
    accrued_swap_cash: float = 0.0
    deal_cash_by_ea_day: dict[int, float] = field(default_factory=dict)
    ledger_balance_cash: float = 0.0


@dataclass(frozen=True)
class PhaseResult:
    phase: int
    status: PhaseStatus
    reason: ResultReason
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
        ResultReason.PHASE_NOT_REACHED,
        0,
        0,
        math.nan,
        math.nan,
        math.nan,
        math.nan,
        math.nan,
        AccountCounters(),
    )


class PhaseAccount:
    def __init__(
        self,
        phase: int,
        policy: RiskPolicy,
        metas: Mapping[str, SymbolMeta],
        config: SimulationConfig,
    ) -> None:
        if set(metas) != set(SYMBOLS):
            raise InputInvariantError("SymbolMeta map must contain exactly the registered symbols")
        self.phase = int(phase)
        self.policy = policy
        self.metas = metas
        self.config = config
        self.balance = float(config.initial_balance)
        self.peak_equity = float(config.initial_balance)
        self.min_equity = float(config.initial_balance)
        self.max_equity = float(config.initial_balance)
        self.pending: dict[str, PendingRuntime] = {}
        self.positions: dict[str, PositionRuntime] = {}
        self.suppressed: set[str] = set()
        self.trading_days: set[int] = set()
        self.phase_days = 0
        self.current_replay_day: int | None = None
        self.current_ea_day: int | None = None
        self.day_start_balance = float(config.initial_balance)
        self.ea_day_start_balance = float(config.initial_balance)
        self.fills_today = 0
        self.consecutive_losses_today = 0
        self.daily_halted = False
        self.target_frozen = False
        self.target_freeze_time: tuple[int, int] | None = None
        self.last_event_role = "neutral"
        self.counters = AccountCounters()

    @property
    def target_pct(self) -> float:
        return self.config.phase1_target_pct if self.phase == 1 else self.config.phase2_target_pct

    @property
    def target_balance(self) -> float:
        return self.config.initial_balance * (1.0 + self.target_pct / 100.0)

    def _meta(self, symbol: str) -> SymbolMeta:
        try:
            meta = self.metas[symbol]
        except KeyError as exc:  # defensive despite constructor exactness.
            raise InputInvariantError(f"missing SymbolMeta for {symbol}") from exc
        if meta.symbol != symbol:
            raise InputInvariantError(f"SymbolMeta key/name mismatch for {symbol}")
        return meta

    def begin_day(self, replay_day: int) -> None:
        if self.current_replay_day is not None:
            raise InputInvariantError("begin_day before prior end_day")
        self.current_replay_day = int(replay_day)
        self.phase_days += 1
        self.day_start_balance = self.balance
        self.last_event_role = "neutral"

    def end_day(self) -> None:
        self.current_replay_day = None

    def ensure_ea_day(self, ea_day: int) -> None:
        ea_day = int(ea_day)
        if self.current_ea_day == ea_day:
            return
        if self.current_ea_day is not None and ea_day < self.current_ea_day:
            raise BootstrapOverlapError("EA server-day token moved backwards")
        self.current_ea_day = ea_day
        self.ea_day_start_balance = self.balance
        self.fills_today = 0
        self.consecutive_losses_today = 0
        self.daily_halted = False

    def _all_active(self) -> tuple[tuple[str, str], ...]:
        return tuple((x.symbol, x.cluster) for x in self.pending.values()) + tuple(
            (x.symbol, x.cluster) for x in self.positions.values()
        )

    def _capacity_assert(self, symbol: str, cluster: str) -> None:
        active = self._all_active()
        if any(existing_symbol == symbol for existing_symbol, _ in active):
            raise BootstrapOverlapError(f"account symbol overlap: {symbol}")
        if sum(existing_cluster == cluster for _, existing_cluster in active) >= self.config.cluster_cap:
            raise BootstrapOverlapError(f"account cluster overlap: {cluster}")
        if len(active) >= self.config.global_cap:
            raise BootstrapOverlapError("account global capacity overlap")

    def _cancel_all_pending(self, reason: str) -> None:
        for trade_id in tuple(self.pending):
            self.pending.pop(trade_id)
            self.suppressed.add(trade_id)
            if reason == "target":
                self.counters.pending_cancel_target += 1
            elif reason == "daily_halt":
                self.counters.pending_cancel_daily_halt += 1

    def advance_time(self, time_key: tuple[int, int]) -> None:
        if (
            self.target_frozen
            and self.target_freeze_time is not None
            and time_key > self.target_freeze_time
            and self.pending
        ):
            self._cancel_all_pending("target")

    def _marked_position_cash(self, runtime: PositionRuntime) -> float:
        return cash_from_price(
            runtime.entry_price,
            runtime.mark_price,
            runtime.side,
            runtime.current_volume,
            self._meta(runtime.symbol),
        ) + runtime.accrued_swap_cash

    def _conservative_position_cash(self, runtime: PositionRuntime) -> float:
        marked_price_cash = cash_from_price(
            runtime.entry_price,
            runtime.mark_price,
            runtime.side,
            runtime.current_volume,
            self._meta(runtime.symbol),
        )
        if self.config.equity_mode is EquityMode.MARKS:
            stressed = marked_price_cash
        else:
            multiple = 1.0 if self.config.equity_mode is EquityMode.TWO_STOP else 2.0
            meta = self._meta(runtime.symbol)
            envelope = -(
                runtime.stop_distance
                / meta.trade_tick_size
                * meta.trade_tick_value_loss
                * runtime.current_volume
                * multiple
            )
            stressed = min(marked_price_cash, envelope)
        return stressed + runtime.accrued_swap_cash

    def marked_equity(self) -> float:
        return self.balance + sum(self._marked_position_cash(x) for x in self.positions.values())

    def equity(self) -> float:
        return self.balance + sum(
            self._conservative_position_cash(x) for x in self.positions.values()
        )

    def _suppress(self, trade_id: str) -> None:
        self.suppressed.add(trade_id)

    def process(self, row: ReplayEvent) -> None:
        if self.current_replay_day is None:
            raise InputInvariantError("event processed outside a calendar day")
        event = row.event
        kind = event.normalized_kind()
        trade_id = row.replay_trade_id
        self.last_event_role = event.mark_role if kind in {
            AccountEventKind.MARK,
            AccountEventKind.PARTIAL,
        } else "neutral"

        if kind is AccountEventKind.PENDING_OPEN:
            if trade_id in self.pending or trade_id in self.positions or trade_id in self.suppressed:
                raise BootstrapOverlapError(f"duplicate account lifecycle: {trade_id}")
            if self.target_frozen:
                self.counters.skipped_target_freeze += 1
                self._suppress(trade_id)
                return
            if self.daily_halted:
                self.counters.skipped_daily_halt += 1
                self._suppress(trade_id)
                return
            if self.fills_today >= self.config.ea_fills_per_day:
                self.counters.skipped_fill_cap += 1
                self._suppress(trade_id)
                return
            if self.consecutive_losses_today >= self.config.ea_consecutive_losses:
                self.counters.skipped_consecutive += 1
                self._suppress(trade_id)
                return
            self._capacity_assert(event.symbol, event.cluster)
            meta = self._meta(event.symbol)
            decision = size_for_risk(
                self.balance,
                self.policy.risk_for(self.phase, event.symbol),
                event.stop_distance,
                meta,
                min_budget_multiple=self.config.min_lot_budget_multiple,
            )
            if decision.rejection:
                self.counters.min_lot_rejections += 1
                self._suppress(trade_id)
                return
            if decision.min_substitution:
                self.counters.min_lot_substitutions += 1
            self.pending[trade_id] = PendingRuntime(
                trade_id,
                event.symbol,
                event.cluster,
                event.side,
                event.price,
                event.stop_distance,
                decision.volume,
                decision.actual_risk_cash,
            )
            self.counters.pending_admitted += 1
            self.counters.max_active = max(self.counters.max_active, len(self._all_active()))
            return

        if kind is AccountEventKind.PENDING_CANCEL:
            if trade_id in self.pending:
                self.pending.pop(trade_id)
                self.counters.pending_cancel_source += 1
            elif trade_id in self.suppressed:
                self.suppressed.discard(trade_id)
            else:
                self.counters.ignored_lifecycle += 1
            return

        if trade_id in self.suppressed:
            self.counters.ignored_lifecycle += 1
            if kind is AccountEventKind.FINAL:
                self.suppressed.discard(trade_id)
            return

        if kind is AccountEventKind.ENTRY:
            pending = self.pending.pop(trade_id, None)
            if pending is None:
                self.counters.ignored_lifecycle += 1
                return
            if abs(event.price - pending.intended_entry) > MONEY_EPS:
                raise InputInvariantError(f"{trade_id}: entry price changed after pending placement")
            slip_cash = event.fixed_slippage_r * pending.actual_risk_cash
            self.balance -= slip_cash
            runtime = PositionRuntime(
                trade_id,
                pending.symbol,
                pending.cluster,
                pending.side,
                event.price,
                pending.stop_distance,
                pending.volume,
                pending.volume,
                pending.actual_risk_cash,
                event.price,
                slip_cash,
                ledger_balance_cash=-slip_cash,
            )
            self.positions[trade_id] = runtime
            self.fills_today += 1
            self.trading_days.add(int(self.current_replay_day))
            self.counters.entries += 1
            self.counters.max_active = max(self.counters.max_active, len(self._all_active()))
            return

        runtime = self.positions.get(trade_id)
        if runtime is None:
            self.counters.ignored_lifecycle += 1
            return
        meta = self._meta(runtime.symbol)

        if kind is AccountEventKind.MARK:
            runtime.mark_price = event.price
            return

        if kind is AccountEventKind.SWAP:
            raw = event.swap_cash_per_lot
            if raw > 0.0:
                self.counters.positive_swap_suppressed += 1
                applied = 0.0
            else:
                applied = raw * event.swap_days * event.swap_multiplier * runtime.current_volume
            runtime.accrued_swap_cash += applied
            self.counters.swap_events += 1
            return

        if kind is AccountEventKind.PARTIAL:
            requested_close = 1.0 - event.remaining_fraction
            close_volume = partial_close_volume(runtime.volume, requested_close, meta)
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
                slip_piece = -runtime.fixed_slippage_cash * (close_volume / runtime.volume)
                runtime.classifier_slippage_used += slip_piece
                runtime.deal_cash_by_ea_day[row.ea_day] = (
                    runtime.deal_cash_by_ea_day.get(row.ea_day, 0.0) + cash + slip_piece
                )
                self.balance += cash
                runtime.ledger_balance_cash += cash
                runtime.current_volume -= close_volume
                self.counters.partial_executed += 1
            runtime.mark_price = event.price
            return

        if kind is AccountEventKind.FINAL:
            price_cash = cash_from_price(
                runtime.entry_price,
                event.price,
                runtime.side,
                runtime.current_volume,
                meta,
            )
            final_slip = -runtime.fixed_slippage_cash - runtime.classifier_slippage_used
            final_deal = price_cash + final_slip + runtime.accrued_swap_cash
            runtime.deal_cash_by_ea_day[row.ea_day] = (
                runtime.deal_cash_by_ea_day.get(row.ea_day, 0.0) + final_deal
            )
            self.balance += price_cash + runtime.accrued_swap_cash
            runtime.ledger_balance_cash += price_cash + runtime.accrued_swap_cash
            classifier_cash = runtime.deal_cash_by_ea_day[row.ea_day]
            if classifier_cash < -MONEY_EPS:
                self.consecutive_losses_today += 1
            elif classifier_cash > MONEY_EPS:
                self.consecutive_losses_today = 0
            # Exact zero intentionally leaves the streak unchanged.
            self.positions.pop(trade_id)
            self.counters.completed += 1
            return

        raise InputInvariantError(f"unsupported in-position event: {kind.value}")

    def check_rails(self) -> tuple[PhaseStatus, ResultReason] | None:
        marked = self.marked_equity()
        tested = marked if self.last_event_role == "favorable" else self.equity()
        self.peak_equity = max(self.peak_equity, marked)
        self.min_equity = min(self.min_equity, tested)
        self.max_equity = max(self.max_equity, marked)

        daily_floor = self.day_start_balance - self.config.initial_balance * (
            self.config.firm_daily_loss_pct / 100.0
        )
        static_floor = self.config.initial_balance * (
            1.0 - self.config.firm_static_loss_pct / 100.0
        )
        if tested <= daily_floor + MONEY_EPS:
            return PhaseStatus.FIRM_BREACH, ResultReason.FTMO_DAILY_LOSS
        if tested <= static_floor + MONEY_EPS:
            return PhaseStatus.FIRM_BREACH, ResultReason.FTMO_STATIC_LOSS

        peak_floor = self.peak_equity * (1.0 - self.config.ea_peak_drawdown_pct / 100.0)
        ea_static = self.config.initial_balance * (1.0 - self.config.ea_static_halt_pct / 100.0)
        if tested <= peak_floor + MONEY_EPS:
            return PhaseStatus.HARD_HALT, ResultReason.EA_PEAK_DRAWDOWN
        if tested <= ea_static + MONEY_EPS:
            return PhaseStatus.HARD_HALT, ResultReason.EA_STATIC_FLOOR

        ea_daily_floor = self.ea_day_start_balance * (
            1.0 - self.config.ea_daily_halt_pct / 100.0
        )
        if not self.daily_halted and tested <= ea_daily_floor + MONEY_EPS:
            self.daily_halted = True
            self.counters.daily_halts += 1
            self._cancel_all_pending("daily_halt")
        return None

    def refresh_target_freeze(self, time_key: tuple[int, int]) -> None:
        if (
            not self.target_frozen
            and self.balance + MONEY_EPS >= self.target_balance
            and len(self.trading_days) >= self.config.minimum_trading_days
        ):
            self.target_frozen = True
            self.target_freeze_time = time_key

    def can_pass(self) -> bool:
        return (
            not self.positions
            and not self.pending
            and self.balance + MONEY_EPS >= self.target_balance
            and len(self.trading_days) >= self.config.minimum_trading_days
        )

    def result(
        self,
        status: PhaseStatus,
        reason: ResultReason,
        *,
        discarded_tail_events: int = 0,
        discarded_raw_active: int = 0,
    ) -> PhaseResult:
        return PhaseResult(
            self.phase,
            status,
            reason,
            self.phase_days,
            len(self.trading_days),
            self.balance,
            self.equity(),
            self.min_equity,
            self.max_equity,
            self.peak_equity,
            replace(self.counters),
            int(discarded_tail_events),
            int(discarded_raw_active),
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


def simulate_two_phase_path(
    tape: PassTape,
    metas: Mapping[str, SymbolMeta],
    policy: RiskPolicy,
    source_indices: Sequence[int],
    *,
    config: SimulationConfig = SimulationConfig(),
    path_id: int = 0,
) -> PathOutcome:
    required = 2 * config.max_calendar_days_per_phase
    if len(source_indices) < required:
        raise InputInvariantError(f"source stream needs at least {required} days")
    cursor = ReplayCursor(tape)
    raw = RawCapacityTracker(config.global_cap, config.cluster_cap)
    account = PhaseAccount(1, policy, metas, config)
    phase1: PhaseResult | None = None
    previous_source: int | None = None

    def terminal_outcome(result: PhaseResult) -> PathOutcome:
        if account.phase == 1:
            return PathOutcome(path_id, policy.name, result, _not_run_phase(2))
        assert phase1 is not None
        return PathOutcome(path_id, policy.name, phase1, result)

    for replay_day, source_value in enumerate(source_indices):
        source_index = int(source_value)
        if not 0 <= source_index < tape.n_days:
            raise InputInvariantError(f"source day out of range: {source_index}")
        if previous_source is not None and source_index != previous_source + 1:
            if (
                raw.active
                or cursor.pending
                or not tape.flat_boundary_at_index(previous_source + 1)
                or not tape.flat_boundary_at_index(source_index)
            ):
                raise BootstrapOverlapError("non-flat lifecycle at sampled block boundary")
        previous_source = source_index

        account.begin_day(replay_day)
        account.advance_time((replay_day, -1))
        terminal = account.check_rails()
        if terminal is not None:
            failed = account.result(*terminal)
            account.end_day()
            return terminal_outcome(failed)
        account.refresh_target_freeze((replay_day, -1))
        if account.can_pass():
            discarded = cursor.discard_pending()
            raw_active = raw.reset_phase_boundary()
            passed = account.result(
                PhaseStatus.PASS,
                ResultReason.TARGET_AND_MIN_DAYS,
                discarded_tail_events=discarded,
                discarded_raw_active=raw_active,
            )
            account.end_day()
            if account.phase == 1:
                phase1 = passed
                account = PhaseAccount(2, policy, metas, config)
                continue
            assert phase1 is not None
            return PathOutcome(path_id, policy.name, phase1, passed)

        rows = cursor.events_for_day(replay_day, source_index)
        transitioned = False
        for pos, row in enumerate(rows):
            account.ensure_ea_day(row.ea_day)
            account.advance_time(row.time_key)
            terminal = account.check_rails()
            if terminal is not None:
                failed = account.result(*terminal)
                account.end_day()
                return terminal_outcome(failed)
            account.refresh_target_freeze(row.time_key)
            if account.can_pass():
                discarded = len(rows) - pos + cursor.discard_pending()
                raw_active = raw.reset_phase_boundary()
                passed = account.result(
                    PhaseStatus.PASS,
                    ResultReason.TARGET_AND_MIN_DAYS,
                    discarded_tail_events=discarded,
                    discarded_raw_active=raw_active,
                )
                account.end_day()
                if account.phase == 1:
                    phase1 = passed
                    account = PhaseAccount(2, policy, metas, config)
                    transitioned = True
                    break
                assert phase1 is not None
                return PathOutcome(path_id, policy.name, phase1, passed)

            raw.process(row)
            account.process(row)
            terminal = account.check_rails()
            if terminal is not None:
                failed = account.result(*terminal)
                account.end_day()
                return terminal_outcome(failed)
            account.refresh_target_freeze(row.time_key)
            if account.can_pass():
                discarded = len(rows) - pos - 1 + cursor.discard_pending()
                raw_active = raw.reset_phase_boundary()
                passed = account.result(
                    PhaseStatus.PASS,
                    ResultReason.TARGET_AND_MIN_DAYS,
                    discarded_tail_events=discarded,
                    discarded_raw_active=raw_active,
                )
                account.end_day()
                if account.phase == 1:
                    phase1 = passed
                    account = PhaseAccount(2, policy, metas, config)
                    transitioned = True
                    break
                assert phase1 is not None
                return PathOutcome(path_id, policy.name, phase1, passed)

        if transitioned:
            continue
        account.end_day()
        if account.phase_days >= config.max_calendar_days_per_phase:
            timeout = account.result(PhaseStatus.TIMEOUT, ResultReason.CALENDAR_CEILING)
            return terminal_outcome(timeout)

    raise InputInvariantError("source stream exhausted unexpectedly")


COUNTER_FIELDS = tuple(AccountCounters.__dataclass_fields__)
RESULT_DTYPE = np.dtype(
    [
        ("path_id", "<i4"),
        ("p1_status", "u1"),
        ("p2_status", "u1"),
        ("p1_reason", "u1"),
        ("p2_reason", "u1"),
        ("both", "u1"),
        ("firm", "u1"),
        ("hard", "u1"),
        ("timeout", "u1"),
        ("p1_days", "<i4"),
        ("p2_days", "<i4"),
        ("total_days", "<i4"),
        ("p1_trading_days", "<i4"),
        ("p2_trading_days", "<i4"),
        ("p1_balance", "<f8"),
        ("p2_balance", "<f8"),
        ("p1_min_equity", "<f8"),
        ("p2_min_equity", "<f8"),
        ("p1_peak_equity", "<f8"),
        ("p2_peak_equity", "<f8"),
    ]
    + [(f"p1_{name}", "<i4") for name in COUNTER_FIELDS]
    + [(f"p2_{name}", "<i4") for name in COUNTER_FIELDS]
)


def _write_outcome(row: np.void, outcome: PathOutcome) -> None:
    p1, p2 = outcome.phase1, outcome.phase2
    row["path_id"] = outcome.path_id
    row["p1_status"] = int(p1.status)
    row["p2_status"] = int(p2.status)
    row["p1_reason"] = int(p1.reason)
    row["p2_reason"] = int(p2.reason)
    row["both"] = int(outcome.both_pass)
    row["firm"] = int(p1.status is PhaseStatus.FIRM_BREACH or p2.status is PhaseStatus.FIRM_BREACH)
    row["hard"] = int(p1.status is PhaseStatus.HARD_HALT or p2.status is PhaseStatus.HARD_HALT)
    row["timeout"] = int(p1.status is PhaseStatus.TIMEOUT or p2.status is PhaseStatus.TIMEOUT)
    row["p1_days"] = p1.calendar_days
    row["p2_days"] = p2.calendar_days
    row["total_days"] = outcome.total_days
    row["p1_trading_days"] = p1.trading_days
    row["p2_trading_days"] = p2.trading_days
    row["p1_balance"] = p1.ending_balance
    row["p2_balance"] = p2.ending_balance
    row["p1_min_equity"] = p1.min_equity
    row["p2_min_equity"] = p2.min_equity
    row["p1_peak_equity"] = p1.peak_equity
    row["p2_peak_equity"] = p2.peak_equity
    for name in COUNTER_FIELDS:
        row[f"p1_{name}"] = getattr(p1.counters, name)
        row[f"p2_{name}"] = getattr(p2.counters, name)


@dataclass(frozen=True)
class MonteCarloSummary:
    paths: int
    phase1_passes: int
    both_passes: int
    phase1_probability: float
    phase2_conditional_probability: float
    both_probability: float
    both_wilson_lower: float
    both_wilson_upper: float
    firm_probability: float
    firm_wilson_upper: float
    hard_probability: float
    hard_wilson_upper: float
    timeout_probability: float
    timeout_wilson_upper: float
    median_total_days_success: float
    p90_total_days_success: float


@dataclass(frozen=True)
class CompactRun:
    policy: RiskPolicy
    rows: np.ndarray

    def normalized_bytes(self) -> bytes:
        header = json.dumps(
            {"policy": self.policy.normalized_dict(), "dtype": self.rows.dtype.descr},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii") + b"\n"
        return header + np.ascontiguousarray(self.rows).tobytes(order="C")

    def sha256(self) -> str:
        return hashlib.sha256(self.normalized_bytes()).hexdigest()

    def summary(self) -> MonteCarloSummary:
        n = len(self.rows)
        if n <= 0:
            raise InputInvariantError("cannot summarize zero paths")
        p1 = self.rows["p1_status"] == int(PhaseStatus.PASS)
        both = self.rows["both"].astype(bool)
        firm = self.rows["firm"].astype(bool)
        hard = self.rows["hard"].astype(bool)
        timeout = self.rows["timeout"].astype(bool)
        p1_n = int(p1.sum())
        both_n = int(both.sum())
        both_lo, both_hi = wilson_one_sided(both_n, n)
        _, firm_hi = wilson_one_sided(int(firm.sum()), n)
        _, hard_hi = wilson_one_sided(int(hard.sum()), n)
        _, timeout_hi = wilson_one_sided(int(timeout.sum()), n)
        successful_days = self.rows["total_days"][both].astype(float)
        if successful_days.size:
            median = float(np.median(successful_days))
            p90 = float(np.quantile(successful_days, 0.90, method="higher"))
        else:
            median = math.nan
            p90 = math.nan
        return MonteCarloSummary(
            n,
            p1_n,
            both_n,
            p1_n / n,
            both_n / p1_n if p1_n else math.nan,
            both_n / n,
            both_lo,
            both_hi,
            float(firm.mean()),
            firm_hi,
            float(hard.mean()),
            hard_hi,
            float(timeout.mean()),
            timeout_hi,
            median,
            p90,
        )

    def paired_delta_lower(
        self,
        control: "CompactRun",
        confidence: float = 0.95,
    ) -> tuple[float, int, int, float, float]:
        if not np.array_equal(self.rows["path_id"], control.rows["path_id"]):
            raise InputInvariantError("paired runs do not share ordered path IDs")
        return exact_paired_delta_lower(
            self.rows["both"].astype(bool).tolist(),
            control.rows["both"].astype(bool).tolist(),
            confidence,
        )


def run_monte_carlo(
    tape: PassTape,
    metas: Mapping[str, SymbolMeta],
    policies: Sequence[RiskPolicy] = POLICIES,
    *,
    paths: int,
    bootstrap: BootstrapSpec = BootstrapSpec(),
    config: SimulationConfig = SimulationConfig(),
) -> dict[str, CompactRun]:
    if paths <= 0 or not policies:
        raise InputInvariantError("Monte Carlo needs positive paths and policies")
    if len({policy.name for policy in policies}) != len(policies):
        raise InputInvariantError("policy names must be unique")
    compiled = CompiledBootstrap.compile(tape, bootstrap)
    arrays = {policy.name: np.zeros(paths, dtype=RESULT_DTYPE) for policy in policies}
    total_days = 2 * config.max_calendar_days_per_phase
    for path_id in range(paths):
        # One stream per path, shared verbatim across every policy (CRN).
        source_indices = compiled.source_indices(path_id, total_days)
        for policy in policies:
            outcome = simulate_two_phase_path(
                tape,
                metas,
                policy,
                source_indices,
                config=config,
                path_id=path_id,
            )
            _write_outcome(arrays[policy.name][path_id], outcome)
    return {policy.name: CompactRun(policy, arrays[policy.name]) for policy in policies}


def _epoch(text: str) -> int:
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def _synthetic_trade(
    prefix: str,
    base_epoch: int,
    *,
    symbol: str = "US30.cash",
    cluster: str = "US",
    sequence: int = 1,
    exit_price: float = 110.0,
    slip_r: float = 0.0,
) -> tuple[AccountEvent, ...]:
    return (
        AccountEvent(
            f"{prefix}:p",
            prefix,
            symbol,
            cluster,
            base_epoch,
            sequence,
            AccountEventKind.PENDING_OPEN,
            1,
            price=100.0,
            stop_distance=10.0,
        ),
        AccountEvent(
            f"{prefix}:e",
            prefix,
            symbol,
            cluster,
            base_epoch + 1,
            sequence + 1,
            AccountEventKind.ENTRY,
            1,
            price=100.0,
            fixed_slippage_r=slip_r,
        ),
        AccountEvent(
            f"{prefix}:f",
            prefix,
            symbol,
            cluster,
            base_epoch + 2,
            sequence + 2,
            AccountEventKind.FINAL,
            1,
            price=exit_price,
            remaining_fraction=0.0,
        ),
    )


def self_test() -> tuple[str, ...]:
    """Run synthetic-only fidelity checks and return stable test names."""

    passed: list[str] = []

    scalar = RiskPolicy("scalar", 0.003, 0.001)
    assert all(scalar.risk_for(1, symbol) == 0.003 for symbol in SYMBOLS)
    assert C0.risk_for(2, "US30.cash") == 0.003
    assert C1.risk_for(2, "JP225.cash") == 0.001
    assert P1.risk_for(1, "US30.cash") == 0.0004
    assert P1.risk_for(2, "US30.cash") == 0.0002
    rejected_map = False
    try:
        RiskPolicy("bad", {"US30.cash": 0.1}, 0.1)
    except InputInvariantError:
        rejected_map = True
    assert rejected_map
    passed.append("complete_symbol_policy_and_scalar_compatibility")

    winter_before, _ = _local_parts(_epoch("2026-01-01T22:59:00Z"), PRAGUE)
    winter_after, _ = _local_parts(_epoch("2026-01-01T23:01:00Z"), PRAGUE)
    summer_before, _ = _local_parts(_epoch("2026-07-01T21:59:00Z"), PRAGUE)
    summer_after, _ = _local_parts(_epoch("2026-07-01T22:01:00Z"), PRAGUE)
    fold_a = _local_parts(_epoch("2026-10-25T00:30:00Z"), PRAGUE)
    fold_b = _local_parts(_epoch("2026-10-25T01:30:00Z"), PRAGUE)
    assert winter_before != winter_after and summer_before != summer_after
    assert fold_a[0] == fold_b[0] and fold_b[1] - fold_a[1] == 3600
    passed.append("prague_dst_and_fold")

    synthetic_metas = {
        symbol: SymbolMeta(symbol, 1.0, 10.0, 12.0, 0.1, 0.1, 100.0)
        for symbol in SYMBOLS
    }
    benign = SimulationConfig(
        initial_balance=100.0,
        phase1_target_pct=90.0,
        phase2_target_pct=90.0,
        firm_daily_loss_pct=99.0,
        firm_static_loss_pct=99.0,
        minimum_trading_days=1,
        max_calendar_days_per_phase=20,
        ea_daily_halt_pct=99.0,
        ea_peak_drawdown_pct=99.0,
        ea_static_halt_pct=99.0,
        equity_mode=EquityMode.MARKS,
    )
    # 31% avoids the intentional raw-MathFloor 0.3/0.1 binary edge and yields
    # an exact synthetic 0.3-lot position.
    policy = RiskPolicy("cash", 0.31, 0.31)
    account = PhaseAccount(1, policy, synthetic_metas, benign)
    account.begin_day(0)
    account.ensure_ea_day(0)
    base = _epoch("2026-01-05T10:00:00Z")
    events = [
        AccountEvent("p", "t", "US30.cash", "US", base, 1,
                     AccountEventKind.PENDING_OPEN, 1, 100.0, 10.0),
        AccountEvent("e", "t", "US30.cash", "US", base + 1, 2,
                     AccountEventKind.ENTRY, 1, 100.0, fixed_slippage_r=0.02),
        AccountEvent("x", "t", "US30.cash", "US", base + 2, 3,
                     AccountEventKind.PARTIAL, 1, 110.0, remaining_fraction=0.5,
                     mark_role="favorable"),
        AccountEvent("s", "t", "US30.cash", "US", base + 3, 4,
                     AccountEventKind.SWAP, 1, swap_cash_per_lot=-2.0),
        AccountEvent("f", "t", "US30.cash", "US", base + 86400, 5,
                     AccountEventKind.FINAL, 1, 80.0, remaining_fraction=0.0),
    ]
    for idx, event in enumerate(events):
        ea_day = 0 if idx < 4 else 1
        account.ensure_ea_day(ea_day)
        account.process(ReplayEvent(0, ea_day, idx, 0, 0, "rt", f"r{idx}", event))
    # 0.3 lot, 0.6 entry slip; 0.1 partial profit=12; remaining 0.2
    # final loss=-40 and accrued swap=-0.4 => closed balance 71 exactly.
    assert abs(account.balance - 71.0) < 1e-9
    assert account.consecutive_losses_today == 1
    assert account.counters.partial_executed == 1 and account.counters.swap_events == 1
    passed.append("entry_slip_actual_partial_swap_realization_and_cross_day_classifier")

    triple = PhaseAccount(1, policy, synthetic_metas, benign)
    triple.begin_day(0)
    triple.ensure_ea_day(0)
    for idx, event in enumerate(events[:2]):
        triple.process(ReplayEvent(0, 0, idx, 0, 0, "rt2", f"q{idx}", event))
    swap3 = AccountEvent("s3", "t", "US30.cash", "US", base + 3, 4,
                         AccountEventKind.SWAP, 1, swap_cash_per_lot=-2.0,
                         swap_days=3, swap_multiplier=2.0)
    triple.process(ReplayEvent(0, 0, 2, 0, 0, "rt2", "q2", swap3))
    assert abs(triple.positions["rt2"].accrued_swap_cash - (-3.6)) < 1e-9
    positive = replace(swap3, event_id="sp", swap_cash_per_lot=2.0)
    triple.process(ReplayEvent(0, 0, 3, 0, 0, "rt2", "q3", positive))
    assert abs(triple.positions["rt2"].accrued_swap_cash - (-3.6)) < 1e-9
    assert triple.counters.positive_swap_suppressed == 1
    passed.append("friday_triple_stress_and_positive_swap_suppression")

    # Target freeze does not cancel an already-prioritized same-time pending;
    # it cancels at the first later modeled management time.
    freeze = PhaseAccount(1, RiskPolicy("freeze", 0.10, 0.10), synthetic_metas,
                          replace(benign, phase1_target_pct=10.0))
    freeze.begin_day(0)
    freeze.ensure_ea_day(0)
    first = _synthetic_trade("winner", base, exit_price=110.0)
    other = AccountEvent("op", "other", "JP225.cash", "JP", base + 1, 99,
                         AccountEventKind.PENDING_OPEN, 1, 100.0, 10.0)
    freeze.process(ReplayEvent(0, 0, 0, 0, 0, "winner", "w0", first[0]))
    freeze.process(ReplayEvent(0, 0, 1, 0, 0, "winner", "w1", first[1]))
    freeze.process(ReplayEvent(0, 0, 1, 0, 0, "other", "o0", other))
    freeze.process(ReplayEvent(0, 0, 2, 0, 0, "winner", "w2", first[2]))
    freeze.refresh_target_freeze((0, 2))
    assert freeze.target_frozen and freeze.pending and not freeze.can_pass()
    freeze.advance_time((0, 2))
    assert freeze.pending
    freeze.advance_time((0, 3))
    assert not freeze.pending and freeze.can_pass()
    passed.append("pending_aware_target_freeze_cancel_and_pass")

    # Explicit zero days and a pending that crosses midnight constrain blocks.
    cross_base = _epoch("2026-01-05T22:30:00Z")
    pending_tape = PassTape.from_events(
        (
            AccountEvent("cp", "cross", "US30.cash", "US", cross_base, 1,
                         AccountEventKind.PENDING_OPEN, 1, 100.0, 10.0),
            AccountEvent("cc", "cross", "US30.cash", "US", cross_base + 7200, 2,
                         AccountEventKind.PENDING_CANCEL, 1),
        ),
        first_day="2026-01-05",
        last_day="2026-01-08",
    )
    assert not pending_tape.flat_boundary_at_index(1)
    starts = pending_tape.eligible_flat_block_starts(2)
    compiled = CompiledBootstrap.compile(
        pending_tape,
        BootstrapSpec(seed=7, block_length=2, eligible_block_starts=starts),
    )
    assert np.array_equal(compiled.source_indices(4, 8), compiled.source_indices(4, 8))
    passed.append("pending_flat_boundary_cached_mbb_crn")

    # Repeated one-day +1R trades cross both targets only after four days.
    win_events = _synthetic_trade("daily", _epoch("2026-02-02T10:00:00Z"))
    win_tape = PassTape.from_events(
        win_events,
        first_day="2026-02-02",
        last_day="2026-02-02",
    )
    small_metas = {
        symbol: SymbolMeta(symbol, 1.0, 1.0, 1.0, 0.01, 0.01, 100.0)
        for symbol in SYMBOLS
    }
    phase_config = SimulationConfig(
        initial_balance=100.0,
        minimum_trading_days=4,
        max_calendar_days_per_phase=5,
        equity_mode=EquityMode.MARKS,
    )
    phase_policy = RiskPolicy("phase", 0.03, 0.03)
    outcome = simulate_two_phase_path(
        win_tape,
        small_metas,
        phase_policy,
        np.zeros(10, dtype="<i4"),
        config=phase_config,
        path_id=3,
    )
    assert outcome.both_pass and outcome.phase1.calendar_days == 4
    assert outcome.phase2.calendar_days == 4 and outcome.total_days == 8
    passed.append("sequential_phases_min_days_next_day_same_stream")

    bootstrap = BootstrapSpec(seed=9, block_length=1, eligible_block_starts=(0,))
    run1 = run_monte_carlo(
        win_tape,
        small_metas,
        (phase_policy,),
        paths=3,
        bootstrap=bootstrap,
        config=phase_config,
    )[phase_policy.name]
    run2 = run_monte_carlo(
        win_tape,
        small_metas,
        (phase_policy,),
        paths=3,
        bootstrap=bootstrap,
        config=phase_config,
    )[phase_policy.name]
    assert run1.normalized_bytes() == run2.normalized_bytes()
    assert run1.sha256() == run2.sha256()
    summary = run1.summary()
    assert summary.both_passes == 3 and summary.p90_total_days_success == 8.0
    lo, hi = wilson_one_sided(88_000, 100_000)
    assert lo < 0.88 < hi
    paired = run1.paired_delta_lower(run2)
    assert paired[1:3] == (0, 0) and paired[0] < 0.0
    passed.append("compact_determinism_wilson_and_paired_bounds")

    return tuple(passed)


if __name__ == "__main__":
    names = self_test()
    print(f"v130 pass-policy synthetic tests: {len(names)} passed")
    for name in names:
        print(name)
