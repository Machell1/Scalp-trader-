"""Lossless pending-aware adapter for the v1.30 FTMO pass-policy simulator.

This module is deliberately an adapter, not an outcome runner.  It consumes an
already materialised :class:`v130_cost_ledger.CostCoupledTape` plus its
``FrozenInputs``-like metadata object.  Importing it performs no file, terminal,
or market-data access; :func:`self_test` uses only hand-built synthetic rows.

The cost-ledger tape conservatively debits fixed slippage at entry for account
equity while the deployed EA classifies a completed position from exit-deal
cashflows.  It also books accumulated swap in the final source event even
though account equity incurs swap at each broker rollover.  The adapter keeps
those views separate:

``balance_r``
    Executable account cashflow.  Fixed slippage is an entry debit and each
    swap definition becomes an event at its actual Helsinki-midnight epoch.

``classifier_r``
    EA loss-streak deal cashflow.  Fixed slippage is allocated pro rata to the
    partial/final exits and accumulated swap remains attached to the final
    deal.  A consumer can therefore reproduce the EA's final-day truncation by
    summing partial/final classifier rows on the final Europe/Helsinki day.

Every lifecycle is owned by the Prague date of *pending placement*, not entry.
This retains unfilled pending occupancy and makes moving-block boundaries
honest: a boundary is eligible only when no pending or position interval spans
it.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo


PRAGUE = ZoneInfo("Europe/Prague")
EA_SERVER = ZoneInfo("Europe/Helsinki")
BLOCK_LENGTH = 20
FLOAT_TOL = 1e-12

PRESERVED_KINDS = frozenset(
    {
        "pending_placement",
        "pending_cancellation",
        "entry_fill",
        "bar_mark",
        "partial_fill",
        "final_exit",
    }
)
TERMINAL_KINDS = frozenset({"pending_cancellation", "final_exit"})


class AdapterInvariantError(RuntimeError):
    """Raised when an in-memory source tape cannot be adapted losslessly."""


def _finite(value: Any, label: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise AdapterInvariantError(f"{label}: expected a finite number") from exc
    if not math.isfinite(out):
        raise AdapterInvariantError(f"{label}: expected a finite number")
    return out


def _close(left: Any, right: Any, label: str, *, atol: float = FLOAT_TOL) -> None:
    a = _finite(left, f"{label}/left")
    b = _finite(right, f"{label}/right")
    if not math.isclose(a, b, rel_tol=0.0, abs_tol=atol):
        raise AdapterInvariantError(f"{label}: {a!r} != {b!r}")


def _local_day(epoch: int, zone: ZoneInfo) -> date:
    return datetime.fromtimestamp(int(epoch), timezone.utc).astimezone(zone).date()


def _local_midnight_epoch(day: date, zone: ZoneInfo) -> int:
    return int(datetime.combine(day, time.min, zone).timestamp())


def _primitive(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return _primitive(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_primitive(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AdapterInvariantError("normalised payload contains a non-finite float")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise AdapterInvariantError(f"unsupported normalised value: {type(value).__name__}")


def _normalized_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _primitive(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def _import_policy_module() -> Any:
    """Import the sibling policy engine in script or package mode."""

    try:
        return importlib.import_module("v130_pass_policy")
    except ModuleNotFoundError as direct:
        if not __package__:
            raise
        try:
            return importlib.import_module(".v130_pass_policy", package=__package__)
        except ModuleNotFoundError:
            raise direct


def _source_event_bytes(events: Iterable[Mapping[str, Any]]) -> bytes:
    # Exact normalisation used by v130_coupled.normalized_event_bytes.
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


def _diagnostic_bytes(diagnostics: Iterable[Mapping[str, Any]]) -> bytes:
    # Exact normalisation used by v130_cost_ledger._diagnostic_bytes.
    return (
        json.dumps(
            list(diagnostics),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


@dataclass(frozen=True)
class PassSymbolMeta:
    symbol: str
    point: float
    trade_tick_size: float
    trade_tick_value_loss: float
    trade_tick_value_profit: float
    volume_min: float
    volume_step: float
    volume_max: float

    def __post_init__(self) -> None:
        values = (
            self.point,
            self.trade_tick_size,
            self.trade_tick_value_loss,
            self.trade_tick_value_profit,
            self.volume_min,
            self.volume_step,
            self.volume_max,
        )
        if not self.symbol or not all(math.isfinite(x) and x > 0.0 for x in values):
            raise AdapterInvariantError(f"invalid symbol metadata for {self.symbol!r}")
        if self.volume_max + FLOAT_TOL < self.volume_min:
            raise AdapterInvariantError(f"{self.symbol}: volume_max < volume_min")


@dataclass(frozen=True)
class SwapDefinition:
    rollover_epoch: int
    rollover_local: str
    preceding_local_date: str
    triple_multiplier: int
    open_fraction: float
    swap_points: float
    raw_cash_per_lot: float
    full_stop_risk_cash_per_lot: float
    raw_full_position_r: float
    conservative_base_r: float
    applied_r: float
    positive_credit_suppressed: bool

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "SwapDefinition":
        return cls(
            rollover_epoch=int(row["rollover_epoch"]),
            rollover_local=str(row["rollover_local"]),
            preceding_local_date=str(row["preceding_local_date"]),
            triple_multiplier=int(row["triple_multiplier"]),
            open_fraction=_finite(row["open_fraction"], "swap/open_fraction"),
            swap_points=_finite(row["swap_points"], "swap/swap_points"),
            raw_cash_per_lot=_finite(row["raw_cash_per_lot"], "swap/raw_cash_per_lot"),
            full_stop_risk_cash_per_lot=_finite(
                row["full_stop_risk_cash_per_lot"], "swap/full_stop_risk_cash_per_lot"
            ),
            raw_full_position_r=_finite(
                row["raw_full_position_r"], "swap/raw_full_position_r"
            ),
            conservative_base_r=_finite(
                row["conservative_base_r"], "swap/conservative_base_r"
            ),
            applied_r=_finite(row["applied_r"], "swap/applied_r"),
            positive_credit_suppressed=bool(row["positive_credit_suppressed"]),
        )

    def __post_init__(self) -> None:
        if self.triple_multiplier not in (1, 3):
            raise AdapterInvariantError("swap triple multiplier must be 1 or 3")
        if not 0.0 < self.open_fraction <= 1.0 + FLOAT_TOL:
            raise AdapterInvariantError("swap open fraction must be in (0, 1]")
        if self.full_stop_risk_cash_per_lot <= 0.0:
            raise AdapterInvariantError("swap stop-risk cash must be positive")
        # Conservative columns may suppress a positive credit but never add it.
        if self.applied_r > FLOAT_TOL:
            raise AdapterInvariantError("positive swap may not be credited")


@dataclass(frozen=True)
class PassEvent:
    event_id: str
    compiled_sequence: int
    source_sequence: int | None
    kind: str
    trade_key: str
    symbol: str
    cluster: str
    owner_day: str
    epoch: int
    scheduler_epoch: int
    prague_day: str
    ea_day: str
    bar: int | None
    signal_bar: int
    entry_bar: int | None
    exit_bar: int | None
    side: int
    price: float | None
    reason: str
    state_before: str
    state_after: str
    global_before: int
    global_after: int
    cluster_before: int
    cluster_after: int
    signal_atr: float
    stop_distance: float
    remaining_fraction: float
    mark_role: str
    price_r: float
    open_r: float
    balance_r: float
    classifier_r: float
    balance_entry_slippage_r: float
    classifier_slippage_r: float
    balance_swap_r: float
    classifier_swap_r: float
    total_r: float | None
    swap: SwapDefinition | None = None

    def __post_init__(self) -> None:
        if not self.event_id or not self.trade_key or not self.symbol or not self.cluster:
            raise AdapterInvariantError("compiled event identities must be non-empty")
        if self.side not in (-1, 1):
            raise AdapterInvariantError(f"{self.event_id}: side must be +/-1")
        if self.signal_atr <= 0.0 or self.stop_distance <= 0.0:
            raise AdapterInvariantError(f"{self.event_id}: ATR/stop must be positive")
        if not 0.0 - FLOAT_TOL <= self.remaining_fraction <= 1.0 + FLOAT_TOL:
            raise AdapterInvariantError(f"{self.event_id}: invalid remaining fraction")
        numerics = (
            self.signal_atr,
            self.stop_distance,
            self.remaining_fraction,
            self.price_r,
            self.open_r,
            self.balance_r,
            self.classifier_r,
            self.balance_entry_slippage_r,
            self.classifier_slippage_r,
            self.balance_swap_r,
            self.classifier_swap_r,
        )
        if self.price is not None:
            numerics += (self.price,)
        if self.total_r is not None:
            numerics += (self.total_r,)
        if not all(math.isfinite(value) for value in numerics):
            raise AdapterInvariantError(f"{self.event_id}: non-finite numeric field")
        if self.mark_role not in {"neutral", "favorable", "adverse"}:
            raise AdapterInvariantError(f"{self.event_id}: invalid mark role")
        if self.kind == "swap_rollover" and self.swap is None:
            raise AdapterInvariantError(f"{self.event_id}: swap definition missing")
        if self.kind != "swap_rollover" and self.swap is not None:
            raise AdapterInvariantError(f"{self.event_id}: unexpected swap definition")


@dataclass(frozen=True)
class PassLifecycle:
    trade_key: str
    symbol: str
    cluster: str
    side: int
    owner_day: str
    placement_sequence: int
    placement_epoch: int
    end_epoch: int
    completed: bool
    terminal_reason: str
    entry_epoch: int | None
    final_epoch: int | None
    total_r: float | None
    loss_classification_r: float | None
    event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.end_epoch < self.placement_epoch:
            raise AdapterInvariantError(f"{self.trade_key}: lifecycle ends before placement")
        if self.completed != (self.final_epoch is not None):
            raise AdapterInvariantError(f"{self.trade_key}: completed/final mismatch")
        if self.completed and (self.entry_epoch is None or self.total_r is None):
            raise AdapterInvariantError(f"{self.trade_key}: completed lifecycle lacks accounting")


@dataclass(frozen=True)
class OwnerDayGroup:
    source_day: str
    lifecycle_ids: tuple[str, ...]


@dataclass(frozen=True)
class CompiledPassTape:
    split: str
    mode: str
    first_day: str
    last_day: str
    timezone_name: str
    block_length: int
    symbol_meta: tuple[PassSymbolMeta, ...]
    events: tuple[PassEvent, ...]
    lifecycles: tuple[PassLifecycle, ...]
    owner_days: tuple[OwnerDayGroup, ...]
    eligible_block_starts: tuple[int, ...]
    source_event_sha256: str
    source_diagnostics_sha256: str
    metadata_sha256: str
    split_metadata_sha256: str
    pre_account_summary: dict[str, Any]
    compiled_sha256: str

    @property
    def n_days(self) -> int:
        return len(self.owner_days)

    def _payload(self) -> dict[str, Any]:
        return {
            "split": self.split,
            "mode": self.mode,
            "first_day": self.first_day,
            "last_day": self.last_day,
            "timezone_name": self.timezone_name,
            "block_length": self.block_length,
            "symbol_meta": self.symbol_meta,
            "events": self.events,
            "lifecycles": self.lifecycles,
            "owner_days": self.owner_days,
            "eligible_block_starts": self.eligible_block_starts,
            "source_event_sha256": self.source_event_sha256,
            "source_diagnostics_sha256": self.source_diagnostics_sha256,
            "metadata_sha256": self.metadata_sha256,
            "split_metadata_sha256": self.split_metadata_sha256,
            "pre_account_summary": self.pre_account_summary,
        }

    def normalized_bytes(self) -> bytes:
        return _normalized_bytes(self._payload())

    def as_policy_mapping(self) -> dict[str, Any]:
        """Return a JSON-safe, hash-bearing input for a policy implementation."""

        payload = _primitive(self._payload())
        payload["compiled_sha256"] = self.compiled_sha256
        return payload

    def to_policy_tape(self) -> Any:
        """Convert directly to :class:`v130_pass_policy.PassTape`.

        The import stays inside the method so this module remains independently
        importable and cannot create a module-level cycle.  A fallback adapter
        protocol is retained for a future compatible policy implementation.
        """

        try:
            module = _import_policy_module()
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "v130_pass_policy is not available; use as_policy_mapping() or "
                "implement from_adapter(compiled_tape)"
            ) from exc
        pass_tape_type = getattr(module, "PassTape", None)
        account_event_type = getattr(module, "AccountEvent", None)
        event_kind_type = getattr(module, "AccountEventKind", None)
        if pass_tape_type is not None and account_event_type is not None and event_kind_type is not None:
            kind_map = {
                "pending_placement": event_kind_type.PENDING_OPEN,
                "pending_cancellation": event_kind_type.PENDING_CANCEL,
                "entry_fill": event_kind_type.ENTRY,
                "bar_mark": event_kind_type.MARK,
                "swap_rollover": event_kind_type.SWAP,
                "partial_fill": event_kind_type.PARTIAL,
                "final_exit": event_kind_type.FINAL,
            }
            mode_swap_multiplier = {"E1_MEASURED": 1.0, "E2_STRESS": 2.0}
            policy_events = []
            for event in self.events:
                try:
                    kind = kind_map[event.kind]
                except KeyError as exc:  # pragma: no cover - PassEvent validates the set.
                    raise RuntimeError(f"unsupported compiled event kind: {event.kind}") from exc
                swap_cash = 0.0
                swap_days = 1
                swap_multiplier = 1.0
                if event.swap is not None:
                    swap_cash = event.swap.raw_cash_per_lot
                    swap_days = event.swap.triple_multiplier
                    swap_multiplier = mode_swap_multiplier[self.mode]
                fixed_slippage = (
                    -event.balance_entry_slippage_r if event.kind == "entry_fill" else 0.0
                )
                if fixed_slippage < -FLOAT_TOL:
                    raise AdapterInvariantError(
                        f"{event.event_id}: entry slippage sign cannot convert to policy input"
                    )
                policy_events.append(
                    account_event_type(
                        event_id=event.event_id,
                        trade_id=event.trade_key,
                        symbol=event.symbol,
                        cluster=event.cluster,
                        epoch=event.epoch,
                        sequence=event.compiled_sequence,
                        kind=kind,
                        side=event.side,
                        price=0.0 if event.price is None else event.price,
                        stop_distance=event.stop_distance,
                        fixed_slippage_r=max(0.0, fixed_slippage),
                        remaining_fraction=event.remaining_fraction,
                        swap_cash_per_lot=swap_cash,
                        swap_days=swap_days,
                        swap_multiplier=swap_multiplier,
                        mark_role=event.mark_role,
                    )
                )
            converted = pass_tape_type.from_events(
                policy_events,
                first_day=self.first_day,
                last_day=self.last_day,
            )
            if converted.eligible_flat_block_starts(self.block_length) != self.eligible_block_starts:
                raise AdapterInvariantError(
                    "v130_pass_policy block eligibility differs from adapter"
                )
            return converted
        for name in ("from_adapter", "compile_from_adapter"):
            converter = getattr(module, name, None)
            if callable(converter):
                return converter(self)
        for name in ("PolicyTape", "CompiledPolicyTape"):
            policy_type = getattr(module, name, None)
            converter = getattr(policy_type, "from_adapter", None)
            if callable(converter):
                return converter(self)
        raise RuntimeError("v130_pass_policy does not expose an adapter conversion API")

    def to_policy_symbol_meta(self) -> dict[str, Any]:
        """Convert broker metadata to the account engine's ``SymbolMeta`` map."""

        try:
            module = _import_policy_module()
        except ModuleNotFoundError as exc:
            raise RuntimeError("v130_pass_policy is not available") from exc
        symbol_meta_type = getattr(module, "SymbolMeta", None)
        if symbol_meta_type is None:
            raise RuntimeError("v130_pass_policy does not expose SymbolMeta")
        return {
            row.symbol: symbol_meta_type(
                symbol=row.symbol,
                trade_tick_size=row.trade_tick_size,
                trade_tick_value_loss=row.trade_tick_value_loss,
                trade_tick_value_profit=row.trade_tick_value_profit,
                volume_min=row.volume_min,
                volume_step=row.volume_step,
                volume_max=row.volume_max,
            )
            for row in self.symbol_meta
        }

    def to_policy_inputs(self) -> tuple[Any, dict[str, Any]]:
        """Return ``(PassTape, SymbolMeta map)`` for ``v130_pass_policy``."""

        return self.to_policy_tape(), self.to_policy_symbol_meta()

    def flat_boundary_at_index(self, boundary_index: int) -> bool:
        if not 0 <= boundary_index <= self.n_days:
            raise AdapterInvariantError("calendar boundary index out of range")
        boundary_day = date.fromisoformat(self.first_day) + timedelta(days=boundary_index)
        boundary_epoch = _local_midnight_epoch(boundary_day, PRAGUE)
        return not any(
            lifecycle.placement_epoch < boundary_epoch < lifecycle.end_epoch
            for lifecycle in self.lifecycles
        )

    def recompute_eligible_block_starts(self, block_length: int | None = None) -> tuple[int, ...]:
        length = self.block_length if block_length is None else int(block_length)
        if length <= 0 or length > self.n_days:
            raise AdapterInvariantError("invalid moving-block length")
        return tuple(
            start
            for start in range(0, self.n_days - length + 1)
            if self.flat_boundary_at_index(start)
            and self.flat_boundary_at_index(start + length)
        )


