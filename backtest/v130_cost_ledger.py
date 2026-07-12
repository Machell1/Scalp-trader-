"""Executable-price cost ledger for MomentumPullbackEA v1.30.

Binding protocol: ``docs/V130_COST_LEDGER_SPEC_2026-07-12.md``
(SHA256 ``271a12f4ce46717f15871aaf0c54321780484442709b82d628b047a2132d97a4``).

The module is additive and performs no data loading on import.  It preserves
the strict-ask F2 fill/bracket geometry while replacing the legacy median
spread debit with explicit executable prices, fixed registered slippage, and
conservative broker-midnight swap cashflows.  Only ``run_cost_coupled`` runs
the shared causal scheduler; ``self_test`` is pure synthetic.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import numpy as np

from parity_engine import BAR_SEC, ExecutionPlan, LifecycleMark, SymData, run_live
from v130_coupled import (
    CAPS,
    F2_STRICT_ASK,
    HOLD,
    PARTIAL_FRACTION,
    PARTIAL_AT_R,
    STOP_ATR,
    SYMBOLS,
    TP_ATR,
    W2,
    WINDOW,
    ea_server_day,
    normalized_event_bytes,
    replay_invariants,
    V130Execution,
)


E0_EXECUTABLE = "E0_EXECUTABLE"
E1_MEASURED = "E1_MEASURED"
E2_STRESS = "E2_STRESS"
COST_MODES = (E0_EXECUTABLE, E1_MEASURED, E2_STRESS)

FIXED_SLIPPAGE_R = {
    E0_EXECUTABLE: 0.0,
    E1_MEASURED: 0.02,
    E2_STRESS: 0.04,
}
SWAP_MULTIPLIER = {
    E0_EXECUTABLE: 0.0,
    E1_MEASURED: 1.0,
    E2_STRESS: 2.0,
}

EA_SERVER = ZoneInfo("Europe/Helsinki")
_FLOAT_TOL = 1e-12


@dataclass(frozen=True)
class SwapCalibration:
    """Frozen pre-outcome points-mode broker calibration."""

    swap_long_points: float
    swap_short_points: float
    point: float
    tick_size: float
    trade_tick_value_loss: float


FROZEN_SWAP_CALIBRATION: dict[str, SwapCalibration] = {
    "US30.cash": SwapCalibration(-1139.46, +47.42, 0.01, 0.01, 0.01),
    "US100.cash": SwapCalibration(-645.63, +26.87, 0.01, 0.01, 0.01),
    "JP225.cash": SwapCalibration(
        -870.78,
        -373.19,
        0.01,
        0.01,
        0.0006183221210922042,
    ),
}


@dataclass(frozen=True)
class SwapEventDiagnostic:
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


@dataclass(frozen=True)
class CostTradeDiagnostic:
    trade_key: str
    geometry_key: str
    mode: str
    symbol: str
    signal_bar: int
    signal_epoch: int
    entry_bar: int
    exit_bar: int
    side: int
    reason: str
    partial: bool
    entry_price: float
    exit_price: float
    frozen_risk: float
    remaining_fraction: float
    base_f2_total_r: float
    legacy_median_spread_debit_r: float
    legacy_debit_removal_contribution_r: float
    legacy_debit_removed_r: float
    short_time_exit_correction_r: float
    short_time_correction_r: float
    banked_partial_r: float
    final_price_r: float
    e0_price_r: float
    fixed_slippage_r: float
    slippage_debit_r: float
    slippage_r: float
    partial_slippage_debit_r: float
    final_slippage_debit_r: float
    conservative_swap_r: float
    swap_r: float
    total_r: float
    final_event_epoch: int
    final_ea_day: str
    loss_classification_r: float
    swap_events: tuple[SwapEventDiagnostic, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CostCoupledTape:
    mode: str
    trades: tuple
    events: tuple[dict, ...]
    census: object
    normalized_sha256: str
    diagnostics: tuple[dict[str, Any], ...]
    diagnostics_sha256: str


def _geometry_key(s: SymData, sig_i: int, side: int) -> str:
    return f"{s.name}:{int(s.ep[sig_i])}:{int(side)}"


def _metadata_symbols(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    symbols = metadata.get("symbols", {})
    if not isinstance(symbols, Mapping):
        raise TypeError("metadata['symbols'] must be a mapping")
    return symbols


def _validate_frozen_calibration(metadata: Mapping[str, Any]) -> None:
    """Reject structural point/tick-size drift while allowing synthetic metadata.

    ``trade_tick_value_loss`` is an account-currency conversion snapshot and
    can move with FX between the frozen-bar retrieval and the registered broker
    calibration.  It cancels algebraically when swap cash and stop risk cash
    are both converted to R, so it is deliberately not equality-gated here.
    """

    supplied_symbols = _metadata_symbols(metadata)
    fields = {
        "point": "point",
        "trade_tick_size": "tick_size",
    }
    for symbol, frozen in FROZEN_SWAP_CALIBRATION.items():
        supplied = supplied_symbols.get(symbol)
        if supplied is None:
            continue
        if not isinstance(supplied, Mapping):
            raise TypeError(f"metadata for {symbol} must be a mapping")
        for field, attribute in fields.items():
            if field not in supplied:
                continue
            observed = float(supplied[field])
            expected = float(getattr(frozen, attribute))
            if not np.isfinite(observed) or not np.isclose(
                observed, expected, rtol=0.0, atol=1e-15
            ):
                raise RuntimeError(
                    f"{symbol}: frozen {field}={expected!r}, metadata has {observed!r}"
                )


def _final_event_epoch(s: SymData, plan: ExecutionPlan) -> int:
    if plan.reason == "TIME":
        return int(plan.free_epoch)
    return int(s.ep[plan.exit_bar]) + BAR_SEC - 1


def _crossed_rollovers(entry_epoch: int, final_epoch: int) -> tuple[tuple[int, date], ...]:
    """Return Helsinki midnights held through, paired with the preceding day."""

    if final_epoch <= entry_epoch:
        return ()
    entry_local = datetime.fromtimestamp(entry_epoch, timezone.utc).astimezone(EA_SERVER)
    final_local = datetime.fromtimestamp(final_epoch, timezone.utc).astimezone(EA_SERVER)
    cursor = entry_local.date() + timedelta(days=1)
    out: list[tuple[int, date]] = []
    while cursor <= final_local.date():
        local_midnight = datetime.combine(cursor, time.min, tzinfo=EA_SERVER)
        epoch = int(local_midnight.timestamp())
        if entry_epoch < epoch <= final_epoch:
            out.append((epoch, cursor - timedelta(days=1)))
        cursor += timedelta(days=1)
    return tuple(out)


class V130CostExecution(V130Execution):
    """F2 executable geometry with an explicit v1.30 cash-R ledger.

    ``V130Execution.mode`` intentionally remains ``F2_STRICT_ASK`` so its
    inherited fill and protective-side touch tests cannot accidentally fall
    back to F1.  The public ledger selector is ``ledger_mode``.
    """

    def __init__(
        self,
        spreads: dict[str, np.ndarray],
        metadata: Mapping[str, Any],
        mode: str,
    ):
        if mode not in COST_MODES:
            raise ValueError(f"unknown cost-ledger mode: {mode!r}")
        if not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        super().__init__(spreads, F2_STRICT_ASK)
        _validate_frozen_calibration(metadata)
        self.metadata = metadata
        self.ledger_mode = mode
        self._diagnostics: dict[str, CostTradeDiagnostic] = {}

    @property
    def diagnostics(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            self._diagnostics[key].to_dict() for key in sorted(self._diagnostics)
        )

    def _swap_events(
        self,
        s: SymData,
        side: int,
        risk: float,
        entry_epoch: int,
        final_epoch: int,
        partial_epoch: int | None,
    ) -> tuple[SwapEventDiagnostic, ...]:
        calibration = FROZEN_SWAP_CALIBRATION.get(s.name)
        if calibration is None:
            raise ValueError(f"no frozen swap calibration for {s.name!r}")
        points = (
            calibration.swap_long_points if side > 0 else calibration.swap_short_points
        )
        risk_cash = (
            risk / calibration.tick_size * calibration.trade_tick_value_loss
        )
        if not np.isfinite(risk_cash) or risk_cash <= 0.0:
            raise ValueError(f"{s.name}: invalid full-position risk cash per lot")
        raw_cash = (
            points
            * calibration.point
            / calibration.tick_size
            * calibration.trade_tick_value_loss
        )
        raw_full_r = raw_cash / risk_cash
        mode_multiplier = SWAP_MULTIPLIER[self.ledger_mode]
        out: list[SwapEventDiagnostic] = []
        for rollover_epoch, preceding_day in _crossed_rollovers(
            entry_epoch, final_epoch
        ):
            if preceding_day.weekday() >= 5:
                continue  # Friday triple already covers Saturday and Sunday.
            open_fraction = (
                1.0 - PARTIAL_FRACTION
                if partial_epoch is not None and partial_epoch < rollover_epoch
                else 1.0
            )
            triple = 3 if preceding_day.weekday() == 4 else 1
            conservative_base = min(raw_full_r, 0.0) * open_fraction * triple
            applied = conservative_base * mode_multiplier
            local_midnight = datetime.fromtimestamp(
                rollover_epoch, timezone.utc
            ).astimezone(EA_SERVER)
            out.append(
                SwapEventDiagnostic(
                    rollover_epoch=int(rollover_epoch),
                    rollover_local=local_midnight.isoformat(),
                    preceding_local_date=preceding_day.isoformat(),
                    triple_multiplier=int(triple),
                    open_fraction=float(open_fraction),
                    swap_points=float(points),
                    raw_cash_per_lot=float(raw_cash),
                    full_stop_risk_cash_per_lot=float(risk_cash),
                    raw_full_position_r=float(raw_full_r),
                    conservative_base_r=float(conservative_base),
                    applied_r=float(applied),
                    positive_credit_suppressed=bool(raw_full_r > 0.0),
                )
            )
        return tuple(out)

    def resolve(
        self,
        s: SymData,
        sig_i: int,
        entry_bar: int,
        side: int,
        entry: float,
        atr_sig: float,
    ) -> ExecutionPlan:
        base = super().resolve(s, sig_i, entry_bar, side, entry, atr_sig)
        risk = STOP_ATR * float(atr_sig)
        if not np.isfinite(risk) or risk <= 0.0:
            raise ValueError("signal ATR risk must be positive and finite")

        partial_marks = tuple(mark for mark in base.marks if mark.kind == "partial_fill")
        if len(partial_marks) > 1:
            raise AssertionError("v1.30 emitted more than one partial")
        partial_done = bool(partial_marks)
        partial_epoch = int(partial_marks[0].epoch) if partial_done else None
        banked_partial_r = sum(float(mark.r_component) for mark in partial_marks)
        remaining = 1.0 - (PARTIAL_FRACTION if partial_done else 0.0)

        exit_price = float(base.exit_price)
        short_time_correction = 0.0
        if base.reason == "TIME" and side < 0:
            observed_spread = self._spread(s, int(base.exit_bar))
            exit_price += observed_spread
            short_time_correction = (
                remaining * side * observed_spread / risk
            )

        final_price_r = remaining * side * (exit_price - float(entry)) / risk
        e0_price_r = banked_partial_r + final_price_r
        legacy_debit = -2.0 * float(s.cost) / STOP_ATR
        legacy_removal = -legacy_debit
        expected_e0 = float(base.total_r) + legacy_removal + short_time_correction
        if not np.isclose(e0_price_r, expected_e0, rtol=0.0, atol=_FLOAT_TOL):
            raise AssertionError(
                f"{s.name}: executable ledger does not reconcile to F2 control"
            )

        entry_epoch = int(s.ep[entry_bar]) + BAR_SEC - 1
        final_epoch = _final_event_epoch(s, base)
        swap_events = self._swap_events(
            s,
            side,
            risk,
            entry_epoch,
            final_epoch,
            partial_epoch,
        )
        swap_r = sum(event.applied_r for event in swap_events)
        fixed_slip = FIXED_SLIPPAGE_R[self.ledger_mode]
        total_r = e0_price_r - fixed_slip + swap_r

        partial_slip = -fixed_slip * (PARTIAL_FRACTION if partial_done else 0.0)
        final_slip = -fixed_slip * remaining
        final_day = ea_server_day(final_epoch)
        loss_classification_r = final_price_r + final_slip + swap_r
        if partial_done and ea_server_day(int(partial_epoch)) == final_day:
            loss_classification_r += banked_partial_r + partial_slip

        geometry_key = _geometry_key(s, sig_i, side)
        if geometry_key in self._diagnostics:
            raise AssertionError(f"duplicate resolved geometry: {geometry_key}")
        diagnostic = CostTradeDiagnostic(
            trade_key=geometry_key,
            geometry_key=geometry_key,
            mode=self.ledger_mode,
            symbol=s.name,
            signal_bar=int(sig_i),
            signal_epoch=int(s.ep[sig_i]),
            entry_bar=int(entry_bar),
            exit_bar=int(base.exit_bar),
            side=int(side),
            reason=str(base.reason),
            partial=partial_done,
            entry_price=float(entry),
            exit_price=float(exit_price),
            frozen_risk=float(risk),
            remaining_fraction=float(remaining),
            base_f2_total_r=float(base.total_r),
            legacy_median_spread_debit_r=float(legacy_debit),
            legacy_debit_removal_contribution_r=float(legacy_removal),
            legacy_debit_removed_r=float(legacy_removal),
            short_time_exit_correction_r=float(short_time_correction),
            short_time_correction_r=float(short_time_correction),
            banked_partial_r=float(banked_partial_r),
            final_price_r=float(final_price_r),
            e0_price_r=float(e0_price_r),
            fixed_slippage_r=float(fixed_slip),
            slippage_debit_r=float(-fixed_slip),
            slippage_r=float(-fixed_slip),
            partial_slippage_debit_r=float(partial_slip),
            final_slippage_debit_r=float(final_slip),
            conservative_swap_r=float(swap_r),
            swap_r=float(swap_r),
            total_r=float(total_r),
            final_event_epoch=int(final_epoch),
            final_ea_day=str(final_day),
            loss_classification_r=float(loss_classification_r),
            swap_events=swap_events,
        )
        self._diagnostics[geometry_key] = diagnostic

        return ExecutionPlan(
            exit_bar=int(base.exit_bar),
            exit_price=float(exit_price),
            reason=str(base.reason),
            total_r=float(total_r),
            free_epoch=int(base.free_epoch),
            entry_r_component=float(-fixed_slip),
            marks=tuple(base.marks),
            loss_classification_r=float(loss_classification_r),
        )


def _diagnostic_bytes(diagnostics: Any) -> bytes:
    return (
        json.dumps(
            diagnostics,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def run_cost_coupled(inputs: Any, mode: str) -> CostCoupledTape:
    """Run one causal E0/E1/E2 column on caller-supplied frozen inputs."""

    events: list[dict] = []
    execution = V130CostExecution(inputs.spreads, inputs.metadata, mode)
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
        raise AssertionError("event replay and cost-ledger trade tape disagree")
    final_keys = {
        str(event["trade_key"])
        for event in events
        if event["kind"] == "final_exit"
    }
    diagnostics = execution.diagnostics
    diagnostic_keys = {str(row["trade_key"]) for row in diagnostics}
    if final_keys != diagnostic_keys:
        raise AssertionError("completed event keys and cost diagnostics disagree")
    event_body = normalized_event_bytes(events)
    diagnostic_body = _diagnostic_bytes(diagnostics)
    return CostCoupledTape(
        mode=mode,
        trades=tuple(trades),
        events=tuple(events),
        census=census,
        normalized_sha256=hashlib.sha256(event_body).hexdigest(),
        diagnostics=diagnostics,
        diagnostics_sha256=hashlib.sha256(diagnostic_body).hexdigest(),
    )


def _synthetic_epochs(local_start: datetime, n: int) -> np.ndarray:
    if local_start.tzinfo is None:
        local_start = local_start.replace(tzinfo=EA_SERVER)
    start = int(local_start.astimezone(timezone.utc).timestamp())
    return np.asarray([start + BAR_SEC * i for i in range(n)], dtype=np.int64)


def _synthetic_symbol(
    name: str,
    epochs: np.ndarray,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    *,
    cost: float = 0.03,
    atr: float = 10.0,
) -> SymData:
    n = len(epochs)
    if not (len(highs) == len(lows) == len(closes) == n):
        raise ValueError("synthetic arrays must have equal length")
    c = np.asarray(closes, dtype=float)
    return SymData(
        name=name,
        ep=np.asarray(epochs, dtype=np.int64),
        o=c.copy(),
        h=np.asarray(highs, dtype=float),
        l=np.asarray(lows, dtype=float),
        c=c,
        atr=np.full(n, float(atr)),
        side=np.zeros(n, dtype=np.int8),
        watr=np.full(n, np.nan),
        cost=float(cost),
        cluster=0,
    )


def _synthetic_execution(
    mode: str, spread: np.ndarray
) -> V130CostExecution:
    spreads = {symbol: np.asarray(spread, dtype=float).copy() for symbol in SYMBOLS}
    return V130CostExecution(spreads, {}, mode)


def _reference_e0(
    s: SymData,
    spread: np.ndarray,
    entry_bar: int,
    side: int,
    entry: float,
    atr_sig: float,
) -> tuple[int, float, str, float, bool]:
    """Small independent strict-ask price-only reference implementation."""

    risk = STOP_ATR * atr_sig
    stop = entry - side * risk
    partial = entry + side * PARTIAL_AT_R * risk
    target = entry + side * TP_ATR * atr_sig
    partial_done = False
    exit_bar = -1
    exit_price = np.nan
    reason = ""
    for bar in range(entry_bar, min(entry_bar + HOLD, len(s.c))):
        bid_high = float(s.h[bar])
        bid_low = float(s.l[bar])
        ask_high = bid_high + float(spread[bar])
        ask_low = bid_low + float(spread[bar])
        stop_hit = bid_low <= stop if side > 0 else ask_high >= stop
        partial_hit = bid_high >= partial if side > 0 else ask_low <= partial
        target_hit = bid_high >= target if side > 0 else ask_low <= target
        if stop_hit:
            exit_bar, exit_price, reason = bar, stop, "SL"
            break
        if not partial_done and partial_hit:
            partial_done = True
        if target_hit:
            exit_bar, exit_price, reason = bar, target, "TP"
            break
    if exit_bar < 0:
        exit_bar = min(entry_bar + HOLD - 1, len(s.c) - 1)
        exit_price = float(s.c[exit_bar])
        if side < 0:
            exit_price += float(spread[exit_bar])
        reason = "TIME"
    remaining = 1.0 - (PARTIAL_FRACTION if partial_done else 0.0)
    total = (
        (PARTIAL_FRACTION * PARTIAL_AT_R if partial_done else 0.0)
        + remaining * side * (exit_price - entry) / risk
    )
    return int(exit_bar), float(exit_price), reason, float(total), partial_done


def self_test() -> dict[str, Any]:
    """Run the binding pure-synthetic geometry, cost, swap, and day tests."""

    passed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            raise AssertionError(name)
        passed.append(name)

    midday = _synthetic_epochs(
        datetime(2026, 7, 6, 12, 0, tzinfo=EA_SERVER), 8
    )
    spread = np.full(8, 1.0)

    cases = {
        "long_sl": (1, [105] * 8, [89] + [95] * 7, [100] * 8, -1.0, "SL", False),
        "short_sl": (-1, [109.5] + [105] * 7, [95] * 8, [100] * 8, -1.0, "SL", False),
        "partial_sl": (1, [111] + [105] * 7, [95, 89] + [95] * 6, [100] * 8, 0.0, "SL", True),
        "partial_tp": (1, [121] + [105] * 7, [95] * 8, [100] * 8, 1.5, "TP", True),
        "stop_first": (1, [121] + [105] * 7, [89] + [95] * 7, [100] * 8, -1.0, "SL", False),
        "long_time": (1, [105] * 8, [95] * 8, [100] * 7 + [103], 0.3, "TIME", False),
        "short_time": (-1, [105] * 8, [95] * 8, [100] * 7 + [97], 0.2, "TIME", False),
    }
    for name, (side, highs, lows, closes, expected_r, reason, partial) in cases.items():
        s = _synthetic_symbol("US30.cash", midday, highs, lows, closes)
        execution = _synthetic_execution(E0_EXECUTABLE, spread)
        plan = execution.resolve(s, 0, 0, side, 100.0, 10.0)
        reference = _reference_e0(s, spread, 0, side, 100.0, 10.0)
        check(f"{name}:reason", plan.reason == reason)
        check(f"{name}:r", abs(plan.total_r - expected_r) <= _FLOAT_TOL)
        check(f"{name}:partial", bool(any(m.kind == "partial_fill" for m in plan.marks)) == partial)
        check(
            f"{name}:independent_reference",
            plan.exit_bar == reference[0]
            and abs(plan.exit_price - reference[1]) <= _FLOAT_TOL
            and plan.reason == reference[2]
            and abs(plan.total_r - reference[3]) <= _FLOAT_TOL
            and partial == reference[4],
        )
    short_diag = _synthetic_execution(E0_EXECUTABLE, spread)
    short_s = _synthetic_symbol(
        "US30.cash", midday, [105] * 8, [95] * 8, [100] * 7 + [97]
    )
    short_diag.resolve(short_s, 0, 0, -1, 100.0, 10.0)
    diag = short_diag.diagnostics[0]
    check("short_time_ask_close", abs(diag["exit_price"] - 98.0) <= _FLOAT_TOL)
    check(
        "short_time_correction",
        abs(diag["short_time_exit_correction_r"] + 0.1) <= _FLOAT_TOL,
    )
    check(
        "legacy_debit_removed",
        abs(diag["legacy_debit_removal_contribution_r"] - 0.06) <= _FLOAT_TOL,
    )

    monday = _synthetic_epochs(
        datetime(2026, 7, 6, 23, 45, tzinfo=EA_SERVER), 8
    )
    quiet_high = [105] * 8
    quiet_low = [95] * 8
    quiet_close = [100] * 8
    jp = _synthetic_symbol(
        "JP225.cash", monday, quiet_high, quiet_low, quiet_close
    )
    e1 = _synthetic_execution(E1_MEASURED, np.zeros(8))
    e1_plan = e1.resolve(jp, 0, 0, 1, 100.0, 10.0)
    e1_diag = e1.diagnostics[0]
    rollover = e1_diag["swap_events"]
    check("ordinary_rollover_count", len(rollover) == 1)
    check("ordinary_rollover_multiplier", rollover[0]["triple_multiplier"] == 1)
    check("ordinary_rollover_fraction", rollover[0]["open_fraction"] == 1.0)
    check("ordinary_negative_swap", rollover[0]["applied_r"] < 0.0)
    check(
        "e1_total_decomposition",
        abs(
            e1_plan.total_r
            - (e1_diag["e0_price_r"] - 0.02 + e1_diag["conservative_swap_r"])
        )
        <= _FLOAT_TOL,
    )

    before_midnight = _synthetic_epochs(
        datetime(2026, 7, 6, 23, 30, tzinfo=EA_SERVER), 8
    )
    partial_jp = _synthetic_symbol(
        "JP225.cash",
        before_midnight,
        [111] + [105] * 7,
        [95] * 8,
        [100] * 8,
    )
    partial_exec = _synthetic_execution(E1_MEASURED, np.zeros(8))
    partial_exec.resolve(partial_jp, 0, 0, 1, 100.0, 10.0)
    partial_diag = partial_exec.diagnostics[0]
    check(
        "partial_before_rollover_fraction",
        partial_diag["swap_events"][0]["open_fraction"] == 0.5,
    )
    check(
        "partial_slippage_prorata",
        abs(partial_diag["partial_slippage_debit_r"] + 0.01) <= _FLOAT_TOL
        and abs(partial_diag["final_slippage_debit_r"] + 0.01) <= _FLOAT_TOL,
    )

    friday = _synthetic_epochs(
        datetime(2026, 7, 10, 23, 45, tzinfo=EA_SERVER), 8
    )
    friday_jp = _synthetic_symbol(
        "JP225.cash", friday, quiet_high, quiet_low, quiet_close
    )
    stress = _synthetic_execution(E2_STRESS, np.zeros(8))
    stress.resolve(friday_jp, 0, 0, 1, 100.0, 10.0)
    stress_diag = stress.diagnostics[0]
    friday_event = stress_diag["swap_events"][0]
    check("friday_triple_rollover", friday_event["triple_multiplier"] == 3)
    check(
        "double_swap_stress",
        abs(
            friday_event["applied_r"]
            - 2.0 * friday_event["conservative_base_r"]
        )
        <= _FLOAT_TOL,
    )
    check("double_slippage_stress", stress_diag["fixed_slippage_r"] == 0.04)
    weekend_events = stress._swap_events(
        friday_jp,
        1,
        10.0,
        int(datetime(2026, 7, 10, 23, 45, tzinfo=EA_SERVER).timestamp()),
        int(datetime(2026, 7, 13, 0, 1, tzinfo=EA_SERVER).timestamp()),
        None,
    )
    check(
        "weekend_not_double_charged",
        len(weekend_events) == 1 and weekend_events[0].triple_multiplier == 3,
    )

    positive_short = _synthetic_symbol(
        "US30.cash", monday, quiet_high, quiet_low, quiet_close
    )
    positive_exec = _synthetic_execution(E1_MEASURED, np.zeros(8))
    positive_exec.resolve(positive_short, 0, 0, -1, 100.0, 10.0)
    positive_diag = positive_exec.diagnostics[0]
    positive_event = positive_diag["swap_events"][0]
    check("positive_swap_suppressed", positive_event["positive_credit_suppressed"])
    check("positive_swap_never_credited", positive_event["applied_r"] == 0.0)

    cross = _synthetic_symbol(
        "US30.cash",
        before_midnight,
        [105] * 8,
        [89] + [95] * 7,
        [100] * 7 + [108],
    )
    cross_exec = _synthetic_execution(E1_MEASURED, np.ones(8))
    cross_plan = cross_exec.resolve(cross, 0, 0, -1, 100.0, 10.0)
    cross_diag = cross_exec.diagnostics[0]
    check("cross_midnight_partial", cross_diag["partial"])
    check("cross_midnight_total_positive", cross_plan.total_r > 0.0)
    check(
        "cross_midnight_day_truncated_loss",
        abs(cross_plan.loss_classification_r + 0.46) <= _FLOAT_TOL,
    )
    check(
        "cross_midnight_classifier_differs",
        cross_plan.loss_classification_r < 0.0 < cross_plan.total_r,
    )

    check(
        "deterministic_diagnostics",
        _diagnostic_bytes(cross_exec.diagnostics)
        == _diagnostic_bytes(cross_exec.diagnostics),
    )
    return {"passed": len(passed), "tests": passed}


if __name__ == "__main__":
    result = self_test()
    print(f"v130 cost-ledger synthetic tests: {result['passed']} passed")
    for test_name in result["tests"]:
        print(f"PASS {test_name}")
