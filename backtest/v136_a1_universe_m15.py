"""M15-grain tape builder for the preregistered v1.36-A1 universe study.

The live strategy remains H1.  This module maps only completed, hour-aligned
H1 signals onto their final M15 constituent and resolves pending orders and
position lifecycles on the underlying manifest M15 bars.  It is research-only.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from build_h1_universe_tape import CLUSTERS, ftmo_metas
from parity_engine import (
    BAR_SEC,
    MB,
    ExecutionPlan,
    LifecycleMark,
    SymData,
    prep_symbol,
    run_live,
)
from run_h1_universe_screen import META_PATH, load_symbol, source_path
from run_mtf_anchor_screen import aggregate_phase
from snapshot_h1_universe_meta import SOURCE_TO_FTMO
from v130_pass_policy import AccountEvent, PassTape


HERE = Path(__file__).resolve().parent
PRAGUE = ZoneInfo("Europe/Prague")

BASE_SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
CANDIDATES = ("France_40", "Australia_200")
ALL_SOURCES = BASE_SOURCES + CANDIDATES
BASE_SYMBOLS = tuple(SOURCE_TO_FTMO[source] for source in BASE_SOURCES)

MOMENTUM_A1 = 3.0
MOMENTUM_C1 = 2.0
WICK_ATR = 0.30
ENTRY_OFFSET_ATR = 0.60
PENDING_M15_BARS = 12
STOP_ATR = 1.0
PARTIAL_AT_R = 1.0
PARTIAL_FRACTION = 0.75
TARGET_ATR = 1.5
HOLD_H1_BARS = 8

CAPS_SOURCE = {
    "global": 2,
    "cluster": 1,
    # Path-dependent day gates belong to the account replay, not source tape.
    "fills_day": 10**9,
    "consec": 10**9,
}

CLUSTER_IDS = {
    "US_INDEX": 0,
    "ASIA_INDEX": 1,
    "FX": 2,
    "EU_INDEX": 3,
}


def _epoch(value) -> int:
    return int(pd.Timestamp(value).timestamp())


def _sha_json(value) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class SplitBounds:
    start_epoch: int
    cutoff_epoch: int
    end_epoch: int

    def as_dict(self) -> dict:
        return {
            "start_epoch": self.start_epoch,
            "start_utc": datetime.fromtimestamp(
                self.start_epoch, timezone.utc
            ).isoformat(),
            "cutoff_epoch": self.cutoff_epoch,
            "cutoff_utc": datetime.fromtimestamp(
                self.cutoff_epoch, timezone.utc
            ).isoformat(),
            "end_epoch": self.end_epoch,
            "end_utc": datetime.fromtimestamp(self.end_epoch, timezone.utc).isoformat(),
        }


@dataclass
class SymbolContext:
    source: str
    symbol: str
    cluster_name: str
    cluster_id: int
    raw: pd.DataFrame
    h1: pd.DataFrame
    h1_prepared: SymData
    end_idx: np.ndarray
    raw_prepared: SymData
    h1_index_by_raw: dict[int, int]
    hour_ordinal_by_raw: np.ndarray
    last_raw_by_hour_ordinal: dict[int, int]
    source_spread: np.ndarray | None
    snapshot_full_spread: float
    fallback_per_side_atr: float | None
    cost_e1_per_side_atr: float
    cost_parts: dict


@dataclass(frozen=True)
class BuiltTape:
    tape: PassTape
    trades: tuple[dict, ...]
    source_events: tuple[dict, ...]
    diagnostics: dict


def _cluster_name(symbol: str) -> str:
    value = CLUSTERS[symbol]
    if value == "US_INDEX":
        return "US_INDEX"
    if value == "ASIA_INDEX":
        return "ASIA_INDEX"
    if value == "EU_INDEX":
        return "EU_INDEX"
    if value == "FX":
        return "FX"
    raise ValueError(f"unregistered universe-study cluster: {symbol} -> {value}")


def _raw_frame(source: str) -> pd.DataFrame:
    frame = pd.read_csv(source_path(source))
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").reset_index(drop=True)
    if frame["time"].duplicated().any():
        raise RuntimeError(f"{source}: duplicate M15 timestamps")
    for column in ("open", "high", "low", "close"):
        values = frame[column].to_numpy(float)
        if not np.isfinite(values).all():
            raise RuntimeError(f"{source}: non-finite {column}")
    return frame


def _hour_maps(raw: pd.DataFrame) -> tuple[np.ndarray, dict[int, int]]:
    hours = raw["time"].dt.floor("h")
    codes, uniques = pd.factorize(hours, sort=False)
    if (codes < 0).any():
        raise RuntimeError("hour factorization failed")
    last: dict[int, int] = {}
    for index, code in enumerate(codes):
        last[int(code)] = int(index)
    if len(last) != len(uniques):
        raise RuntimeError("hour ordinal map is inconsistent")
    return codes.astype(np.int64), last


def load_context(source: str) -> SymbolContext:
    if source not in ALL_SOURCES:
        raise ValueError(f"source not preregistered: {source}")
    metadata = json.loads(META_PATH.read_text(encoding="utf-8"))
    loaded = load_symbol(source, metadata)
    raw = _raw_frame(source)
    aggregated = aggregate_phase(raw, factor=4, phase=0)
    h1 = aggregated[[
        "time", "open", "high", "low", "close", "volume", "spread_price"
    ]].copy()
    reference = loaded.h1.reset_index(drop=True)
    pd.testing.assert_frame_equal(
        h1.reset_index(drop=True), reference, check_dtype=False, check_exact=True
    )

    cluster_name = _cluster_name(loaded.ftmo_symbol)
    h1_prepared = prep_symbol(
        h1,
        loaded.cost_e1,
        loaded.ftmo_symbol,
        CLUSTER_IDS[cluster_name],
    )
    end_idx = aggregated["end_idx"].to_numpy(np.int64)
    n = len(raw)
    raw_base = prep_symbol(
        raw[["time", "open", "high", "low", "close"]],
        loaded.cost_e1,
        loaded.ftmo_symbol,
        CLUSTER_IDS[cluster_name],
    )
    raw_base.atr[:] = np.nan
    raw_base.side[:] = 0
    raw_base.watr[:] = np.nan
    h1_index_by_raw: dict[int, int] = {}
    for h1_index, raw_index in enumerate(end_idx):
        raw_index = int(raw_index)
        if not 0 <= raw_index < n:
            raise RuntimeError(f"{source}: H1 end index outside M15 frame")
        raw_base.atr[raw_index] = h1_prepared.atr[h1_index]
        raw_base.side[raw_index] = h1_prepared.side[h1_index]
        raw_base.watr[raw_index] = h1_prepared.watr[h1_index]
        h1_index_by_raw[raw_index] = int(h1_index)

    row = metadata["symbols"][source]
    snapshot_full_spread = float(row["spread_points"]) * float(row["point"])
    has_spread = "spread_price" in raw.columns
    source_spread = (
        raw["spread_price"].to_numpy(float).copy() if has_spread else None
    )
    if source_spread is not None:
        invalid = ~np.isfinite(source_spread) | (source_spread < 0)
        if invalid.any():
            raise RuntimeError(f"{source}: invalid source spread rows")
    fallback = None if has_spread else 0.03
    hour_codes, last_by_hour = _hour_maps(raw)
    return SymbolContext(
        source=source,
        symbol=loaded.ftmo_symbol,
        cluster_name=cluster_name,
        cluster_id=CLUSTER_IDS[cluster_name],
        raw=raw,
        h1=h1,
        h1_prepared=h1_prepared,
        end_idx=end_idx,
        raw_prepared=raw_base,
        h1_index_by_raw=h1_index_by_raw,
        hour_ordinal_by_raw=hour_codes,
        last_raw_by_hour_ordinal=last_by_hour,
        source_spread=source_spread,
        snapshot_full_spread=snapshot_full_spread,
        fallback_per_side_atr=fallback,
        cost_e1_per_side_atr=float(loaded.cost_e1),
        cost_parts=dict(loaded.cost_parts),
    )


def load_contexts(sources: Iterable[str] = ALL_SOURCES) -> dict[str, SymbolContext]:
    contexts = {source: load_context(source) for source in sources}
    symbols = [context.symbol for context in contexts.values()]
    if len(symbols) != len(set(symbols)):
        raise RuntimeError("source-to-FTMO mapping is not one-to-one")
    return contexts


def split_bounds(contexts: dict[str, SymbolContext]) -> SplitBounds:
    required = set(ALL_SOURCES)
    if set(contexts) != required:
        raise ValueError("split bounds require the current four plus both candidates")
    starts = [_epoch(context.h1.iloc[0]["time"]) for context in contexts.values()]
    ends = [_epoch(context.h1.iloc[-1]["time"]) + 3600 for context in contexts.values()]
    start = max(starts)
    end = min(ends)
    if end <= start:
        raise RuntimeError("no common H1 timestamp interval")
    raw_cutoff = start + math.floor(0.70 * (end - start))
    cutoff = ((raw_cutoff + 3599) // 3600) * 3600
    if not start < cutoff < end:
        raise RuntimeError("invalid registered chronological cutoff")
    return SplitBounds(start, cutoff, end)


def _full_horizon_available(
    context: SymbolContext, raw_index: int, bounds: SplitBounds
) -> bool:
    """Require the complete pending window and worst-case H1 hold before end."""
    latest_fill = raw_index + PENDING_M15_BARS
    cancellation_bar = latest_fill + 1
    if cancellation_bar >= len(context.raw_prepared.c):
        return False
    latest_entry_hour = int(context.hour_ordinal_by_raw[latest_fill])
    final_hour = latest_entry_hour + HOLD_H1_BARS - 1
    final_bar = context.last_raw_by_hour_ordinal.get(final_hour)
    if final_bar is None or final_bar < latest_fill:
        return False
    cancellation_epoch = int(context.raw_prepared.ep[cancellation_bar])
    final_epoch = (
        int(context.raw_prepared.ep[final_bar + 1])
        if final_bar + 1 < len(context.raw_prepared.ep)
        else int(context.raw_prepared.ep[final_bar]) + BAR_SEC
    )
    return cancellation_epoch <= bounds.end_epoch and final_epoch <= bounds.end_epoch


def _signal_mask(
    context: SymbolContext,
    bounds: SplitBounds,
    segment: str,
    momentum_atr_mult: float,
) -> tuple[SymData, int]:
    if segment not in {"discovery", "validation", "full"}:
        raise ValueError(f"unknown segment: {segment}")
    if momentum_atr_mult not in {MOMENTUM_C1, MOMENTUM_A1}:
        raise ValueError("only preregistered 2.0 and 3.0 momentum thresholds exist")
    base = context.raw_prepared
    lifted = SymData(
        base.name,
        base.ep.copy(),
        base.o.copy(),
        base.h.copy(),
        base.l.copy(),
        base.c.copy(),
        base.atr.copy(),
        base.side.copy(),
        base.watr.copy(),
        base.cost,
        base.cluster,
    )
    right_censored = 0
    for raw_index, h1_index in context.h1_index_by_raw.items():
        side = int(lifted.side[raw_index])
        if side == 0:
            continue
        signal_open = int(lifted.ep[raw_index]) - 2700
        placement = int(lifted.ep[raw_index]) + BAR_SEC
        if signal_open < bounds.start_epoch or placement >= bounds.end_epoch:
            lifted.side[raw_index] = 0
            continue
        if segment == "discovery" and placement >= bounds.cutoff_epoch:
            lifted.side[raw_index] = 0
            continue
        if segment == "validation" and placement < bounds.cutoff_epoch:
            lifted.side[raw_index] = 0
            continue
        if momentum_atr_mult > MOMENTUM_C1:
            prepared = context.h1_prepared
            move = (
                prepared.c[h1_index - (MB - 1)] - prepared.c[h1_index]
                if h1_index >= MB - 1 else np.nan
            )
            atr = float(prepared.atr[h1_index])
            impulse = abs(move / atr) if np.isfinite(move) and atr > 0 else np.nan
            if not np.isfinite(impulse) or impulse < momentum_atr_mult:
                lifted.side[raw_index] = 0
                continue
        passes_w2 = (
            np.isfinite(lifted.watr[raw_index])
            and lifted.watr[raw_index] >= WICK_ATR
        )
        if passes_w2 and not _full_horizon_available(context, raw_index, bounds):
            lifted.side[raw_index] = 0
            right_censored += 1
    return lifted, right_censored


class A1M15Execution:
    """Quote-side M15 execution with frozen H1 ATR and bar-counted time exit."""

    def __init__(self, contexts_by_symbol: dict[str, SymbolContext], cost_mult: float):
        if cost_mult not in {1.0, 2.0}:
            raise ValueError("cost multiplier must be E1=1 or E2=2")
        self.contexts = contexts_by_symbol
        self.cost_mult = float(cost_mult)

    def _context(self, s: SymData) -> SymbolContext:
        try:
            return self.contexts[s.name]
        except KeyError as exc:
            raise ValueError(f"missing execution context for {s.name}") from exc

    def _spread(self, s: SymData, bar: int, atr_sig: float) -> float:
        context = self._context(s)
        candidates = [max(0.0, float(context.snapshot_full_spread))]
        if context.source_spread is not None:
            candidates.append(float(context.source_spread[bar]))
        if context.fallback_per_side_atr is not None:
            candidates.append(
                2.0 * float(context.fallback_per_side_atr) * float(atr_sig)
            )
        value = max(candidates)
        if not np.isfinite(value) or value < 0:
            raise RuntimeError(f"{s.name} bar {bar}: invalid modeled spread")
        return value

    def find_fill(
        self, s: SymData, side: int, entry: float, w_start: int, w_end: int
    ) -> int:
        signal_bar = w_start - 1
        atr_sig = float(s.atr[signal_bar])
        for bar in range(w_start, min(w_end + 1, len(s.c))):
            spread = self._spread(s, bar, atr_sig)
            if side > 0:
                touched = float(s.l[bar]) + spread <= entry
            else:
                touched = float(s.h[bar]) >= entry
            if touched:
                return int(bar)
        return -1

    def _time_exit_bar(self, s: SymData, entry_bar: int) -> int:
        context = self._context(s)
        entry_hour = int(context.hour_ordinal_by_raw[entry_bar])
        target_hour = entry_hour + HOLD_H1_BARS - 1
        if target_hour in context.last_raw_by_hour_ordinal:
            return int(context.last_raw_by_hour_ordinal[target_hour])
        raise RuntimeError(
            f"{s.name}: censored eighth-H1 time exit reached execution"
        )

    def resolve(
        self,
        s: SymData,
        sig_i: int,
        entry_bar: int,
        side: int,
        entry: float,
        atr_sig: float,
    ) -> ExecutionPlan:
        del sig_i
        risk = STOP_ATR * float(atr_sig)
        if not np.isfinite(risk) or risk <= 0:
            raise ValueError("signal ATR risk must be positive")
        stop = entry - side * risk
        partial = entry + side * PARTIAL_AT_R * risk
        target = entry + side * TARGET_ATR * float(atr_sig)
        partial_done = False
        marks: list[LifecycleMark] = []
        exit_bar = None
        exit_price = None
        reason = ""
        time_exit = self._time_exit_bar(s, entry_bar)

        for bar in range(entry_bar, min(time_exit + 1, len(s.c))):
            high = float(s.h[bar])
            low = float(s.l[bar])
            spread = self._spread(s, bar, atr_sig)
            if side > 0:
                stop_hit = low <= stop
                partial_hit = high >= partial
                target_hit = high >= target
                favorable = target if target_hit else high
                adverse = low
            else:
                ask_high = high + spread
                ask_low = low + spread
                stop_hit = ask_high >= stop
                partial_hit = ask_low <= partial
                target_hit = ask_low <= target
                favorable = target if target_hit else ask_low
                adverse = ask_high

            if stop_hit:
                exit_bar, exit_price, reason = bar, stop, "SL"
                break

            mark_epoch = int(s.ep[bar]) + BAR_SEC - 1

            def append_partial() -> None:
                nonlocal partial_done
                partial_done = True
                marks.append(
                    LifecycleMark(
                        "partial_fill",
                        int(bar),
                        mark_epoch,
                        float(partial),
                        PARTIAL_FRACTION * PARTIAL_AT_R,
                        "+1R bank75:favorable",
                    )
                )

            def append_mark(price: float, role: str) -> None:
                marks.append(
                    LifecycleMark(
                        "bar_mark", int(bar), mark_epoch, float(price), 0.0,
                        f"m15_quote_side:{role}",
                    )
                )

            if target_hit:
                append_mark(adverse, "adverse")
                if not partial_done and partial_hit:
                    append_partial()
                append_mark(favorable, "favorable")
            else:
                if not partial_done and partial_hit:
                    append_partial()
                append_mark(favorable, "favorable")
                append_mark(adverse, "adverse")
            if target_hit:
                exit_bar, exit_price, reason = bar, target, "TP"
                break

        if exit_bar is None:
            exit_bar = int(time_exit)
            exit_price = float(s.c[exit_bar])
            if side < 0:
                exit_price += self._spread(s, exit_bar, atr_sig)
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


def _calendar_bounds(bounds: SplitBounds, segment: str) -> tuple:
    if segment == "discovery":
        first, last = bounds.start_epoch, bounds.cutoff_epoch - 1
    elif segment == "validation":
        first, last = bounds.cutoff_epoch, bounds.end_epoch - 1
    elif segment == "full":
        first, last = bounds.start_epoch, bounds.end_epoch - 1
    else:
        raise ValueError(segment)
    first_day = datetime.fromtimestamp(first, timezone.utc).astimezone(PRAGUE).date()
    last_day = datetime.fromtimestamp(last, timezone.utc).astimezone(PRAGUE).date()
    return first_day, last_day


def _to_policy_events(
    source_events: Iterable[dict], symbols: dict[str, SymData], clusters: dict[str, str]
) -> tuple[AccountEvent, ...]:
    output: list[AccountEvent] = []
    remaining: dict[str, float] = {}
    index_by_symbol = {symbol: data for symbol, data in symbols.items()}
    kind_map = {
        "pending_placement": "pending_open",
        "pending_cancellation": "pending_cancel",
        "entry_fill": "entry",
        "bar_mark": "mark",
        "partial_fill": "partial",
        "final_exit": "final",
    }
    sequence = 0
    for row in source_events:
        kind = row["kind"]
        if kind not in kind_map:
            continue
        trade_id = str(row["trade_key"])
        symbol = str(row["symbol"])
        data = index_by_symbol[symbol]
        signal_bar = int(row["signal_bar"])
        stop_distance = float(data.atr[signal_bar]) * STOP_ATR
        if not np.isfinite(stop_distance) or stop_distance <= 0:
            raise RuntimeError(f"{trade_id}: invalid frozen stop distance")
        if kind == "pending_placement":
            remaining[trade_id] = 1.0
        current = remaining.get(trade_id, 1.0)
        if kind == "partial_fill":
            current = 1.0 - PARTIAL_FRACTION
            remaining[trade_id] = current
        elif kind == "final_exit":
            current = 0.0
        role = "neutral"
        reason = str(row.get("reason", ""))
        if kind == "partial_fill" or reason.endswith(":favorable"):
            role = "favorable"
        elif reason.endswith(":adverse"):
            role = "adverse"
        fixed = (
            -float(row.get("r_component") or 0.0) if kind == "entry_fill" else 0.0
        )
        if fixed < -1e-12:
            raise RuntimeError(f"{trade_id}: entry cost has wrong sign")
        sequence += 1
        output.append(
            AccountEvent(
                event_id=f"{trade_id}:{row['sequence']}:{kind}",
                trade_id=trade_id,
                symbol=symbol,
                cluster=clusters[symbol],
                epoch=int(row["epoch"]),
                sequence=sequence,
                kind=kind_map[kind],
                side=int(row["side"]),
                price=float(row["price"]),
                stop_distance=stop_distance,
                fixed_slippage_r=max(0.0, fixed),
                remaining_fraction=float(current),
                mark_role=role,
            )
        )
        if kind in {"pending_cancellation", "final_exit"}:
            remaining.pop(trade_id, None)
    if remaining:
        raise RuntimeError(f"unterminated source lifecycles: {sorted(remaining)[:3]}")
    return tuple(output)


def _filter_straddlers(
    events: tuple[dict, ...], trades: list, bounds: SplitBounds, segment: str
) -> tuple[tuple[dict, ...], list, int]:
    if segment != "discovery":
        return events, trades, 0
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in events:
        if row["kind"] != "signal_rejection":
            grouped[str(row["trade_key"])].append(row)
    straddlers = {
        key for key, rows in grouped.items()
        if min(int(row["epoch"]) for row in rows) < bounds.cutoff_epoch
        and max(int(row["epoch"]) for row in rows) >= bounds.cutoff_epoch
    }
    kept_events = tuple(
        row for row in events
        if row["kind"] == "signal_rejection" or str(row["trade_key"]) not in straddlers
    )
    kept_trades = [
        trade for trade in trades
        if f"{trade.sym}:{int(trade.ep_sig)}:{int(trade.side)}" not in straddlers
    ]
    return kept_events, kept_trades, len(straddlers)


def build_tape(
    contexts: dict[str, SymbolContext],
    sources: tuple[str, ...],
    bounds: SplitBounds,
    *,
    segment: str,
    cost_mult: float,
    momentum_atr_mult: float = MOMENTUM_A1,
) -> BuiltTape:
    if not set(BASE_SOURCES).issubset(sources) and len(sources) != 1:
        raise ValueError("portfolio tape must preserve the current four sources")
    if len(sources) > 1 and tuple(sources[:4]) != BASE_SOURCES:
        raise ValueError("current A1 priority must remain fixed at positions 0..3")
    if len(sources) > 4 and len(sources) != 5:
        raise ValueError("only one appended candidate is permitted")
    lifted_rows = [
        _signal_mask(contexts[source], bounds, segment, momentum_atr_mult)
        for source in sources
    ]
    lifted = [row[0] for row in lifted_rows]
    right_censored = {
        contexts[source].symbol: int(row[1])
        for source, row in zip(sources, lifted_rows)
    }
    symbols_by_name = {data.name: data for data in lifted}
    contexts_by_symbol = {contexts[source].symbol: contexts[source] for source in sources}
    clusters = {contexts[source].symbol: contexts[source].cluster_name for source in sources}
    execution = A1M15Execution(contexts_by_symbol, cost_mult)
    event_rows: list[dict] = []
    thresholds = {data.name: WICK_ATR for data in lifted}
    trades, census = run_live(
        lifted,
        thr=thresholds,
        caps=CAPS_SOURCE,
        queue=False,
        reverse_scan=False,
        window=PENDING_M15_BARS,
        replace_on_signal=False,
        execution=execution,
        event_sink=event_rows.append,
    )
    event_tuple, trades, straddlers = _filter_straddlers(
        tuple(event_rows), trades, bounds, segment
    )
    lifecycle_events = tuple(
        row for row in event_tuple if row["kind"] != "signal_rejection"
    )
    policy_events = _to_policy_events(lifecycle_events, symbols_by_name, clusters)
    first_day, last_day = _calendar_bounds(bounds, segment)
    tape = PassTape.from_events(policy_events, first_day=first_day, last_day=last_day)

    events_by_trade: dict[str, list[dict]] = defaultdict(list)
    for row in lifecycle_events:
        events_by_trade[str(row["trade_key"])].append(row)
    trade_rows = []
    for trade in trades:
        raw_index = int(trade.sig)
        context = contexts_by_symbol[trade.sym]
        h1_index = context.h1_index_by_raw[raw_index]
        signal_epoch = int(trade.ep_sig)
        trade_id = f"{trade.sym}:{signal_epoch}:{int(trade.side)}"
        rows = events_by_trade[trade_id]
        placement_row = next(row for row in rows if row["kind"] == "pending_placement")
        entry_row = next(row for row in rows if row["kind"] == "entry_fill")
        exit_row = next(row for row in rows if row["kind"] == "final_exit")
        placement_epoch = int(placement_row["epoch"])
        entry_epoch = int(entry_row["epoch"])
        exit_epoch = int(exit_row["epoch"])
        trade_rows.append({
            "trade_id": trade_id,
            "symbol": trade.sym,
            "source": context.source,
            "side": int(trade.side),
            "signal_epoch": signal_epoch,
            "signal_utc": datetime.fromtimestamp(
                signal_epoch, timezone.utc
            ).isoformat(),
            "placement_epoch": placement_epoch,
            "placement_utc": datetime.fromtimestamp(
                placement_epoch, timezone.utc
            ).isoformat(),
            "entry_epoch": entry_epoch,
            "entry_utc": datetime.fromtimestamp(entry_epoch, timezone.utc).isoformat(),
            "exit_epoch": exit_epoch,
            "exit_utc": datetime.fromtimestamp(exit_epoch, timezone.utc).isoformat(),
            "signal_h1_index": int(h1_index),
            "entry_bar": int(trade.entry_bar),
            "exit_bar": int(trade.exit_bar),
            "r": float(trade.r),
            "reason": str(trade.reason),
        })
    rejects = Counter(
        str(row["reason"]) for row in event_tuple if row["kind"] == "signal_rejection"
    )
    kinds = Counter(str(row["kind"]) for row in lifecycle_events)
    by_symbol = Counter(row["symbol"] for row in trade_rows)
    by_side = Counter(
        f"{row['symbol']}:{'long' if row['side'] > 0 else 'short'}"
        for row in trade_rows
    )
    diagnostics = {
        "sources": list(sources),
        "symbols": [contexts[source].symbol for source in sources],
        "segment": segment,
        "cost_mode": "E1_MEASURED" if cost_mult == 1.0 else "E2_STRESS",
        "cost_multiplier": cost_mult,
        "momentum_atr_mult": momentum_atr_mult,
        "priority": [contexts[source].symbol for source in sources],
        "clusters": clusters,
        "split": bounds.as_dict(),
        "straddling_lifecycles_excluded": straddlers,
        "right_censored_signals_excluded": right_censored,
        "fills": len(trade_rows),
        "fills_by_symbol": dict(sorted(by_symbol.items())),
        "fills_by_symbol_side": dict(sorted(by_side.items())),
        "source_event_kinds": dict(sorted(kinds.items())),
        "signal_rejections": dict(sorted(rejects.items())),
        "scheduler_census": asdict(census),
        "policy_events": len(tape.events),
        "policy_trades": len(tape.trades),
        "source_events_sha256": _sha_json(lifecycle_events),
        "policy_events_sha256": _sha_json([asdict(event) for event in tape.events]),
        "trade_rows_sha256": _sha_json(trade_rows),
        "costs": {
            contexts[source].symbol: {
                "e1_per_side_atr": contexts[source].cost_e1_per_side_atr,
                "parts": contexts[source].cost_parts,
                "snapshot_full_spread": contexts[source].snapshot_full_spread,
                "fallback_per_side_atr": contexts[source].fallback_per_side_atr,
                "source_spread_available": contexts[source].source_spread is not None,
            }
            for source in sources
        },
    }
    return BuiltTape(tape, tuple(trade_rows), lifecycle_events, diagnostics)


def metadata_for_sources(sources: tuple[str, ...]):
    return ftmo_metas(sources)


def event_hash(tape: PassTape) -> str:
    return _sha_json([asdict(event) for event in tape.events])
