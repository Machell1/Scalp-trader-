"""Freeze an outcome-blind, immutable US100.cash M1 terminal snapshot.

Protocol: docs/VIDEO_M1_FREEZE_AMENDMENT_2026-07-13.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "data" / "ftmoM1_us100_video_20260713"
MANIFEST = HERE / "ftmo_m1_us100_video_20260713.manifest.sha256"
SPEC = HERE.parent / "docs" / "VIDEO_M1_FREEZE_AMENDMENT_2026-07-13.md"
TERMINAL = Path(r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe")
EXPECTED_SERVER = "FTMO-Demo"
EXPECTED_COMPANY = "FTMO Global Markets Ltd"
SYMBOL = "US100.cash"
END_UTC = datetime(2026, 7, 10, 23, 59, tzinfo=timezone.utc)
EXPECTED_ROWS = 98_807
PROTOCOL_SHA256 = "0dc3fd9521abfe00b7425c02191520bbf7440346267bd2a0b95a24f497a38e9c"
INTERNAL_MANIFEST = "MANIFEST.sha256"
DATA_FILES = frozenset(
    {
        "US100_cash_M1_98807.npy",
        "US100_cash_M1_98807.csv",
        "METADATA.json",
        "INTEGRITY.json",
    }
)
CSV_FIELDS = (
    "time_epoch",
    "time_utc",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)
SYMBOL_FIELDS = (
    "digits",
    "point",
    "trade_tick_value",
    "trade_tick_value_profit",
    "trade_tick_value_loss",
    "trade_tick_size",
    "trade_contract_size",
    "volume_min",
    "volume_max",
    "volume_step",
    "trade_stops_level",
    "trade_freeze_level",
    "filling_mode",
    "order_mode",
    "currency_base",
    "currency_profit",
    "currency_margin",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_utc(epoch: int) -> str:
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def verify_protocol_hash() -> None:
    rel = SPEC.relative_to(HERE.parent).as_posix()
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=HERE.parent).returncode:
        raise RuntimeError("protocol working tree differs from committed HEAD")
    raw = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=HERE.parent)
    if b"\r" in raw:
        raise RuntimeError("committed protocol is not canonical UTF-8/LF")
    marker = b"\n\n**Recorded protocol SHA256:**"
    boundary = raw.find(marker)
    if boundary < 0:
        raise RuntimeError("protocol hash boundary missing")
    actual = hashlib.sha256(raw[: boundary + 1]).hexdigest()
    text = raw.decode("utf-8")
    recorded = re.search(r"\*\*Recorded protocol SHA256:\*\* `([0-9a-f]{64})`", text)
    if recorded is None or actual != PROTOCOL_SHA256 or recorded.group(1) != PROTOCOL_SHA256:
        raise RuntimeError("protocol hash mismatch")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def json_value(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def validate_rates(rates: np.ndarray) -> dict[str, Any]:
    if len(rates) != EXPECTED_ROWS:
        raise RuntimeError(f"{SYMBOL}: expected {EXPECTED_ROWS} rows, got {len(rates)}")
    required = {"time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"}
    if rates.dtype.names is None or not required.issubset(rates.dtype.names):
        raise RuntimeError(f"{SYMBOL}: unexpected MT5 bar schema {rates.dtype.names}")
    times = rates["time"].astype(np.int64)
    deltas = np.diff(times)
    if not np.all(deltas > 0):
        raise RuntimeError(f"{SYMBOL}: epochs are not strictly increasing and unique")
    values = np.column_stack([rates[key].astype(float) for key in ("open", "high", "low", "close")])
    if not np.all(np.isfinite(values)):
        raise RuntimeError(f"{SYMBOL}: non-finite OHLC")
    o, h, l, c = values.T
    if not np.all((l <= o) & (l <= c) & (h >= o) & (h >= c) & (l <= h)):
        raise RuntimeError(f"{SYMBOL}: OHLC invariant failure")
    if np.any(rates["spread"].astype(np.int64) < 0) or np.any(rates["tick_volume"].astype(np.int64) < 0):
        raise RuntimeError(f"{SYMBOL}: negative spread or tick volume")
    gap_counts = Counter(int(value) for value in deltas)
    return {
        "rows": int(len(rates)),
        "first_epoch": int(times[0]),
        "first_utc": iso_utc(times[0]),
        "last_epoch": int(times[-1]),
        "last_utc": iso_utc(times[-1]),
        "unique_epochs": int(len(np.unique(times))),
        "expected_m1_delta_rows": int(np.sum(deltas == 60)),
        "non_60_gap_rows": int(np.sum(deltas != 60)),
        "gap_seconds_counts": {str(key): int(value) for key, value in sorted(gap_counts.items())},
        "ohlc_invariants": "OK",
        "spread_nonnegative": "OK",
        "tick_volume_nonnegative": "OK",
    }


def write_csv(path: Path, rates: np.ndarray) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for bar in rates:
            epoch = int(bar["time"])
            writer.writerow({
                "time_epoch": epoch, "time_utc": iso_utc(epoch),
                "open": repr(float(bar["open"])), "high": repr(float(bar["high"])),
                "low": repr(float(bar["low"])), "close": repr(float(bar["close"])),
                "tick_volume": int(bar["tick_volume"]), "spread": int(bar["spread"]),
                "real_volume": int(bar["real_volume"]),
            })


def verify_serialization(npy_path: Path, csv_path: Path, rates: np.ndarray) -> None:
    recovered = np.load(npy_path, allow_pickle=False)
    if recovered.dtype != rates.dtype or not np.array_equal(recovered, rates):
        raise RuntimeError("NPY round-trip mismatch")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(rates):
        raise RuntimeError("CSV round-trip row-count mismatch")
    for index, (row, bar) in enumerate(zip(rows, rates, strict=True)):
        expected = (int(bar["time"]), float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"]), int(bar["tick_volume"]), int(bar["spread"]), int(bar["real_volume"]))
        actual = (int(row["time_epoch"]), float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), int(row["tick_volume"]), int(row["spread"]), int(row["real_volume"]))
        if actual != expected or row["time_utc"] != iso_utc(expected[0]):
            raise RuntimeError(f"CSV round-trip mismatch at row {index}")


def manifest_text(directory: Path) -> str:
    entries = {path.name for path in directory.iterdir()}
    if entries != DATA_FILES:
        raise RuntimeError(f"freeze file-set mismatch: actual={sorted(entries)}")
    if any(not path.is_file() or path.is_symlink() for path in directory.iterdir()):
        raise RuntimeError("freeze contains a non-regular or symlinked file")
    return "".join(f"{file_sha256(directory / name)}  {(OUT_DIR.relative_to(HERE) / name).as_posix()}\n" for name in sorted(DATA_FILES, key=str.lower))


def verify_directory(directory: Path, manifest_body: str) -> None:
    expected = DATA_FILES | {INTERNAL_MANIFEST}
    paths = list(directory.iterdir())
    actual = {path.name for path in paths}
    if actual != expected:
        raise RuntimeError(f"sealed file-set mismatch: missing={sorted(expected - actual)} extra={sorted(actual - expected)}")
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise RuntimeError("sealed freeze contains a non-regular or symlinked file")
    rows = manifest_body.splitlines()
    if len(rows) != len(DATA_FILES):
        raise RuntimeError("manifest row count mismatch")
    seen: set[str] = set()
    for row in rows:
        match = re.fullmatch(r"([0-9a-f]{64})  data/ftmoM1_us100_video_20260713/([^/]+)", row)
        if match is None or match.group(2) not in DATA_FILES:
            raise RuntimeError(f"malformed manifest row: {row!r}")
        if match.group(2) in seen:
            raise RuntimeError(f"duplicate manifest file: {match.group(2)}")
        seen.add(match.group(2))
        if file_sha256(directory / match.group(2)) != match.group(1):
            raise RuntimeError(f"manifest mismatch: {match.group(2)}")
    if seen != DATA_FILES:
        raise RuntimeError("manifest file set is incomplete")


def terminal_is_running() -> bool:
    completed = subprocess.run(["tasklist", "/FI", "IMAGENAME eq terminal64.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=False)
    return any("terminal64.exe" in line.lower() for line in completed.stdout.splitlines())


def freeze() -> None:
    import MetaTrader5 as mt5

    verify_protocol_hash()
    repo = HERE.parent
    rel = Path(__file__).resolve().relative_to(repo).as_posix()
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=repo).returncode:
        raise RuntimeError("freezer working tree differs from committed HEAD")
    if OUT_DIR.exists() or MANIFEST.exists():
        raise RuntimeError("sealed destination or tracked manifest already exists")
    if not terminal_is_running():
        raise RuntimeError("terminal64.exe is not already running; refusing to launch a terminal")
    staging = Path(tempfile.mkdtemp(prefix=f".{OUT_DIR.name}.", dir=str(OUT_DIR.parent)))
    initialized = False
    published = False
    try:
        if not mt5.initialize(path=str(TERMINAL), timeout=30_000):
            raise RuntimeError(f"MetaTrader5 initialize failed: {mt5.last_error()}")
        initialized = True
        account, terminal = mt5.account_info(), mt5.terminal_info()
        if account is None or terminal is None:
            raise RuntimeError(f"terminal/account unavailable: {mt5.last_error()}")
        if account.server != EXPECTED_SERVER or account.company != EXPECTED_COMPANY:
            raise RuntimeError(f"wrong terminal venue: server={account.server!r} company={account.company!r}")
        rates = mt5.copy_rates_from(SYMBOL, mt5.TIMEFRAME_M1, END_UTC, EXPECTED_ROWS)
        if rates is None:
            raise RuntimeError(f"{SYMBOL}: copy_rates_from failed: {mt5.last_error()}")
        rates = np.asarray(rates)
        integrity = validate_rates(rates)
        info = mt5.symbol_info(SYMBOL)
        if info is None:
            raise RuntimeError(f"{SYMBOL}: symbol_info unavailable")
        metadata = {
            "retrieval_utc": datetime.now(timezone.utc).isoformat(), "read_only_terminal_calls": ["initialize", "account_info", "terminal_info", "version", "copy_rates_from", "symbol_info", "last_error", "shutdown"],
            "server": account.server, "company": account.company, "terminal_path": str(TERMINAL), "terminal_build": int(terminal.build), "mt5_version": list(mt5.version()), "metatrader5_python_version": getattr(mt5, "__version__", "unknown"), "python_version": sys.version, "platform": platform.platform(), "symbol": SYMBOL, "timeframe": "M1", "requested_end_utc": END_UTC.isoformat(), "requested_rows": EXPECTED_ROWS,
            "protocol_sha256": PROTOCOL_SHA256, "symbol_info": {field: json_value(getattr(info, field)) for field in SYMBOL_FIELDS},
        }
        npy_path, csv_path = staging / "US100_cash_M1_98807.npy", staging / "US100_cash_M1_98807.csv"
        np.save(npy_path, rates, allow_pickle=False)
        write_csv(csv_path, rates)
        verify_serialization(npy_path, csv_path, rates)
        integrity["npy_roundtrip"] = "OK"
        integrity["csv_roundtrip"] = "OK"
        write_json(staging / "METADATA.json", metadata)
        write_json(staging / "INTEGRITY.json", integrity)
        body = manifest_text(staging)
        (staging / INTERNAL_MANIFEST).write_text(body, encoding="ascii", newline="\n")
        verify_directory(staging, body)
        staging.rename(OUT_DIR)
        published = True
        MANIFEST.write_text(body, encoding="ascii", newline="\n")
        verify_directory(OUT_DIR, body)
        print(f"froze {SYMBOL}: {integrity['rows']} rows {integrity['first_utc']}..{integrity['last_utc']}")
        print(f"verified video M1 freeze {len(DATA_FILES)} OK, 0 missing, 0 mismatched, 0 extra")
    finally:
        if initialized:
            mt5.shutdown()
        if not published and staging.exists():
            shutil.rmtree(staging)


def verify() -> None:
    verify_protocol_hash()
    if not OUT_DIR.is_dir() or not MANIFEST.is_file():
        raise RuntimeError("sealed directory or tracked manifest missing")
    body = MANIFEST.read_text(encoding="ascii")
    internal = OUT_DIR / INTERNAL_MANIFEST
    if not internal.is_file() or internal.read_text(encoding="ascii") != body:
        raise RuntimeError("internal and tracked manifests differ")
    verify_directory(OUT_DIR, body)
    print(f"verified video M1 freeze {len(DATA_FILES)} OK, 0 missing, 0 mismatched, 0 extra")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    verify() if args.verify else freeze()


if __name__ == "__main__":
    main()
