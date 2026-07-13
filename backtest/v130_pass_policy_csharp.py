"""C# execution transport for the frozen v1.30 pass-policy state machine."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import subprocess
import tempfile
from typing import Mapping, Sequence

import numpy as np

from v130_pass_policy import (
    COUNTER_FIELDS, RESULT_DTYPE, SYMBOLS, BootstrapSpec, CompiledBootstrap,
    CompactRun, PassTape, PhaseStatus, POLICIES, RiskPolicy,
)
from v130_risk_policy import SymbolMeta


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "v130_pass_policy_kernel.cs"
EXE = HERE / "v130_pass_policy_kernel.exe"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
KIND_CODE = {
    "pending_open": 0, "pending_cancel": 1, "entry": 2, "mark": 3,
    "swap": 4, "partial": 5, "final": 6,
}
N_COUNTERS = len(COUNTER_FIELDS)
INT_WIDTH = 8 + 2 * N_COUNTERS
FLOAT_WIDTH = 6


@dataclass(frozen=True)
class PrimitiveTape:
    ints: tuple[np.ndarray, ...]
    doubles: tuple[np.ndarray, ...]
    n_days: int
    n_events: int
    max_offset: int
    gather_capacity: int
    n_trades: int


def compile_primitive_tape(tape: PassTape) -> PrimitiveTape:
    symbol_codes = {symbol: i for i, symbol in enumerate(SYMBOLS)}
    cluster_codes = {
        cluster: i for i, cluster in enumerate(sorted({x.cluster for x in tape.trades}))
    }
    trade_codes = {trade.trade_id: i for i, trade in enumerate(tape.trades)}
    names_i = (
        "trade", "offset", "ea_offset", "second", "sequence", "kind",
        "symbol", "cluster", "side", "swap_days", "favorable",
    )
    names_d = ("price", "stop", "slip", "remaining", "swap_cash", "swap_mult")
    iv = {name: [] for name in names_i}
    dv = {name: [] for name in names_d}
    starts = np.empty(tape.n_days, dtype="<i4")
    ends = np.empty(tape.n_days, dtype="<i4")
    counts_by_day: list[dict[int, int]] = []
    max_offset = 0
    for day_index, day in enumerate(tape.days):
        starts[day_index] = len(iv["kind"])
        counts: dict[int, int] = {}
        for trade in day.trades:
            for item in trade.events:
                event = item.event
                offset = int(item.day_offset)
                max_offset = max(max_offset, offset)
                counts[offset] = counts.get(offset, 0) + 1
                iv["trade"].append(trade_codes[trade.trade_id])
                iv["offset"].append(offset)
                iv["ea_offset"].append(int(item.ea_day_offset))
                iv["second"].append(int(item.second_of_day))
                iv["sequence"].append(int(event.sequence))
                iv["kind"].append(KIND_CODE[event.normalized_kind().value])
                iv["symbol"].append(symbol_codes[event.symbol])
                iv["cluster"].append(cluster_codes[event.cluster])
                iv["side"].append(int(event.side))
                iv["swap_days"].append(int(event.swap_days))
                iv["favorable"].append(int(event.mark_role == "favorable"))
                dv["price"].append(float(event.price))
                dv["stop"].append(float(event.stop_distance))
                dv["slip"].append(float(event.fixed_slippage_r))
                dv["remaining"].append(float(event.remaining_fraction))
                dv["swap_cash"].append(float(event.swap_cash_per_lot))
                dv["swap_mult"].append(float(event.swap_multiplier))
        ends[day_index] = len(iv["kind"])
        counts_by_day.append(counts)
    gather_capacity = sum(
        max((counts.get(offset, 0) for counts in counts_by_day), default=0)
        for offset in range(max_offset + 1)
    )
    int_arrays = (starts, ends) + tuple(np.asarray(iv[name], dtype="<i4") for name in names_i)
    double_arrays = tuple(np.asarray(dv[name], dtype="<f8") for name in names_d)
    return PrimitiveTape(
        int_arrays, double_arrays, tape.n_days, len(iv["kind"]), max_offset,
        gather_capacity, len(tape.trades),
    )


def _meta_arrays(metas: Mapping[str, SymbolMeta]) -> tuple[np.ndarray, np.ndarray]:
    ordered = [metas[symbol] for symbol in SYMBOLS]
    doubles = np.asarray([
        value for x in ordered for value in (
            x.trade_tick_size, x.trade_tick_value_loss, x.trade_tick_value_profit,
            x.volume_min, x.volume_step, x.volume_max,
        )
    ], dtype="<f8")
    digits = np.asarray([
        len(f"{x.volume_step:.12f}".rstrip("0").partition(".")[2]) for x in ordered
    ], dtype="<i4")
    return doubles, digits


def _risk_array(policies: Sequence[RiskPolicy]) -> np.ndarray:
    return np.asarray([
        policy.risk_for(phase, symbol)
        for policy in policies for phase in (1, 2) for symbol in SYMBOLS
    ], dtype="<f8")


def compile_backend() -> Path:
    if not CSC.exists():
        raise RuntimeError(f"C# compiler missing: {CSC}")
    if not EXE.exists() or EXE.stat().st_mtime_ns < SOURCE.stat().st_mtime_ns:
        completed = subprocess.run(
            [str(CSC), "/nologo", "/optimize+", "/target:exe", f"/out:{EXE}", str(SOURCE)],
            cwd=HERE, text=True, capture_output=True,
        )
        if completed.returncode:
            raise RuntimeError(
                f"C# compile failed ({completed.returncode})\n{completed.stdout}{completed.stderr}"
            )
    return EXE


def _write_array(handle, array: np.ndarray) -> None:
    contiguous = np.ascontiguousarray(array)
    handle.write(contiguous.tobytes(order="C"))


def _to_runs(path_start: int, policies, ints: np.ndarray, floats: np.ndarray):
    output = {}
    for p, policy in enumerate(policies):
        rows = np.zeros(ints.shape[0], dtype=RESULT_DTYPE)
        values = ints[:, p]
        f = floats[:, p]
        rows["path_id"] = np.arange(path_start, path_start + len(rows), dtype=np.int32)
        rows["p1_status"], rows["p2_status"] = values[:, 0], values[:, 1]
        rows["p1_reason"], rows["p2_reason"] = values[:, 2], values[:, 3]
        rows["both"] = ((values[:, 0] == 1) & (values[:, 1] == 1)).astype(np.uint8)
        rows["firm"] = ((values[:, 0] == 2) | (values[:, 1] == 2)).astype(np.uint8)
        rows["hard"] = ((values[:, 0] == 3) | (values[:, 1] == 3)).astype(np.uint8)
        rows["timeout"] = ((values[:, 0] == 4) | (values[:, 1] == 4)).astype(np.uint8)
        rows["p1_days"], rows["p2_days"] = values[:, 4], values[:, 5]
        rows["total_days"] = values[:, 4] + values[:, 5]
        rows["p1_trading_days"], rows["p2_trading_days"] = values[:, 6], values[:, 7]
        rows["p1_balance"], rows["p2_balance"] = f[:, 0], f[:, 1]
        rows["p1_min_equity"], rows["p2_min_equity"] = f[:, 2], f[:, 3]
        rows["p1_peak_equity"], rows["p2_peak_equity"] = f[:, 4], f[:, 5]
        for c, name in enumerate(COUNTER_FIELDS):
            rows[f"p1_{name}"] = values[:, 8 + c]
            rows[f"p2_{name}"] = values[:, 8 + N_COUNTERS + c]
        output[policy.name] = CompactRun(policy, rows)
    return output


def run_csharp_monte_carlo(
    tape: PassTape,
    metas: Mapping[str, SymbolMeta],
    policies: Sequence[RiskPolicy] = POLICIES,
    *,
    paths: int,
    path_start: int = 0,
    bootstrap: BootstrapSpec = BootstrapSpec(),
):
    exe = compile_backend()
    primitive = compile_primitive_tape(tape)
    compiled_bootstrap = CompiledBootstrap.compile(tape, bootstrap)
    total_days = 7300
    source = np.empty((paths, total_days), dtype="<i4")
    for local in range(paths):
        source[local] = compiled_bootstrap.source_indices(path_start + local, total_days)
    meta_doubles, meta_digits = _meta_arrays(metas)
    with tempfile.TemporaryDirectory(prefix="v130-csharp-") as folder:
        input_path = Path(folder) / "input.bin"
        output_path = Path(folder) / "output.bin"
        with input_path.open("wb") as handle:
            handle.write(struct.pack(
                "<10i", 0x56313330, primitive.n_days, primitive.n_events,
                primitive.max_offset, primitive.gather_capacity,
                primitive.n_trades, paths, total_days, len(policies), len(SYMBOLS),
            ))
            for array in primitive.ints:
                _write_array(handle, array)
            for array in primitive.doubles:
                _write_array(handle, array)
            _write_array(handle, meta_doubles)
            _write_array(handle, meta_digits)
            _write_array(handle, _risk_array(policies))
            _write_array(handle, source)
        completed = subprocess.run(
            [str(exe), str(input_path), str(output_path)], cwd=HERE,
            text=True, capture_output=True,
        )
        if completed.returncode:
            raise RuntimeError(
                f"C# kernel failed ({completed.returncode})\n{completed.stdout}{completed.stderr}"
            )
        raw = output_path.read_bytes()
    expected = paths * len(policies) * (INT_WIDTH * 8 + FLOAT_WIDTH * 8)
    if len(raw) != expected:
        raise RuntimeError(f"C# output length mismatch: {len(raw)} != {expected}")
    cursor = 0
    ints = np.empty((paths, len(policies), INT_WIDTH), dtype="<i8")
    floats = np.empty((paths, len(policies), FLOAT_WIDTH), dtype="<f8")
    for path in range(paths):
        for policy in range(len(policies)):
            stop = cursor + INT_WIDTH * 8
            ints[path, policy] = np.frombuffer(raw[cursor:stop], dtype="<i8")
            cursor = stop
            stop = cursor + FLOAT_WIDTH * 8
            floats[path, policy] = np.frombuffer(raw[cursor:stop], dtype="<f8")
            cursor = stop
    return _to_runs(path_start, policies, ints, floats)
