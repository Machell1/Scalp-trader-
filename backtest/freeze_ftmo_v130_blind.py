"""Freeze the preregistered FTMO M15 lineage-blind frames without scoring them.

Protocol: docs/V130_RISK_POLICY_SPEC_2026-07-11.md
SHA256: 8f2043af550df082e493a3d295f305d014c4083115b96bfbdfe61855f860e30a

This exporter is deliberately outcome-blind: it retrieves the exact registered
UTC ranges, validates market-data integrity, writes round-trip-safe CSV plus the
raw NumPy structured arrays, and builds a SHA256 manifest. It never imports a
strategy/backtest module and never computes a signal, trade, expectancy, win
rate, or pass probability.
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
OUT_DIR = HERE / "data" / "ftmoM15_blind_20260711"
MANIFEST = HERE / "ftmo_v130_blind_20260711.manifest.sha256"
SPEC = HERE.parent / "docs" / "V130_RISK_POLICY_SPEC_2026-07-11.md"
TERMINAL = Path(r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe")
EXPECTED_SERVER = "FTMO-Demo"
EXPECTED_COMPANY = "FTMO Global Markets Ltd"
EXPECTED_TOTAL = 99_999
PROTOCOL_SHA256 = "8f2043af550df082e493a3d295f305d014c4083115b96bfbdfe61855f860e30a"
INTERNAL_MANIFEST = "MANIFEST.sha256"

SPLITS: dict[str, dict[str, dict[str, Any]]] = {
    "US30.cash": {
        "holdout": {
            "start": "2022-04-13T23:15:00Z",
            "end": "2023-12-22T09:15:00Z",
            "rows": 39_999,
        },
        "confirmation": {
            "start": "2023-12-22T09:30:00Z",
            "end": "2025-04-02T20:45:00Z",
            "rows": 30_000,
        },
        "mined": {
            "start": "2025-04-02T21:00:00Z",
            "end": "2026-07-10T23:45:00Z",
            "rows": 30_000,
        },
    },
    "US100.cash": {
        "holdout": {
            "start": "2022-04-14T01:30:00Z",
            "end": "2023-12-22T10:30:00Z",
            "rows": 39_999,
        },
        "confirmation": {
            "start": "2023-12-22T10:45:00Z",
            "end": "2025-04-02T22:00:00Z",
            "rows": 30_000,
        },
        "mined": {
            "start": "2025-04-02T22:15:00Z",
            "end": "2026-07-10T23:45:00Z",
            "rows": 30_000,
        },
    },
    "JP225.cash": {
        "holdout": {
            "start": "2022-04-13T16:00:00Z",
            "end": "2023-12-22T15:30:00Z",
            "rows": 39_999,
        },
        "confirmation": {
            "start": "2023-12-22T15:45:00Z",
            "end": "2025-04-02T23:00:00Z",
            "rows": 30_000,
        },
        "mined": {
            "start": "2025-04-02T23:15:00Z",
            "end": "2026-07-10T23:45:00Z",
            "rows": 30_000,
        },
    },
}

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
    "volume_limit",
    "trade_stops_level",
    "trade_freeze_level",
    "filling_mode",
    "order_mode",
    "currency_base",
    "currency_profit",
    "currency_margin",
)

EXPECTED_DATA_FILES = frozenset(
    {
        "US30_cash_M15_99999.npy",
        "US30_cash_M15_99999.csv",
        "US100_cash_M15_99999.npy",
        "US100_cash_M15_99999.csv",
        "JP225_cash_M15_99999.npy",
        "JP225_cash_M15_99999.csv",
        "METADATA.json",
        "SPLIT.json",
        "INTEGRITY.json",
    }
)


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso_utc(epoch: int) -> str:
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_protocol_hash() -> None:
    """Recompute the committed UTF-8/LF protocol prefix before evidence access."""
    if not SPEC.is_file():
        raise RuntimeError(f"protocol missing: {SPEC}")
    rel = SPEC.relative_to(HERE.parent).as_posix()
    if subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", rel], cwd=HERE.parent
    ).returncode != 0:
        raise RuntimeError("working protocol differs from committed HEAD")
    try:
        raw = subprocess.check_output(
            ["git", "show", f"HEAD:{rel}"], cwd=HERE.parent
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("protocol is not committed at HEAD") from exc
    if b"\r" in raw:
        raise RuntimeError("committed protocol is not canonical UTF-8/LF")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("committed protocol is not UTF-8") from exc
    marker = b"\n\n**Recorded protocol SHA256:**"
    boundary = raw.find(marker)
    if boundary < 0:
        raise RuntimeError("protocol hash boundary missing")
    prefix = raw[: boundary + 1]
    actual = hashlib.sha256(prefix).hexdigest()
    match = re.search(r"\*\*Recorded protocol SHA256:\*\* `([0-9a-f]{64})`", text)
    if match is None:
        raise RuntimeError("recorded protocol SHA256 line missing or malformed")
    recorded = match.group(1)
    if recorded != PROTOCOL_SHA256 or actual != PROTOCOL_SHA256:
        raise RuntimeError(
            f"protocol hash mismatch: constant={PROTOCOL_SHA256} "
            f"recorded={recorded} recomputed={actual}"
        )


def json_ready(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path: Path, payload: Any) -> None:
    text = json.dumps(
        payload, indent=2, sort_keys=True, default=json_ready, allow_nan=False
    ) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def validate_rates(symbol: str, rates: np.ndarray) -> dict[str, Any]:
    if len(rates) != EXPECTED_TOTAL:
        raise RuntimeError(f"{symbol}: expected {EXPECTED_TOTAL} rows, got {len(rates)}")
    times = rates["time"].astype(np.int64)
    deltas = np.diff(times)
    if not np.all(deltas > 0):
        raise RuntimeError(f"{symbol}: epochs are not strictly increasing and unique")

    o = rates["open"].astype(float)
    h = rates["high"].astype(float)
    l = rates["low"].astype(float)
    c = rates["close"].astype(float)
    if not np.all(np.isfinite(np.column_stack((o, h, l, c)))):
        raise RuntimeError(f"{symbol}: non-finite OHLC value")
    if not np.all((l <= o) & (l <= c) & (h >= o) & (h >= c) & (l <= h)):
        raise RuntimeError(f"{symbol}: OHLC invariant failure")
    if np.any(rates["spread"].astype(np.int64) < 0):
        raise RuntimeError(f"{symbol}: negative spread")
    if np.any(rates["tick_volume"].astype(np.int64) < 0):
        raise RuntimeError(f"{symbol}: negative tick volume")

    gap_counts = Counter(int(x) for x in deltas)
    return {
        "rows": int(len(rates)),
        "first_epoch": int(times[0]),
        "first_utc": iso_utc(times[0]),
        "last_epoch": int(times[-1]),
        "last_utc": iso_utc(times[-1]),
        "unique_epochs": int(len(np.unique(times))),
        "expected_m15_delta_rows": int(np.sum(deltas == 900)),
        "non_900_gap_rows": int(np.sum(deltas != 900)),
        "gap_seconds_counts": {str(k): int(v) for k, v in sorted(gap_counts.items())},
        "ohlc_invariants": "OK",
        "spread_nonnegative": "OK",
        "tick_volume_nonnegative": "OK",
    }


def validate_splits(symbol: str, rates: np.ndarray) -> dict[str, Any]:
    epochs = rates["time"].astype(np.int64)
    result: dict[str, Any] = {}
    for name, spec in SPLITS[symbol].items():
        start = int(parse_utc(spec["start"]).timestamp())
        end = int(parse_utc(spec["end"]).timestamp())
        selected = epochs[(epochs >= start) & (epochs <= end)]
        if len(selected) != spec["rows"]:
            raise RuntimeError(
                f"{symbol}/{name}: expected {spec['rows']} rows, got {len(selected)}"
            )
        if int(selected[0]) != start or int(selected[-1]) != end:
            raise RuntimeError(f"{symbol}/{name}: exact UTC endpoints do not match")
        result[name] = {
            **spec,
            "start_epoch": start,
            "end_epoch": end,
            "actual_rows": int(len(selected)),
        }
    if sum(int(v["actual_rows"]) for v in result.values()) != EXPECTED_TOTAL:
        raise RuntimeError(f"{symbol}: split rows do not cover the frozen array")
    return result


def write_csv(path: Path, rates: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_FIELDS)
        for row in rates:
            writer.writerow(
                (
                    str(int(row["time"])),
                    iso_utc(int(row["time"])),
                    format(float(row["open"]), ".17g"),
                    format(float(row["high"]), ".17g"),
                    format(float(row["low"]), ".17g"),
                    format(float(row["close"]), ".17g"),
                    str(int(row["tick_volume"])),
                    str(int(row["spread"])),
                    str(int(row["real_volume"])),
                )
            )


def verify_serialization(npy_path: Path, csv_path: Path, rates: np.ndarray) -> None:
    loaded = np.load(npy_path, allow_pickle=False)
    if loaded.dtype != rates.dtype or not np.array_equal(loaded, rates):
        raise RuntimeError(f"NPY round-trip mismatch: {npy_path.name}")

    numeric_float = ("open", "high", "low", "close")
    numeric_int = ("time", "tick_volume", "spread", "real_volume")
    rows = 0
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise RuntimeError(f"CSV header mismatch: {csv_path.name}")
        for rows, record in enumerate(reader, start=1):
            source = rates[rows - 1]
            if int(record["time_epoch"]) != int(source["time"]):
                raise RuntimeError(f"CSV epoch mismatch: {csv_path.name} row {rows}")
            if record["time_utc"] != iso_utc(int(source["time"])):
                raise RuntimeError(f"CSV UTC mismatch: {csv_path.name} row {rows}")
            for field in numeric_float:
                if float(record[field]) != float(source[field]):
                    raise RuntimeError(
                        f"CSV float mismatch: {csv_path.name} row {rows} {field}"
                    )
            for field in numeric_int:
                csv_name = "time_epoch" if field == "time" else field
                if int(record[csv_name]) != int(source[field]):
                    raise RuntimeError(
                        f"CSV integer mismatch: {csv_path.name} row {rows} {field}"
                    )
    if rows != len(rates):
        raise RuntimeError(f"CSV row count mismatch: {csv_path.name}: {rows}")


def manifest_text(directory: Path) -> str:
    entries = list(directory.iterdir())
    invalid_types = sorted(
        p.name for p in entries if not p.is_file() or p.is_symlink()
    )
    if invalid_types:
        raise RuntimeError(f"non-regular freeze entries: {invalid_types}")
    actual = {p.name for p in entries}
    if actual != EXPECTED_DATA_FILES:
        missing = sorted(EXPECTED_DATA_FILES - actual)
        extra = sorted(actual - EXPECTED_DATA_FILES)
        raise RuntimeError(f"freeze file-set mismatch: missing={missing} extra={extra}")
    lines = []
    for name in sorted(EXPECTED_DATA_FILES, key=str.lower):
        path = directory / name
        rel = (OUT_DIR.relative_to(HERE) / name).as_posix()
        lines.append(f"{file_sha256(path)}  {rel}\n")
    return "".join(lines)


def parse_manifest(text: str) -> dict[str, str]:
    rows = text.splitlines()
    if len(rows) != len(EXPECTED_DATA_FILES):
        raise RuntimeError(
            f"manifest row count {len(rows)} != {len(EXPECTED_DATA_FILES)}"
        )
    parsed: dict[str, str] = {}
    expected_rel = {
        (OUT_DIR.relative_to(HERE) / name).as_posix(): name
        for name in EXPECTED_DATA_FILES
    }
    for row in rows:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", row)
        if match is None:
            raise RuntimeError(f"malformed manifest row: {row!r}")
        digest, rel = match.groups()
        if rel in parsed:
            raise RuntimeError(f"duplicate manifest path: {rel}")
        if rel not in expected_rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise RuntimeError(f"unexpected manifest path: {rel}")
        parsed[rel] = digest
    if set(parsed) != set(expected_rel):
        raise RuntimeError("manifest path set is incomplete")
    return parsed


def verify_directory(directory: Path, manifest_body: str) -> None:
    parsed = parse_manifest(manifest_body)
    entries = list(directory.iterdir())
    invalid_types = sorted(
        p.name for p in entries if not p.is_file() or p.is_symlink()
    )
    if invalid_types:
        raise RuntimeError(f"non-regular sealed entries: {invalid_types}")
    actual_files = {p.name for p in entries}
    expected_files = EXPECTED_DATA_FILES | {INTERNAL_MANIFEST}
    if actual_files != expected_files:
        raise RuntimeError(
            f"sealed directory file-set mismatch: "
            f"missing={sorted(expected_files - actual_files)} "
            f"extra={sorted(actual_files - expected_files)}"
        )
    root = directory.resolve()
    for rel, expected in parsed.items():
        name = Path(rel).name
        path = (directory / name).resolve()
        if path.parent != root:
            raise RuntimeError(f"manifest path escapes sealed directory: {rel}")
        actual = file_sha256(path)
        if actual != expected:
            raise RuntimeError(f"manifest mismatch: {rel}: {actual} != {expected}")


def publish_external_manifest() -> None:
    verify_protocol_hash()
    internal = OUT_DIR / INTERNAL_MANIFEST
    if not internal.is_file():
        raise RuntimeError(f"internal manifest missing: {internal}")
    body = internal.read_text(encoding="ascii")
    verify_directory(OUT_DIR, body)
    if MANIFEST.exists():
        if MANIFEST.read_text(encoding="ascii") != body:
            raise RuntimeError("tracked and internal manifests differ")
        return
    temp = OUT_DIR.parent / (
        f".{MANIFEST.name}.{os.getpid()}.{datetime.now(timezone.utc).timestamp():.6f}.tmp"
    )
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="ascii", newline="\n") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, MANIFEST)
        except FileExistsError:
            if MANIFEST.read_text(encoding="ascii") != body:
                raise RuntimeError("concurrent tracked manifest differs")
    finally:
        temp.unlink(missing_ok=True)


def verify_manifest() -> None:
    verify_protocol_hash()
    if not OUT_DIR.is_dir():
        raise RuntimeError(f"sealed directory missing: {OUT_DIR}")
    internal = OUT_DIR / INTERNAL_MANIFEST
    if not internal.is_file() or not MANIFEST.is_file():
        raise RuntimeError("internal or tracked manifest missing")
    body = internal.read_text(encoding="ascii")
    if MANIFEST.read_text(encoding="ascii") != body:
        raise RuntimeError("tracked and internal manifests differ")
    verify_directory(OUT_DIR, body)
    print(
        f"verified FTMO blind freeze {len(EXPECTED_DATA_FILES)} OK, "
        "0 missing, 0 mismatched, 0 extra"
    )


def freeze() -> None:
    import MetaTrader5 as mt5

    verify_protocol_hash()
    repo = HERE.parent
    exporter_rel = Path(__file__).resolve().relative_to(repo).as_posix()
    if subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", exporter_rel], cwd=repo
    ).returncode != 0:
        raise RuntimeError("exporter working tree differs from committed HEAD")
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        exporter_blob = subprocess.check_output(
            ["git", "show", f"HEAD:{exporter_rel}"], cwd=repo
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("exporter is not committed at HEAD") from exc

    OUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    if OUT_DIR.exists() or MANIFEST.exists():
        raise RuntimeError("sealed destination or tracked manifest already exists")
    staging = Path(
        tempfile.mkdtemp(prefix=f".{OUT_DIR.name}.", dir=str(OUT_DIR.parent))
    )
    published = False
    mt5_initialized = False
    try:
        if not mt5.initialize(path=str(TERMINAL), timeout=30_000):
            raise RuntimeError(f"MetaTrader5 initialize failed: {mt5.last_error()}")
        mt5_initialized = True
        account = mt5.account_info()
        terminal = mt5.terminal_info()
        if account is None or terminal is None:
            raise RuntimeError(f"terminal/account unavailable: {mt5.last_error()}")
        if account.server != EXPECTED_SERVER or account.company != EXPECTED_COMPANY:
            raise RuntimeError(
                f"wrong terminal venue: server={account.server!r} "
                f"company={account.company!r}"
            )

        metadata: dict[str, Any] = {
            "retrieval_utc": datetime.now(timezone.utc).isoformat(),
            "server": account.server,
            "company": account.company,
            "terminal_path": str(TERMINAL),
            "terminal_build": int(terminal.build),
            "mt5_version": list(mt5.version()),
            "metatrader5_python_version": getattr(mt5, "__version__", "unknown"),
            "python_version": sys.version,
            "platform": platform.platform(),
            "timeframe": "M15",
            "expected_rows_per_symbol": EXPECTED_TOTAL,
            "symbols": {},
            "protocol_sha256": PROTOCOL_SHA256,
            "exporter_git_commit": head,
            "exporter_git_blob_sha256": hashlib.sha256(exporter_blob).hexdigest(),
            "exporter_worktree_sha256": file_sha256(Path(__file__).resolve()),
        }
        integrity: dict[str, Any] = {}
        split_payload: dict[str, Any] = {
            "policy": "absolute UTC inclusive endpoints; no position offsets",
            "symbols": {},
        }

        for symbol, split_spec in SPLITS.items():
            full_start = parse_utc(split_spec["holdout"]["start"])
            full_end = parse_utc(split_spec["mined"]["end"])
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, full_start, full_end)
            if rates is None:
                raise RuntimeError(f"{symbol}: copy_rates_range failed: {mt5.last_error()}")
            rates = np.asarray(rates)
            integrity[symbol] = validate_rates(symbol, rates)
            split_payload["symbols"][symbol] = validate_splits(symbol, rates)

            info = mt5.symbol_info(symbol)
            if info is None:
                raise RuntimeError(f"{symbol}: symbol_info unavailable")
            metadata["symbols"][symbol] = {
                key: getattr(info, key) for key in SYMBOL_FIELDS
            }

            stem = symbol.replace(".", "_")
            npy_path = staging / f"{stem}_M15_99999.npy"
            csv_path = staging / f"{stem}_M15_99999.csv"
            np.save(npy_path, rates, allow_pickle=False)
            write_csv(csv_path, rates)
            verify_serialization(npy_path, csv_path, rates)
            integrity[symbol]["npy_roundtrip"] = "OK"
            integrity[symbol]["csv_roundtrip"] = "OK"
            print(
                f"froze {symbol}: {len(rates)} rows "
                f"{integrity[symbol]['first_utc']}..{integrity[symbol]['last_utc']}"
            )

        write_json(staging / "METADATA.json", metadata)
        write_json(staging / "SPLIT.json", split_payload)
        write_json(staging / "INTEGRITY.json", integrity)
        body = manifest_text(staging)
        with (staging / INTERNAL_MANIFEST).open(
            "x", encoding="ascii", newline="\n"
        ) as handle:
            handle.write(body)
        verify_directory(staging, body)

        if OUT_DIR.exists():
            raise RuntimeError("sealed destination appeared during staging")
        staging.rename(OUT_DIR)
        published = True
        publish_external_manifest()
    finally:
        if mt5_initialized:
            mt5.shutdown()
        if not published and staging.exists():
            resolved = staging.resolve()
            parent = OUT_DIR.parent.resolve()
            if resolved.parent != parent or not resolved.name.startswith(
                f".{OUT_DIR.name}."
            ):
                raise RuntimeError(f"refusing unsafe staging cleanup: {resolved}")
            shutil.rmtree(resolved)

    verify_manifest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify the immutable files against the tracked SHA256 manifest",
    )
    parser.add_argument(
        "--publish-manifest",
        action="store_true",
        help="publish a missing tracked manifest from a verified sealed directory",
    )
    args = parser.parse_args()
    if args.verify and args.publish_manifest:
        parser.error("choose only one of --verify or --publish-manifest")
    if args.verify:
        verify_manifest()
    elif args.publish_manifest:
        publish_external_manifest()
        verify_manifest()
    else:
        freeze()


if __name__ == "__main__":
    main()