@dataclass(frozen=True)
class _LifecycleDraft:
    lifecycle: PassLifecycle
    events: tuple[PassEvent, ...]


def _metadata_rows(inputs: Any) -> tuple[PassSymbolMeta, ...]:
    try:
        raw = inputs.metadata["symbols"]
    except (AttributeError, KeyError, TypeError) as exc:
        raise AdapterInvariantError("inputs.metadata['symbols'] is required") from exc
    names = tuple(str(symbol.name) for symbol in inputs.symbols)
    if len(set(names)) != len(names):
        raise AdapterInvariantError("duplicate input symbol names")
    rows: list[PassSymbolMeta] = []
    for name in names:
        try:
            item = raw[name]
        except (KeyError, TypeError) as exc:
            raise AdapterInvariantError(f"missing broker metadata for {name}") from exc
        rows.append(
            PassSymbolMeta(
                symbol=name,
                point=_finite(item["point"], f"{name}/point"),
                trade_tick_size=_finite(
                    item["trade_tick_size"], f"{name}/trade_tick_size"
                ),
                trade_tick_value_loss=_finite(
                    item["trade_tick_value_loss"], f"{name}/trade_tick_value_loss"
                ),
                trade_tick_value_profit=_finite(
                    item["trade_tick_value_profit"], f"{name}/trade_tick_value_profit"
                ),
                volume_min=_finite(item["volume_min"], f"{name}/volume_min"),
                volume_step=_finite(item["volume_step"], f"{name}/volume_step"),
                volume_max=_finite(item["volume_max"], f"{name}/volume_max"),
            )
        )
    return tuple(sorted(rows, key=lambda row: row.symbol))


