"""Build cost-matched H1 account tapes for universe-admission portfolios."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from parity_engine import MB, START, prep_symbol
from run_h1_universe_screen import BASE_SOURCES, META_PATH, load_symbol, source_path
from snapshot_h1_universe_meta import SOURCE_TO_FTMO
from v130_pass_policy import AccountEvent, PassTape
from v130_risk_policy import SymbolMeta
from walkforward_dsr import real_cost_per_side


HERE = Path(__file__).resolve().parent
PRAGUE = ZoneInfo("Europe/Prague")
BASE_ORDER = {"US30.cash": 0, "US100.cash": 1, "JP225.cash": 2}
CLUSTERS = {
    "US30.cash": "US_INDEX", "US100.cash": "US_INDEX",
    "US500.cash": "US_INDEX", "US2000.cash": "US_INDEX",
    "GER40.cash": "EU_INDEX", "FRA40.cash": "EU_INDEX", "UK100.cash": "EU_INDEX",
    "JP225.cash": "ASIA_INDEX", "AUS200.cash": "ASIA_INDEX", "HK50.cash": "ASIA_INDEX",
    "NATGAS.cash": "ENERGY", "UKOIL.cash": "ENERGY", "USOIL.cash": "ENERGY",
    "XAUUSD": "METALS", "XAGUSD": "METALS", "XCUUSD": "METALS", "XPTUSD": "METALS",
    "BTCUSD": "CRYPTO", "ETHUSD": "CRYPTO", "SOLUSD": "CRYPTO",
    "XRPUSD": "CRYPTO", "BCHUSD": "CRYPTO", "LTCUSD": "CRYPTO",
    "AUDJPY": "FX", "EURGBP": "FX", "EURJPY": "FX", "EURUSD": "FX",
    "GBPJPY": "FX", "GBPUSD": "FX", "NZDUSD": "FX", "USDCAD": "FX",
    "USDCHF": "FX", "USDJPY": "FX",
}

SIGNAL_DETECTIONS = frozenset({"none", "r_struct", "r_drive", "mask"})
SEAT_POLICIES = frozenset({"fixed", "max_z", "min_z", "random"})
Z_TIE_EPSILON = 1e-9


def _audited_impulse_atr(prepared) -> np.ndarray:
    """Return the existing parity-engine impulse magnitude without re-indexing it."""
    n = len(prepared.c)
    move = np.full(n, np.nan)
    move[MB - 1:] = prepared.c[:n - (MB - 1)] - prepared.c[MB - 1:]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.abs(move / prepared.atr)


def _struct_breakout(closes: np.ndarray, bar: int, side: int) -> tuple[bool, float | None]:
    """Frozen 20-prior-close structural-breakout predicate."""
    if bar < 20:
        return False, None
    prior = closes[bar - 20:bar]
    boundary = float(np.max(prior) if side > 0 else np.min(prior))
    decision = closes[bar] > boundary if side > 0 else closes[bar] < boundary
    return bool(decision), boundary


def _m15_component_lookup(source: str) -> dict[pd.Timestamp, tuple[int, float, float]]:
    """Load only causal M15 body inputs, retaining duplicate counts explicitly."""
    raw = pd.read_csv(source_path(source), usecols=["time", "open", "close"])
    raw["_time"] = pd.to_datetime(raw["time"])
    lookup: dict[pd.Timestamp, tuple[int, float, float]] = {}
    for timestamp, rows in raw.groupby("_time", sort=False):
        first = rows.iloc[0]
        lookup[pd.Timestamp(timestamp)] = (
            int(len(rows)), float(first["open"]), float(first["close"])
        )
    return lookup


def _drive_feature(
    lookup: dict[pd.Timestamp, tuple[int, float, float]],
    signal_time,
    side: int,
) -> tuple[bool, int | None, bool, tuple[str, ...]]:
    """Frozen four-constituent R_DRIVE predicate; no next-hour access is possible."""
    start = pd.Timestamp(signal_time)
    timestamps = tuple(start + pd.Timedelta(minutes=15 * offset) for offset in range(4))
    rows = [lookup.get(timestamp) for timestamp in timestamps]
    complete = all(row is not None and row[0] == 1 for row in rows)
    if not complete:
        return False, None, False, tuple(str(timestamp) for timestamp in timestamps)
    bodies = np.asarray([side * (row[2] - row[1]) for row in rows], dtype=float)
    # np.argmax is explicitly earliest-on-tie.
    k_star = int(np.argmax(bodies))
    return k_star <= 1, k_star, True, tuple(str(timestamp) for timestamp in timestamps)


def _ordered_claimants(rows: list[tuple], policy: str, rng) -> list[tuple]:
    """Order one same-epoch claimant set under the preregistered seat policies."""
    fixed = sorted(rows, key=lambda item: (item[1], item[2]))
    if policy == "fixed" or len(fixed) < 2:
        return fixed
    if policy == "random":
        order = rng.permutation(len(fixed))
        return [fixed[int(index)] for index in order]
    remaining = fixed.copy()
    ordered = []
    while remaining:
        extreme = (
            max(float(item[6]) for item in remaining)
            if policy == "max_z"
            else min(float(item[6]) for item in remaining)
        )
        tied = [
            item for item in remaining
            if abs(float(item[6]) - extreme) <= Z_TIE_EPSILON
        ]
        chosen = min(tied, key=lambda item: (item[1], item[2]))
        ordered.append(chosen)
        remaining.remove(chosen)
    return ordered


def _epoch(value) -> int:
    return int(pd.Timestamp(value).timestamp())


def _event(event_id, trade_id, symbol, cluster, side, epoch, sequence, kind, **kwargs):
    return AccountEvent(
        event_id=event_id,
        trade_id=trade_id,
        symbol=symbol,
        cluster=cluster,
        epoch=int(epoch),
        sequence=int(sequence),
        kind=kind,
        side=int(side),
        **kwargs,
    )


def ftmo_metas(sources: tuple[str, ...]) -> dict[str, SymbolMeta]:
    snapshot = json.loads(META_PATH.read_text(encoding="utf-8"))
    output = {}
    for source in sources:
        row = snapshot["symbols"][source]
        symbol = row["ftmo_symbol"]
        output[symbol] = SymbolMeta(
            symbol=symbol,
            trade_tick_size=float(row["trade_tick_size"]),
            trade_tick_value_loss=float(row["trade_tick_value_loss"]),
            trade_tick_value_profit=float(row["trade_tick_value_profit"]),
            volume_min=float(row["volume_min"]),
            volume_step=float(row["volume_step"]),
            volume_max=float(row["volume_max"]),
        )
    return output


def build_h1_universe_tape(
    sources: tuple[str, ...], *, stress: bool = True, cost_mode: str = "registered",
    partial_fraction: float = 0.5, target_atr: float = 2.0,
    reference_same_bar_partial: bool = False,
    momentum_atr_mult: float = 2.0,
    signal_detection: str = "none",
    marginal_admit: dict[str, set[int]] | None = None,
    seat_policy: str = "fixed",
    seat_seed: int = 20260711,
    return_diagnostics: bool = False,
    symbol_cache: dict[str, object] | None = None,
    m15_cache: dict[str, dict[pd.Timestamp, tuple[int, float, float]]] | None = None,
) -> tuple[PassTape, dict[str, int]] | tuple[PassTape, dict[str, int], dict]:
    """Build the registered H1 portfolio tape.

    The exit and momentum arguments are additive.  Their defaults preserve the
    historical account-tape bytes.  ``reference_same_bar_partial`` includes a
    +1R partial immediately before a same-bar target/time exit, matching
    ``retest_engine.resolve`` and the tick-checked EA lifecycle.

    ``momentum_atr_mult`` may only tighten the audited 2.0-ATR signal set.  The
    exact default path is intentionally untouched so the legacy byte regression
    remains meaningful.
    """
    if not set(BASE_SOURCES).issubset(sources):
        raise ValueError("the live H1 control trio must remain in every portfolio")
    if not 0.0 < partial_fraction < 1.0:
        raise ValueError("partial_fraction must be in (0, 1)")
    if target_atr <= 1.0:
        raise ValueError("target_atr must be greater than the +1R partial level")
    if momentum_atr_mult < 2.0:
        raise ValueError("momentum_atr_mult cannot loosen the audited 2.0 threshold")
    if signal_detection not in SIGNAL_DETECTIONS:
        raise ValueError(f"unknown signal detection mode: {signal_detection}")
    if seat_policy not in SEAT_POLICIES:
        raise ValueError(f"unknown seat policy: {seat_policy}")
    if signal_detection != "none" and seat_policy != "fixed":
        raise ValueError(
            "registered cells cannot combine signal re-admission with seat arbitration"
        )
    if signal_detection != "none" and momentum_atr_mult != 3.0:
        raise ValueError("registered signal-detection cells require momentum_atr_mult=3.0")
    if signal_detection == "mask" and marginal_admit is None:
        raise ValueError("mask signal detection requires marginal_admit")
    masks = {
        source: {int(bar) for bar in bars}
        for source, bars in (marginal_admit or {}).items()
    }
    snapshot = json.loads(META_PATH.read_text(encoding="utf-8"))
    events = []
    seq = 0
    first_epoch = None
    last_epoch = None
    raw_counts = {}
    trade_meta = {}
    raw_signal_rows = []
    missing_m15 = 0
    for source in sources:
        if symbol_cache is not None and source not in symbol_cache:
            raise ValueError(f"symbol cache is missing {source}")
        loaded = symbol_cache[source] if symbol_cache is not None else load_symbol(source, snapshot)
        h1 = loaded.h1
        if cost_mode == "registered":
            cost_e1 = loaded.cost_e1
        elif cost_mode == "legacy_source":
            cost_e1 = float(real_cost_per_side(h1))
        else:
            raise ValueError(f"unknown cost mode: {cost_mode}")
        cost = cost_e1 * (2.0 if stress else 1.0)
        prepared = prep_symbol(h1, cost, source)
        base_side = prepared.side.copy()
        impulse_atr = _audited_impulse_atr(prepared)
        feature_decisions = np.zeros(len(prepared.c), dtype=bool)
        feature_values: dict[int, object] = {}
        if signal_detection == "r_drive":
            if m15_cache is not None and source not in m15_cache:
                raise ValueError(f"M15 cache is missing {source}")
            drive_lookup = (
                m15_cache[source]
                if m15_cache is not None else _m15_component_lookup(source)
            )
        else:
            drive_lookup = None
        if signal_detection == "none":
            if momentum_atr_mult > 2.0:
                keep = (
                    (base_side != 0)
                    & np.isfinite(impulse_atr)
                    & (impulse_atr >= momentum_atr_mult)
                )
                prepared.side[~keep] = 0
        else:
            a1 = (
                (base_side != 0)
                & np.isfinite(impulse_atr)
                & (impulse_atr >= 3.0)
            )
            marginal = (
                (base_side != 0)
                & np.isfinite(impulse_atr)
                & (impulse_atr >= 2.0)
                & (impulse_atr < 3.0)
            )
            for bar in np.flatnonzero(marginal):
                bar = int(bar)
                side = int(base_side[bar])
                if signal_detection == "r_struct":
                    decision, boundary = _struct_breakout(prepared.c, bar, side)
                    feature_decisions[bar] = decision
                    feature_values[bar] = {"channel_boundary": boundary}
                elif signal_detection == "r_drive":
                    decision, k_star, complete, timestamps = _drive_feature(
                        drive_lookup, h1.iloc[bar]["time"], side
                    )
                    feature_decisions[bar] = decision
                    feature_values[bar] = {
                        "k_star": k_star,
                        "m15_complete": complete,
                        "m15_timestamps": timestamps,
                    }
                    if (
                        not complete
                        and START <= bar < len(prepared.c) - 5
                        and pd.notna(prepared.watr[bar])
                        and prepared.watr[bar] >= 0.30
                    ):
                        missing_m15 += 1
                else:
                    feature_decisions[bar] = bar in masks.get(source, set())
                    feature_values[bar] = {"mask_member": bool(feature_decisions[bar])}
            prepared.side[~(a1 | (marginal & feature_decisions))] = 0
        symbol = loaded.ftmo_symbol
        cluster = CLUSTERS[symbol]
        if return_diagnostics:
            for bar in range(START, len(prepared.c) - 5):
                side = int(base_side[bar])
                if side == 0 or not np.isfinite(impulse_atr[bar]):
                    continue
                z_value = float(impulse_atr[bar])
                quality = "a1" if z_value >= 3.0 else "marginal"
                feature = None if quality == "a1" else bool(feature_decisions[bar])
                if signal_detection == "none":
                    detection_admit = z_value >= momentum_atr_mult
                else:
                    detection_admit = quality == "a1" or bool(feature)
                w2_pass = bool(pd.notna(prepared.watr[bar]) and prepared.watr[bar] >= 0.30)
                feature_value = feature_values.get(bar)
                signal_admitted = bool(detection_admit and w2_pass)
                raw_signal_rows.append({
                    "source": source,
                    "symbol": symbol,
                    "bar_index": int(bar),
                    "bar_count": int(len(prepared.c)),
                    "oos_start": int(len(prepared.c) * 0.70),
                    "signal_time": str(pd.Timestamp(h1.iloc[bar]["time"])),
                    "placement_epoch": _epoch(h1.iloc[bar]["time"]) + 3599,
                    "side": side,
                    "z": z_value,
                    "quality": quality,
                    "w2_pass": w2_pass,
                    "feature_decision": feature,
                    "feature_value": feature_value,
                    "k_star": (
                        feature_value.get("k_star")
                        if isinstance(feature_value, dict) else None
                    ),
                    "m15_complete": (
                        feature_value.get("m15_complete")
                        if isinstance(feature_value, dict) else None
                    ),
                    "signal_admitted": signal_admitted,
                    "admitted": signal_admitted,
                    "selected_local": False,
                    "portfolio_accepted": False,
                    "accepted": False,
                    "filled": False,
                    "trade_id": f"H1U:{symbol}:{bar}",
                })
        i = START
        n_trades = 0
        while i < len(prepared.c) - 5:
            side = int(prepared.side[i])
            if side == 0 or not pd.notna(prepared.watr[i]) or prepared.watr[i] < 0.30:
                i += 1
                continue
            trade_id = f"H1U:{symbol}:{i}"
            trade_meta[trade_id] = {
                "source": source,
                "symbol": symbol,
                "bar_index": int(i),
                "z": float(impulse_atr[i]),
            }
            signal_atr = float(prepared.atr[i])
            entry = float(prepared.c[i] - 0.6 * signal_atr * side)
            fill = -1
            for bar in range(i + 1, min(i + 4, len(prepared.c))):
                if (side > 0 and prepared.l[bar] <= entry) or (
                    side < 0 and prepared.h[bar] >= entry
                ):
                    fill = bar
                    break
            open_epoch = _epoch(h1.iloc[i]["time"]) + 3599
            seq += 1
            events.append(_event(
                f"{trade_id}:open", trade_id, symbol, cluster, side,
                open_epoch, seq, "pending_open", price=entry,
                stop_distance=signal_atr, fixed_slippage_r=0.0,
                remaining_fraction=1.0, mark_role="neutral",
            ))
            first_epoch = open_epoch if first_epoch is None else min(first_epoch, open_epoch)
            if fill < 0:
                cancel_epoch = _epoch(h1.iloc[i + 4]["time"])
                seq += 1
                events.append(_event(
                    f"{trade_id}:cancel", trade_id, symbol, cluster, side,
                    cancel_epoch, seq, "pending_cancel", price=entry,
                    stop_distance=signal_atr, fixed_slippage_r=0.0,
                    remaining_fraction=1.0, mark_role="neutral",
                ))
                last_epoch = cancel_epoch if last_epoch is None else max(last_epoch, cancel_epoch)
                i += 4
                continue
            stop = entry - signal_atr * side
            target = entry + target_atr * signal_atr * side
            partial = None
            exit_bar = None
            exit_price = None
            for bar in range(fill, min(fill + 8, len(prepared.c))):
                if side > 0:
                    if prepared.l[bar] <= stop:
                        exit_bar, exit_price = bar, stop
                        break
                    if partial is None and prepared.h[bar] >= entry + signal_atr:
                        partial = bar
                    if prepared.h[bar] >= target:
                        exit_bar, exit_price = bar, target
                        break
                else:
                    if prepared.h[bar] >= stop:
                        exit_bar, exit_price = bar, stop
                        break
                    if partial is None and prepared.l[bar] <= entry - signal_atr:
                        partial = bar
                    if prepared.l[bar] <= target:
                        exit_bar, exit_price = bar, target
                        break
            if exit_bar is None:
                exit_bar = min(fill + 7, len(prepared.c) - 1)
                exit_price = float(prepared.c[exit_bar])
            entry_epoch = _epoch(h1.iloc[fill]["time"])
            seq += 1
            events.append(_event(
                f"{trade_id}:entry", trade_id, symbol, cluster, side,
                entry_epoch, seq, "entry", price=entry,
                stop_distance=signal_atr, fixed_slippage_r=cost,
                remaining_fraction=1.0, mark_role="neutral",
            ))
            for bar in range(fill, exit_bar):
                if partial == bar:
                    seq += 1
                    events.append(_event(
                        f"{trade_id}:partial", trade_id, symbol, cluster, side,
                        _epoch(h1.iloc[bar]["time"]) + 3599, seq, "partial",
                        price=entry + side * signal_atr, stop_distance=signal_atr,
                        fixed_slippage_r=0.0,
                        remaining_fraction=1.0 - partial_fraction,
                        mark_role="favorable",
                    ))
                    continue
                mark_price = float(prepared.c[bar])
                seq += 1
                events.append(_event(
                    f"{trade_id}:mark:{bar}", trade_id, symbol, cluster, side,
                    _epoch(h1.iloc[bar]["time"]) + 3599, seq, "mark",
                    price=mark_price, stop_distance=signal_atr,
                    fixed_slippage_r=0.0,
                    remaining_fraction=(
                        1.0 - partial_fraction
                        if partial is not None and bar > partial else 1.0
                    ),
                    mark_role="favorable" if (mark_price - entry) * side > 0 else "adverse",
                ))
            final_epoch = _epoch(h1.iloc[exit_bar]["time"]) + 3599
            if reference_same_bar_partial and partial == exit_bar:
                seq += 1
                events.append(_event(
                    f"{trade_id}:partial", trade_id, symbol, cluster, side,
                    final_epoch, seq, "partial",
                    price=entry + side * signal_atr, stop_distance=signal_atr,
                    fixed_slippage_r=0.0,
                    remaining_fraction=1.0 - partial_fraction,
                    mark_role="favorable",
                ))
            seq += 1
            events.append(_event(
                f"{trade_id}:final", trade_id, symbol, cluster, side,
                final_epoch, seq, "final", price=float(exit_price),
                stop_distance=signal_atr, fixed_slippage_r=0.0,
                remaining_fraction=0.0, mark_role="neutral",
            ))
            last_epoch = final_epoch if last_epoch is None else max(last_epoch, final_epoch)
            n_trades += 1
            i = exit_bar + 1
        raw_counts[symbol] = n_trades

    grouped = {}
    for event in events:
        grouped.setdefault(event.trade_id, []).append(event)
    extra = sorted(set(SOURCE_TO_FTMO[source] for source in sources) - set(BASE_ORDER))
    order = dict(BASE_ORDER)
    order.update({symbol: 3 + index for index, symbol in enumerate(extra)})
    intervals = []
    for trade_id, rows in grouped.items():
        opening = next(row for row in rows if row.kind == "pending_open")
        ending = max(row.epoch for row in rows if row.kind in {"pending_cancel", "final"})
        intervals.append(
            (
                opening.epoch, order[opening.symbol], trade_id, opening.symbol,
                opening.cluster, ending, trade_meta[trade_id]["z"],
            )
        )
    active = []
    accepted = set()
    contention_epochs = 0
    contention_claimants = 0
    seat_rejections = {"symbol": 0, "cluster": 0, "global": 0}
    by_placement = {}
    for interval in intervals:
        by_placement.setdefault(interval[0], []).append(interval)
    rng = np.random.default_rng(seat_seed) if seat_policy == "random" else None
    for placement in sorted(by_placement):
        active = [item for item in active if item[5] >= placement]
        claimants = by_placement[placement]
        if len(claimants) > 1:
            contention_epochs += 1
            contention_claimants += len(claimants)
        for interval in _ordered_claimants(claimants, seat_policy, rng):
            _, priority, trade_id, symbol, cluster, ending, z_value = interval
            if any(item[3] == symbol for item in active):
                seat_rejections["symbol"] += 1
                continue
            if any(item[4] == cluster for item in active):
                seat_rejections["cluster"] += 1
                continue
            if len(active) >= 2:
                seat_rejections["global"] += 1
                continue
            accepted.add(trade_id)
            active.append(
                (placement, priority, trade_id, symbol, cluster, ending, z_value)
            )
    kept = [event for event in events if event.trade_id in accepted]
    counts = {
        SOURCE_TO_FTMO[source]: sum(
            trade_id in accepted for trade_id in grouped
            if trade_id.startswith(f"H1U:{SOURCE_TO_FTMO[source]}:")
        )
        for source in sources
    }
    first_day = datetime.fromtimestamp(first_epoch, timezone.utc).astimezone(PRAGUE).date()
    last_day = datetime.fromtimestamp(last_epoch, timezone.utc).astimezone(PRAGUE).date()
    tape = PassTape.from_events(kept, first_day=first_day, last_day=last_day)
    if not return_diagnostics:
        return tape, counts

    locally_selected = set(grouped)
    locally_filled = {
        trade_id for trade_id, rows in grouped.items()
        if any(row.kind == "entry" for row in rows)
    }
    accepted_filled = locally_filled & accepted
    for row in raw_signal_rows:
        trade_id = row["trade_id"]
        row["selected_local"] = trade_id in locally_selected
        row["portfolio_accepted"] = trade_id in accepted
        row["accepted"] = row["portfolio_accepted"]
        row["filled"] = trade_id in accepted_filled
    diagnostics = {
        "signal_detection": signal_detection,
        "seat_policy": seat_policy,
        "seat_seed": int(seat_seed),
        "raw_signals": raw_signal_rows,
        "accepted_trade_ids": sorted(accepted),
        "filled_trade_ids": sorted(accepted_filled),
        "locally_selected_trade_ids": sorted(locally_selected),
        "locally_filled_trade_ids": sorted(locally_filled),
        "missing_m15_constituents": int(missing_m15),
        "contention_epochs": int(contention_epochs),
        "contention_claimants": int(contention_claimants),
        "seat_rejections": seat_rejections,
    }
    return tape, counts, diagnostics


if __name__ == "__main__":
    tape, accepted = build_h1_universe_tape(BASE_SOURCES, stress=True)
    print("H1_UNIVERSE_TAPE", tape.n_days, len(tape.events), len(tape.trades), accepted)
