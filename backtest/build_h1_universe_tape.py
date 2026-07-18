"""Build cost-matched H1 account tapes for universe-admission portfolios."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from parity_engine import START, prep_symbol
from run_h1_universe_screen import BASE_SOURCES, META_PATH, load_symbol
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
    tp_mult: float = 2.0, partial_r: float = 1.0, bank_frac: float = 0.5,
) -> tuple[PassTape, dict[str, int]]:
    if not set(BASE_SOURCES).issubset(sources):
        raise ValueError("the live H1 control trio must remain in every portfolio")
    snapshot = json.loads(META_PATH.read_text(encoding="utf-8"))
    events = []
    seq = 0
    first_epoch = None
    last_epoch = None
    raw_counts = {}
    for source in sources:
        loaded = load_symbol(source, snapshot)
        h1 = loaded.h1
        if cost_mode == "registered":
            cost_e1 = loaded.cost_e1
        elif cost_mode == "legacy_source":
            cost_e1 = float(real_cost_per_side(h1))
        else:
            raise ValueError(f"unknown cost mode: {cost_mode}")
        cost = cost_e1 * (2.0 if stress else 1.0)
        prepared = prep_symbol(h1, cost, source)
        symbol = loaded.ftmo_symbol
        cluster = CLUSTERS[symbol]
        i = START
        n_trades = 0
        while i < len(prepared.c) - 5:
            side = int(prepared.side[i])
            if side == 0 or not pd.notna(prepared.watr[i]) or prepared.watr[i] < 0.30:
                i += 1
                continue
            trade_id = f"H1U:{symbol}:{i}"
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
            target = entry + tp_mult * signal_atr * side
            partial = None
            exit_bar = None
            exit_price = None
            for bar in range(fill, min(fill + 8, len(prepared.c))):
                if side > 0:
                    if prepared.l[bar] <= stop:
                        exit_bar, exit_price = bar, stop
                        break
                    if partial is None and prepared.h[bar] >= entry + partial_r * signal_atr:
                        partial = bar
                    if prepared.h[bar] >= target:
                        exit_bar, exit_price = bar, target
                        break
                else:
                    if prepared.h[bar] >= stop:
                        exit_bar, exit_price = bar, stop
                        break
                    if partial is None and prepared.l[bar] <= entry - partial_r * signal_atr:
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
                        price=entry + side * partial_r * signal_atr, stop_distance=signal_atr,
                        fixed_slippage_r=0.0, remaining_fraction=1.0 - bank_frac,
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
                    remaining_fraction=(1.0 - bank_frac) if partial is not None and bar > partial else 1.0,
                    mark_role="favorable" if (mark_price - entry) * side > 0 else "adverse",
                ))
            final_epoch = _epoch(h1.iloc[exit_bar]["time"]) + 3599
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
            (opening.epoch, order[opening.symbol], trade_id, opening.symbol, opening.cluster, ending)
        )
    active = []
    accepted = set()
    for placement, priority, trade_id, symbol, cluster, ending in sorted(intervals):
        active = [item for item in active if item[5] >= placement]
        if any(item[3] == symbol for item in active):
            continue
        if any(item[4] == cluster for item in active) or len(active) >= 2:
            continue
        accepted.add(trade_id)
        active.append((placement, priority, trade_id, symbol, cluster, ending))
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
    return PassTape.from_events(kept, first_day=first_day, last_day=last_day), counts


if __name__ == "__main__":
    tape, accepted = build_h1_universe_tape(BASE_SOURCES, stress=True)
    print("H1_UNIVERSE_TAPE", tape.n_days, len(tape.events), len(tape.trades), accepted)