def _source_hashes(inputs: Any, tape: Any) -> tuple[str, str, str, str]:
    event_hash = hashlib.sha256(_source_event_bytes(tape.events)).hexdigest()
    diagnostic_hash = hashlib.sha256(_diagnostic_bytes(tape.diagnostics)).hexdigest()
    if event_hash != str(tape.normalized_sha256):
        raise AdapterInvariantError("source event SHA256 does not match CostCoupledTape")
    if diagnostic_hash != str(tape.diagnostics_sha256):
        raise AdapterInvariantError("source diagnostic SHA256 does not match CostCoupledTape")
    metadata_hash = hashlib.sha256(_normalized_bytes(inputs.metadata)).hexdigest()
    split_metadata = getattr(inputs, "split_metadata", {})
    split_metadata_hash = hashlib.sha256(_normalized_bytes(split_metadata)).hexdigest()
    return event_hash, diagnostic_hash, metadata_hash, split_metadata_hash


def _source_field(row: Mapping[str, Any], name: str, default: Any = None) -> Any:
    return row[name] if name in row else default


def _state_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "state_before": str(_source_field(row, "state_before", "unknown")),
        "state_after": str(_source_field(row, "state_after", "unknown")),
        "global_before": int(_source_field(row, "global_before", 0)),
        "global_after": int(_source_field(row, "global_after", 0)),
        "cluster_before": int(_source_field(row, "cluster_before", 0)),
        "cluster_after": int(_source_field(row, "cluster_after", 0)),
    }


def _draft_event(
    row: Mapping[str, Any],
    *,
    event_id: str,
    owner_day: date,
    cluster: str,
    signal_atr: float,
    stop_distance: float,
    remaining_fraction: float,
    mark_role: str = "neutral",
    price_r: float = 0.0,
    open_r: float = 0.0,
    balance_r: float = 0.0,
    classifier_r: float = 0.0,
    balance_entry_slippage_r: float = 0.0,
    classifier_slippage_r: float = 0.0,
    balance_swap_r: float = 0.0,
    classifier_swap_r: float = 0.0,
    total_r: float | None = None,
) -> PassEvent:
    epoch = int(row["epoch"])
    price_value = _source_field(row, "price")
    return PassEvent(
        event_id=event_id,
        compiled_sequence=0,
        source_sequence=int(row["sequence"]),
        kind=str(row["kind"]),
        trade_key=str(row["trade_key"]),
        symbol=str(row["symbol"]),
        cluster=cluster,
        owner_day=owner_day.isoformat(),
        epoch=epoch,
        scheduler_epoch=int(_source_field(row, "scheduler_epoch", epoch)),
        prague_day=_local_day(epoch, PRAGUE).isoformat(),
        ea_day=_local_day(epoch, EA_SERVER).isoformat(),
        bar=None if _source_field(row, "bar") is None else int(row["bar"]),
        signal_bar=int(row["signal_bar"]),
        entry_bar=None
        if _source_field(row, "entry_bar") is None
        else int(row["entry_bar"]),
        exit_bar=None
        if _source_field(row, "exit_bar") is None
        else int(row["exit_bar"]),
        side=int(row["side"]),
        price=None if price_value is None else _finite(price_value, f"{event_id}/price"),
        reason=str(_source_field(row, "reason", "")),
        signal_atr=signal_atr,
        stop_distance=stop_distance,
        remaining_fraction=remaining_fraction,
        mark_role=mark_role,
        price_r=price_r,
        open_r=open_r,
        balance_r=balance_r,
        classifier_r=classifier_r,
        balance_entry_slippage_r=balance_entry_slippage_r,
        classifier_slippage_r=classifier_slippage_r,
        balance_swap_r=balance_swap_r,
        classifier_swap_r=classifier_swap_r,
        total_r=total_r,
        swap=None,
        **_state_fields(row),
    )


def _compile_lifecycle(
    key: str,
    rows: list[Mapping[str, Any]],
    diagnostic: Mapping[str, Any] | None,
    symbol_objects: Mapping[str, Any],
    clusters: Mapping[str, str],
    mode: str,
) -> _LifecycleDraft:
    rows = sorted(rows, key=lambda row: int(row["sequence"]))
    sequences = [int(row["sequence"]) for row in rows]
    if len(set(sequences)) != len(sequences):
        raise AdapterInvariantError(f"{key}: duplicate source sequence")
    placements = [row for row in rows if row["kind"] == "pending_placement"]
    entries = [row for row in rows if row["kind"] == "entry_fill"]
    partials = [row for row in rows if row["kind"] == "partial_fill"]
    finals = [row for row in rows if row["kind"] == "final_exit"]
    cancellations = [row for row in rows if row["kind"] == "pending_cancellation"]
    if len(placements) != 1:
        raise AdapterInvariantError(f"{key}: require exactly one pending placement")
    completed = bool(finals)
    if completed:
        if len(entries) != 1 or len(finals) != 1 or cancellations or len(partials) > 1:
            raise AdapterInvariantError(
                f"{key}: completed lifecycle requires one entry/final, <=1 partial, no cancel"
            )
        if diagnostic is None:
            raise AdapterInvariantError(f"{key}: completed lifecycle lacks diagnostic")
    else:
        if len(cancellations) != 1 or entries or partials or finals or diagnostic is not None:
            raise AdapterInvariantError(
                f"{key}: unfilled lifecycle requires one cancellation and no diagnostic"
            )

    placement = placements[0]
    symbol = str(placement["symbol"])
    side = int(placement["side"])
    if side not in (-1, 1):
        raise AdapterInvariantError(f"{key}: invalid side")
    if any(str(row["symbol"]) != symbol or int(row["side"]) != side for row in rows):
        raise AdapterInvariantError(f"{key}: symbol/side changes inside lifecycle")
    try:
        symbol_object = symbol_objects[symbol]
        cluster = clusters[symbol]
    except KeyError as exc:
        raise AdapterInvariantError(f"{key}: symbol absent from inputs") from exc
    signal_bar = int(placement["signal_bar"])
    try:
        signal_atr = _finite(symbol_object.atr[signal_bar], f"{key}/signal_atr")
    except (IndexError, TypeError) as exc:
        raise AdapterInvariantError(f"{key}: signal bar outside ATR array") from exc
    if signal_atr <= 0.0:
        raise AdapterInvariantError(f"{key}: nonpositive signal ATR")
    stop_distance = signal_atr  # v1.30 STOP_ATR is frozen at 1.0.
    owner_day = _local_day(int(placement["epoch"]), PRAGUE)
    drafts: list[PassEvent] = []

    if not completed:
        for row in rows:
            event_id = f"{key}:src:{int(row['sequence'])}:{row['kind']}"
            drafts.append(
                _draft_event(
                    row,
                    event_id=event_id,
                    owner_day=owner_day,
                    cluster=cluster,
                    signal_atr=signal_atr,
                    stop_distance=stop_distance,
                    remaining_fraction=0.0,
                )
            )
        cancellation = cancellations[0]
        lifecycle = PassLifecycle(
            trade_key=key,
            symbol=symbol,
            cluster=cluster,
            side=side,
            owner_day=owner_day.isoformat(),
            placement_sequence=int(placement["sequence"]),
            placement_epoch=int(placement["epoch"]),
            end_epoch=int(cancellation["epoch"]),
            completed=False,
            terminal_reason=str(_source_field(cancellation, "reason", "")),
            entry_epoch=None,
            final_epoch=None,
            total_r=None,
            loss_classification_r=None,
            event_ids=tuple(event.event_id for event in drafts),
        )
        return _LifecycleDraft(lifecycle, tuple(drafts))

    assert diagnostic is not None
    if str(diagnostic["trade_key"]) != key or str(diagnostic["symbol"]) != symbol:
        raise AdapterInvariantError(f"{key}: diagnostic identity mismatch")
    if str(diagnostic["mode"]) != mode or int(diagnostic["side"]) != side:
        raise AdapterInvariantError(f"{key}: diagnostic mode/side mismatch")
    if int(diagnostic["signal_bar"]) != signal_bar:
        raise AdapterInvariantError(f"{key}: diagnostic signal-bar mismatch")
    entry = entries[0]
    final = finals[0]
    entry_price = _finite(entry["price"], f"{key}/entry_price")
    final_price = _finite(final["price"], f"{key}/final_price")
    frozen_risk = _finite(diagnostic["frozen_risk"], f"{key}/frozen_risk")
    _close(frozen_risk, stop_distance, f"{key}/risk")
    _close(entry_price, diagnostic["entry_price"], f"{key}/entry_price")
    _close(final_price, diagnostic["exit_price"], f"{key}/exit_price")
    if int(diagnostic["entry_bar"]) != int(entry["bar"]):
        raise AdapterInvariantError(f"{key}: entry-bar mismatch")
    if int(diagnostic["exit_bar"]) != int(final["bar"]):
        raise AdapterInvariantError(f"{key}: exit-bar mismatch")
    if int(diagnostic["final_event_epoch"]) != int(final["epoch"]):
        raise AdapterInvariantError(f"{key}: final-epoch mismatch")
    if bool(diagnostic["partial"]) != bool(partials):
        raise AdapterInvariantError(f"{key}: partial-state mismatch")

    fixed_slippage = _finite(diagnostic["fixed_slippage_r"], f"{key}/fixed_slippage")
    partial_slippage = _finite(
        diagnostic["partial_slippage_debit_r"], f"{key}/partial_slippage"
    )
    final_slippage = _finite(
        diagnostic["final_slippage_debit_r"], f"{key}/final_slippage"
    )
    swap_total = _finite(diagnostic["swap_r"], f"{key}/swap_total")
    total_r = _finite(diagnostic["total_r"], f"{key}/total_r")
    final_price_r = _finite(diagnostic["final_price_r"], f"{key}/final_price_r")
    banked_partial_r = _finite(
        diagnostic["banked_partial_r"], f"{key}/banked_partial_r"
    )
    final_classifier = final_price_r + final_slippage + swap_total
    _close(
        -fixed_slippage,
        _source_field(entry, "r_component"),
        f"{key}/source_entry_slippage",
    )
    _close(
        final_price_r + swap_total,
        _source_field(final, "r_component"),
        f"{key}/source_final_component",
    )
    _close(total_r, _source_field(final, "total_r"), f"{key}/source_total")
    if partials:
        _close(
            banked_partial_r,
            _source_field(partials[0], "r_component"),
            f"{key}/source_partial_component",
        )
    else:
        _close(banked_partial_r, 0.0, f"{key}/no_partial_component")
    _close(
        total_r,
        -fixed_slippage + banked_partial_r + final_price_r + swap_total,
        f"{key}/diagnostic_total_reconciliation",
    )
    _close(
        -fixed_slippage,
        partial_slippage + final_slippage,
        f"{key}/classifier_slippage_allocation",
    )

    remaining = 0.0
    for row in rows:
        kind = str(row["kind"])
        event_id = f"{key}:src:{int(row['sequence'])}:{kind}"
        kwargs: dict[str, Any] = {}
        if kind == "entry_fill":
            remaining = 1.0
            kwargs.update(
                remaining_fraction=1.0,
                balance_r=-fixed_slippage,
                balance_entry_slippage_r=-fixed_slippage,
                total_r=total_r,
            )
        elif kind == "bar_mark":
            price = _finite(row["price"], f"{event_id}/mark_price")
            price_r = side * (price - entry_price) / frozen_risk
            role = "favorable" if str(_source_field(row, "reason", "")).endswith(
                ":favorable"
            ) else "adverse"
            kwargs.update(
                remaining_fraction=remaining,
                mark_role=role,
                open_r=price_r * remaining,
                total_r=total_r,
            )
        elif kind == "partial_fill":
            remaining = _finite(
                diagnostic["remaining_fraction"], f"{key}/remaining_fraction"
            )
            kwargs.update(
                remaining_fraction=remaining,
                mark_role="favorable",
                price_r=banked_partial_r,
                open_r=(side * (_finite(row["price"], f"{event_id}/price") - entry_price)
                        / frozen_risk * remaining),
                balance_r=banked_partial_r,
                classifier_r=banked_partial_r + partial_slippage,
                classifier_slippage_r=partial_slippage,
                total_r=total_r,
            )
        elif kind == "final_exit":
            remaining = 0.0
            kwargs.update(
                remaining_fraction=0.0,
                price_r=final_price_r,
                balance_r=final_price_r,
                classifier_r=final_classifier,
                classifier_slippage_r=final_slippage,
                classifier_swap_r=swap_total,
                total_r=total_r,
            )
        else:
            kwargs.update(remaining_fraction=remaining, total_r=total_r)
        drafts.append(
            _draft_event(
                row,
                event_id=event_id,
                owner_day=owner_day,
                cluster=cluster,
                signal_atr=signal_atr,
                stop_distance=stop_distance,
                **kwargs,
            )
        )

    swap_definitions = tuple(
        SwapDefinition.from_mapping(row) for row in diagnostic.get("swap_events", ())
    )
    if tuple(sorted(item.rollover_epoch for item in swap_definitions)) != tuple(
        item.rollover_epoch for item in swap_definitions
    ):
        raise AdapterInvariantError(f"{key}: swap definitions are not time ordered")
    _close(sum(item.applied_r for item in swap_definitions), swap_total, f"{key}/swap_sum")
    for index, definition in enumerate(swap_definitions):
        if not int(entry["epoch"]) < definition.rollover_epoch <= int(final["epoch"]):
            raise AdapterInvariantError(f"{key}: swap epoch outside open lifecycle")
        event_id = f"{key}:swap:{definition.rollover_epoch}:{index}"
        drafts.append(
            PassEvent(
                event_id=event_id,
                compiled_sequence=0,
                source_sequence=None,
                kind="swap_rollover",
                trade_key=key,
                symbol=symbol,
                cluster=cluster,
                owner_day=owner_day.isoformat(),
                epoch=definition.rollover_epoch,
                scheduler_epoch=definition.rollover_epoch,
                prague_day=_local_day(definition.rollover_epoch, PRAGUE).isoformat(),
                ea_day=_local_day(definition.rollover_epoch, EA_SERVER).isoformat(),
                bar=None,
                signal_bar=signal_bar,
                entry_bar=int(entry["bar"]),
                exit_bar=None,
                side=side,
                price=None,
                reason="broker_rollover",
                state_before="position",
                state_after="position",
                global_before=int(_source_field(entry, "global_after", 1)),
                global_after=int(_source_field(entry, "global_after", 1)),
                cluster_before=int(_source_field(entry, "cluster_after", 1)),
                cluster_after=int(_source_field(entry, "cluster_after", 1)),
                signal_atr=signal_atr,
                stop_distance=stop_distance,
                remaining_fraction=definition.open_fraction,
                mark_role="adverse" if definition.applied_r < 0.0 else "neutral",
                price_r=0.0,
                open_r=0.0,
                balance_r=definition.applied_r,
                classifier_r=0.0,
                balance_entry_slippage_r=0.0,
                classifier_slippage_r=0.0,
                balance_swap_r=definition.applied_r,
                classifier_swap_r=0.0,
                total_r=total_r,
                swap=definition,
            )
        )

    drafts.sort(key=_event_sort_key)
    balance_total = sum(event.balance_r for event in drafts)
    classifier_total = sum(event.classifier_r for event in drafts)
    _close(balance_total, total_r, f"{key}/compiled_balance_total")
    _close(classifier_total, total_r, f"{key}/compiled_classifier_total")
    final_ea_day = str(diagnostic["final_ea_day"])
    final_day_classifier = sum(
        event.classifier_r
        for event in drafts
        if event.kind in {"partial_fill", "final_exit"} and event.ea_day == final_ea_day
    )
    loss_classification_r = _finite(
        diagnostic["loss_classification_r"], f"{key}/loss_classification_r"
    )
    _close(
        final_day_classifier,
        loss_classification_r,
        f"{key}/final_day_classifier",
    )
    lifecycle = PassLifecycle(
        trade_key=key,
        symbol=symbol,
        cluster=cluster,
        side=side,
        owner_day=owner_day.isoformat(),
        placement_sequence=int(placement["sequence"]),
        placement_epoch=int(placement["epoch"]),
        end_epoch=int(final["epoch"]),
        completed=True,
        terminal_reason=str(_source_field(final, "reason", "")),
        entry_epoch=int(entry["epoch"]),
        final_epoch=int(final["epoch"]),
        total_r=total_r,
        loss_classification_r=loss_classification_r,
        event_ids=tuple(event.event_id for event in drafts),
    )
    return _LifecycleDraft(lifecycle, tuple(drafts))


def _event_sort_key(event: PassEvent) -> tuple[int, int, int, str, str]:
    # Rollover is an account cashflow at the boundary before any same-epoch
    # lifecycle event; final-deal classification still carries its swap copy.
    priority = 0 if event.kind == "swap_rollover" else 1
    source = -1 if event.source_sequence is None else event.source_sequence
    return event.epoch, priority, source, event.trade_key, event.event_id


def _calendar_bounds(inputs: Any, drafts: Iterable[_LifecycleDraft]) -> tuple[date, date]:
    epochs: list[int] = []
    for symbol in inputs.symbols:
        try:
            if len(symbol.ep) == 0:
                raise AdapterInvariantError(f"{symbol.name}: empty epoch array")
            epochs.extend((int(symbol.ep[0]), int(symbol.ep[-1])))
        except (AttributeError, IndexError, TypeError) as exc:
            raise AdapterInvariantError("input symbols require non-empty ep arrays") from exc
    for draft in drafts:
        epochs.extend((draft.lifecycle.placement_epoch, draft.lifecycle.end_epoch))
    if not epochs:
        raise AdapterInvariantError("cannot derive calendar bounds")
    days = tuple(_local_day(epoch, PRAGUE) for epoch in epochs)
    return min(days), max(days)


def _eligible_starts(
    lifecycles: Iterable[PassLifecycle], first_day: date, last_day: date
) -> tuple[int, ...]:
    rows = tuple(lifecycles)
    n_days = (last_day - first_day).days + 1
    if n_days < BLOCK_LENGTH:
        raise AdapterInvariantError("calendar frame is shorter than the 20-day block")

    def flat(index: int) -> bool:
        boundary = _local_midnight_epoch(first_day + timedelta(days=index), PRAGUE)
        return not any(row.placement_epoch < boundary < row.end_epoch for row in rows)

    return tuple(
        start
        for start in range(0, n_days - BLOCK_LENGTH + 1)
        if flat(start) and flat(start + BLOCK_LENGTH)
    )


def _summary(
    events: tuple[PassEvent, ...],
    lifecycles: tuple[PassLifecycle, ...],
    owner_days: tuple[OwnerDayGroup, ...],
    eligible: tuple[int, ...],
    source_event_count: int,
    source_trade_count: int,
) -> dict[str, Any]:
    kinds: dict[str, int] = {}
    for event in events:
        kinds[event.kind] = kinds.get(event.kind, 0) + 1
    completed = tuple(row for row in lifecycles if row.completed)
    per_symbol: dict[str, dict[str, Any]] = {}
    for lifecycle in lifecycles:
        bucket = per_symbol.setdefault(
            lifecycle.symbol,
            {"lifecycles": 0, "completed": 0, "unfilled": 0, "wins": 0, "total_r": 0.0},
        )
        bucket["lifecycles"] += 1
        if lifecycle.completed:
            bucket["completed"] += 1
            assert lifecycle.total_r is not None
            bucket["total_r"] += lifecycle.total_r
            bucket["wins"] += int(lifecycle.total_r > 0.0)
        else:
            bucket["unfilled"] += 1
    wins = sum(int(row.total_r is not None and row.total_r > 0.0) for row in completed)
    total_r = sum(float(row.total_r) for row in completed if row.total_r is not None)
    return {
        "source_events": int(source_event_count),
        "source_completed_trades": int(source_trade_count),
        "preserved_events": len(events),
        "event_kinds": dict(sorted(kinds.items())),
        "lifecycles": len(lifecycles),
        "completed": len(completed),
        "unfilled": len(lifecycles) - len(completed),
        "wins": wins,
        "win_rate": None if not completed else wins / len(completed),
        "total_r": total_r,
        "entry_slippage_r": sum(event.balance_entry_slippage_r for event in events),
        "timed_swap_r": sum(event.balance_swap_r for event in events),
        "owner_days": len(owner_days),
        "nonempty_owner_days": sum(bool(day.lifecycle_ids) for day in owner_days),
        "eligible_20_day_starts": len(eligible),
        "per_symbol": dict(sorted(per_symbol.items())),
    }


def compile_cost_tape(inputs: Any, tape: Any) -> CompiledPassTape:
    """Compile one in-memory E1/E2 cost tape into a pending-aware policy tape."""

    mode = str(tape.mode)
    if mode not in {"E1_MEASURED", "E2_STRESS"}:
        raise AdapterInvariantError(f"pass-policy adapter rejects non-eligibility mode {mode!r}")
    event_hash, diagnostic_hash, metadata_hash, split_metadata_hash = _source_hashes(
        inputs, tape
    )
    meta = _metadata_rows(inputs)
    symbol_objects = {str(symbol.name): symbol for symbol in inputs.symbols}
    raw_meta = inputs.metadata["symbols"]
    clusters: dict[str, str] = {}
    # The causal scheduler freezes US30/US100 together and JP225 separately.
    # A metadata-provided cluster may be used by synthetic callers, but actual
    # trio names retain the registered mapping.
    for name in symbol_objects:
        if name in {"US30.cash", "US100.cash"}:
            clusters[name] = "0"
        elif name == "JP225.cash":
            clusters[name] = "1"
        else:
            clusters[name] = str(raw_meta[name].get("cluster", name))

    source_rows = tuple(dict(row) for row in tape.events)
    source_sequences = [int(row["sequence"]) for row in source_rows]
    if len(set(source_sequences)) != len(source_sequences):
        raise AdapterInvariantError("source tape contains duplicate global sequences")
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in source_rows:
        kind = str(row["kind"])
        if kind not in PRESERVED_KINDS:
            continue
        grouped.setdefault(str(row["trade_key"]), []).append(row)
    if not grouped:
        raise AdapterInvariantError("source tape contains no pending lifecycles")

    diagnostics = tuple(dict(row) for row in tape.diagnostics)
    diagnostic_map: dict[str, Mapping[str, Any]] = {}
    for row in diagnostics:
        key = str(row["trade_key"])
        if key in diagnostic_map:
            raise AdapterInvariantError(f"duplicate diagnostic key: {key}")
        diagnostic_map[key] = row
    completed_keys = {
        key
        for key, rows in grouped.items()
        if any(str(row["kind"]) == "final_exit" for row in rows)
    }
    if completed_keys != set(diagnostic_map):
        missing = sorted(completed_keys - set(diagnostic_map))
        extra = sorted(set(diagnostic_map) - completed_keys)
        raise AdapterInvariantError(
            f"diagnostic join mismatch: missing={missing}, extra={extra}"
        )
    if len(tuple(tape.trades)) != len(completed_keys):
        raise AdapterInvariantError("source trade count and completed lifecycles differ")

    drafts = tuple(
        _compile_lifecycle(
            key,
            grouped[key],
            diagnostic_map.get(key),
            symbol_objects,
            clusters,
            mode,
        )
        for key in sorted(grouped)
    )
    all_events = [event for draft in drafts for event in draft.events]
    event_ids = [event.event_id for event in all_events]
    if len(set(event_ids)) != len(event_ids):
        raise AdapterInvariantError("compiled event IDs are not unique")
    ordered_events = tuple(
        replace(event, compiled_sequence=index)
        for index, event in enumerate(sorted(all_events, key=_event_sort_key), start=1)
    )
    event_by_id = {event.event_id: event for event in ordered_events}
    lifecycles = tuple(
        replace(
            draft.lifecycle,
            event_ids=tuple(
                event.event_id
                for event in sorted(
                    (event_by_id[event_id] for event_id in draft.lifecycle.event_ids),
                    key=_event_sort_key,
                )
            ),
        )
        for draft in sorted(
            drafts,
            key=lambda item: (
                item.lifecycle.placement_epoch,
                item.lifecycle.placement_sequence,
                item.lifecycle.trade_key,
            ),
        )
    )
    first_day, last_day = _calendar_bounds(inputs, drafts)
    by_owner: dict[str, list[PassLifecycle]] = {}
    for lifecycle in lifecycles:
        owner = date.fromisoformat(lifecycle.owner_day)
        if owner < first_day or owner > last_day:
            raise AdapterInvariantError(f"{lifecycle.trade_key}: owner day outside calendar")
        by_owner.setdefault(lifecycle.owner_day, []).append(lifecycle)
    owner_days: list[OwnerDayGroup] = []
    cursor = first_day
    while cursor <= last_day:
        owned = tuple(
            row.trade_key
            for row in sorted(
                by_owner.get(cursor.isoformat(), ()),
                key=lambda row: (row.placement_epoch, row.placement_sequence, row.trade_key),
            )
        )
        owner_days.append(OwnerDayGroup(cursor.isoformat(), owned))
        cursor += timedelta(days=1)
    owner_tuple = tuple(owner_days)
    eligible = _eligible_starts(lifecycles, first_day, last_day)
    summary = _summary(
        ordered_events,
        lifecycles,
        owner_tuple,
        eligible,
        len(source_rows),
        len(tuple(tape.trades)),
    )
    provisional = CompiledPassTape(
        split=str(getattr(inputs, "split", "unknown")),
        mode=mode,
        first_day=first_day.isoformat(),
        last_day=last_day.isoformat(),
        timezone_name="Europe/Prague",
        block_length=BLOCK_LENGTH,
        symbol_meta=meta,
        events=ordered_events,
        lifecycles=lifecycles,
        owner_days=owner_tuple,
        eligible_block_starts=eligible,
        source_event_sha256=event_hash,
        source_diagnostics_sha256=diagnostic_hash,
        metadata_sha256=metadata_hash,
        split_metadata_sha256=split_metadata_hash,
        pre_account_summary=summary,
        compiled_sha256="",
    )
    compiled_hash = hashlib.sha256(provisional.normalized_bytes()).hexdigest()
    compiled = replace(provisional, compiled_sha256=compiled_hash)
    if compiled.recompute_eligible_block_starts() != eligible:
        raise AdapterInvariantError("compiled block eligibility is not self-consistent")
    return compiled


def _epoch(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def _synthetic_source_event(
    sequence: int,
    kind: str,
    key: str,
    epoch: int,
    *,
    price: float | None,
    r_component: float | None,
    total_r: float | None,
    reason: str,
    state_before: str,
    state_after: str,
    global_before: int,
    global_after: int,
    bar: int,
    entry_bar: int | None = None,
    exit_bar: int | None = None,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "kind": kind,
        "trade_key": key,
        "symbol": "SYN",
        "epoch": epoch,
        "scheduler_epoch": epoch,
        "bar": bar,
        "signal_bar": 1,
        "entry_bar": entry_bar,
        "exit_bar": exit_bar,
        "side": 1,
        "price": price,
        "r_component": r_component,
        "total_r": total_r,
        "reason": reason,
        "state_before": state_before,
        "state_after": state_after,
        "global_before": global_before,
        "global_after": global_after,
        "cluster_before": global_before,
        "cluster_after": global_after,
    }


def _synthetic_fixture() -> tuple[Any, Any]:
    key = "SYN:1:1"
    place = _epoch("2026-01-05T22:50:00Z")  # Prague Jan 5 23:50.
    entry = _epoch("2026-01-05T23:15:00Z")  # Prague Jan 6 00:15.
    mark1 = _epoch("2026-01-06T20:00:00Z")
    partial = _epoch("2026-01-06T21:00:00Z")
    rollover = _epoch("2026-01-06T22:00:00Z")  # Helsinki Jan 7 00:00.
    mark2 = _epoch("2026-01-06T23:00:00Z")
    final = _epoch("2026-01-07T00:00:00Z")
    unfilled_key = "SYN:2:-1"
    unfilled_place = _epoch("2026-01-25T22:30:00Z")
    unfilled_cancel = _epoch("2026-01-26T00:00:00Z")
    total_r = 1.45
    events = (
        _synthetic_source_event(
            1,
            "pending_placement",
            key,
            place,
            price=100.0,
            r_component=None,
            total_r=None,
            reason="signal",
            state_before="free",
            state_after="pending",
            global_before=0,
            global_after=1,
            bar=2,
        ),
        _synthetic_source_event(
            2,
            "entry_fill",
            key,
            entry,
            price=100.0,
            r_component=-0.02,
            total_r=total_r,
            reason="limit_fill",
            state_before="pending",
            state_after="position",
            global_before=1,
            global_after=1,
            bar=2,
            entry_bar=2,
        ),
        _synthetic_source_event(
            3,
            "bar_mark",
            key,
            mark1,
            price=112.0,
            r_component=0.0,
            total_r=total_r,
            reason="bar:favorable",
            state_before="position",
            state_after="position",
            global_before=1,
            global_after=1,
            bar=2,
            entry_bar=2,
        ),
        _synthetic_source_event(
            4,
            "partial_fill",
            key,
            partial,
            price=110.0,
            r_component=0.5,
            total_r=total_r,
            reason="partial_1R",
            state_before="position",
            state_after="position",
            global_before=1,
            global_after=1,
            bar=2,
            entry_bar=2,
        ),
        _synthetic_source_event(
            5,
            "bar_mark",
            key,
            mark2,
            price=105.0,
            r_component=0.0,
            total_r=total_r,
            reason="bar:adverse",
            state_before="position",
            state_after="position",
            global_before=1,
            global_after=1,
            bar=3,
            entry_bar=2,
        ),
        _synthetic_source_event(
            6,
            "final_exit",
            key,
            final,
            price=120.0,
            r_component=0.97,
            total_r=total_r,
            reason="TP",
            state_before="position",
            state_after="free",
            global_before=1,
            global_after=0,
            bar=3,
            entry_bar=2,
            exit_bar=3,
        ),
        _synthetic_source_event(
            7,
            "pending_placement",
            unfilled_key,
            unfilled_place,
            price=90.0,
            r_component=None,
            total_r=None,
            reason="signal",
            state_before="free",
            state_after="pending",
            global_before=0,
            global_after=1,
            bar=2,
        ),
        _synthetic_source_event(
            8,
            "pending_cancellation",
            unfilled_key,
            unfilled_cancel,
            price=90.0,
            r_component=None,
            total_r=None,
            reason="unfilled_expiry",
            state_before="pending",
            state_after="free",
            global_before=1,
            global_after=0,
            bar=3,
        ),
    )
    diagnostics = (
        {
            "trade_key": key,
            "geometry_key": key,
            "mode": "E1_MEASURED",
            "symbol": "SYN",
            "signal_bar": 1,
            "signal_epoch": _epoch("2026-01-05T22:45:00Z"),
            "entry_bar": 2,
            "exit_bar": 3,
            "side": 1,
            "reason": "TP",
            "partial": True,
            "entry_price": 100.0,
            "exit_price": 120.0,
            "frozen_risk": 10.0,
            "remaining_fraction": 0.5,
            "base_f2_total_r": 1.0,
            "legacy_median_spread_debit_r": -0.5,
            "legacy_debit_removal_contribution_r": 0.5,
            "legacy_debit_removed_r": 0.5,
            "short_time_exit_correction_r": 0.0,
            "short_time_correction_r": 0.0,
            "banked_partial_r": 0.5,
            "final_price_r": 1.0,
            "e0_price_r": 1.5,
            "fixed_slippage_r": 0.02,
            "slippage_debit_r": -0.02,
            "slippage_r": -0.02,
            "partial_slippage_debit_r": -0.01,
            "final_slippage_debit_r": -0.01,
            "conservative_swap_r": -0.03,
            "swap_r": -0.03,
            "total_r": total_r,
            "final_event_epoch": final,
            "final_ea_day": "2026-01-07",
            "loss_classification_r": 0.96,
            "swap_events": (
                {
                    "rollover_epoch": rollover,
                    "rollover_local": "2026-01-07T00:00:00+02:00",
                    "preceding_local_date": "2026-01-06",
                    "triple_multiplier": 1,
                    "open_fraction": 0.5,
                    "swap_points": -30.0,
                    "raw_cash_per_lot": -3.0,
                    "full_stop_risk_cash_per_lot": 50.0,
                    "raw_full_position_r": -0.06,
                    "conservative_base_r": -0.03,
                    "applied_r": -0.03,
                    "positive_credit_suppressed": False,
                },
            ),
        },
    )
    metadata = {
        "symbols": {
            "SYN": {
                "cluster": "SYN_CLUSTER",
                "point": 0.01,
                "trade_tick_size": 0.01,
                "trade_tick_value_loss": 1.0,
                "trade_tick_value_profit": 1.0,
                "volume_min": 0.01,
                "volume_step": 0.01,
                "volume_max": 100.0,
            }
        }
    }
    symbol = SimpleNamespace(
        name="SYN",
        ep=[_epoch("2026-01-01T00:00:00Z"), place, entry, _epoch("2026-02-20T00:00:00Z")],
        atr=[10.0, 10.0, 10.0, 10.0],
    )
    inputs = SimpleNamespace(
        split="synthetic",
        symbols=(symbol,),
        metadata=metadata,
        split_metadata={"synthetic": True},
    )
    tape = SimpleNamespace(
        mode="E1_MEASURED",
        trades=(SimpleNamespace(sym="SYN", r=total_r),),
        events=events,
        diagnostics=diagnostics,
        normalized_sha256=hashlib.sha256(_source_event_bytes(events)).hexdigest(),
        diagnostics_sha256=hashlib.sha256(_diagnostic_bytes(diagnostics)).hexdigest(),
    )
    return inputs, tape


def self_test() -> dict[str, Any]:
    """Exercise only synthetic pending, cashflow, rollover, and block cases."""

    passed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            raise AssertionError(name)
        passed.append(name)

    inputs, source = _synthetic_fixture()
    compiled = compile_cost_tape(inputs, source)
    check("owner_is_pending_placement_day", compiled.lifecycles[0].owner_day == "2026-01-05")
    check("entry_occurs_next_prague_day", compiled.lifecycles[0].entry_epoch is not None and _local_day(compiled.lifecycles[0].entry_epoch, PRAGUE).isoformat() == "2026-01-06")
    check("unfilled_pending_retained", compiled.pre_account_summary["unfilled"] == 1)
    check("completed_lifecycle_retained", compiled.pre_account_summary["completed"] == 1)
    swap_rows = tuple(event for event in compiled.events if event.kind == "swap_rollover")
    check("actual_timed_swap_inserted_once", len(swap_rows) == 1)
    check("timed_swap_balance_component", abs(swap_rows[0].balance_r + 0.03) <= FLOAT_TOL)
    entry_row = next(event for event in compiled.events if event.kind == "entry_fill")
    partial_row = next(event for event in compiled.events if event.kind == "partial_fill")
    final_row = next(event for event in compiled.events if event.kind == "final_exit")
    check("fixed_slippage_debited_at_entry", abs(entry_row.balance_r + 0.02) <= FLOAT_TOL)
    check("partial_classifier_slippage_allocated", abs(partial_row.classifier_r - 0.49) <= FLOAT_TOL)
    check("final_classifier_carries_swap", abs(final_row.classifier_r - 0.96) <= FLOAT_TOL)
    lifecycle_rows = tuple(
        event for event in compiled.events if event.trade_key == compiled.lifecycles[0].trade_key
    )
    check("balance_cashflows_reconcile", abs(sum(row.balance_r for row in lifecycle_rows) - 1.45) <= FLOAT_TOL)
    check("classifier_cashflows_reconcile", abs(sum(row.classifier_r for row in lifecycle_rows) - 1.45) <= FLOAT_TOL)
    boundary_index = (date(2026, 1, 26) - date.fromisoformat(compiled.first_day)).days
    check("pending_spanning_midnight_is_not_flat", not compiled.flat_boundary_at_index(boundary_index))
    check(
        "spanning_boundary_excluded_from_blocks",
        all(
            start != boundary_index and start + BLOCK_LENGTH != boundary_index
            for start in compiled.eligible_block_starts
        ),
    )
    check("block_eligibility_recomputes", compiled.recompute_eligible_block_starts() == compiled.eligible_block_starts)
    again = compile_cost_tape(inputs, source)
    check("compiled_hash_deterministic", compiled.compiled_sha256 == again.compiled_sha256)
    check("compiled_bytes_deterministic", compiled.normalized_bytes() == again.normalized_bytes())
    check("policy_mapping_retains_hash", compiled.as_policy_mapping()["compiled_sha256"] == compiled.compiled_sha256)
    policy_tape, policy_meta = compiled.to_policy_inputs()
    check("policy_tape_event_count", len(policy_tape.events) == len(compiled.events))
    check("policy_tape_owner_is_pending_day", policy_tape.trades[0].owner_day.isoformat() == "2026-01-05")
    check(
        "policy_tape_block_eligibility",
        policy_tape.eligible_flat_block_starts(BLOCK_LENGTH) == compiled.eligible_block_starts,
    )
    policy_swap = next(
        event for event in policy_tape.events if event.normalized_kind().value == "swap"
    )
    check(
        "policy_swap_raw_cadence",
        policy_swap.swap_cash_per_lot == -3.0
        and policy_swap.swap_days == 1
        and policy_swap.swap_multiplier == 1.0,
    )
    check("policy_symbol_meta_conversion", set(policy_meta) == {"SYN"})

    broken = SimpleNamespace(**vars(source))
    broken.diagnostics = tuple({**row, "trade_key": "WRONG"} for row in source.diagnostics)
    broken.diagnostics_sha256 = hashlib.sha256(_diagnostic_bytes(broken.diagnostics)).hexdigest()
    try:
        compile_cost_tape(inputs, broken)
    except AdapterInvariantError:
        passed.append("diagnostic_join_failure_detected")
    else:  # pragma: no cover - failure path is the assertion target
        raise AssertionError("diagnostic_join_failure_detected")

    return {"passed": len(passed), "checks": tuple(passed)}


if __name__ == "__main__":
    result = self_test()
    print(f"V130_PASS_ADAPTER_SYNTHETIC passed={result['passed']}")
