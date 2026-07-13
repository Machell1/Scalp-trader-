"""Export a sanitized, immutable Momentum Pullback execution-history fixture.

The exporter is deliberately read-only with respect to MT5: it reads broker
history and EA telemetry, strips account/path/comment identifiers, and writes
only under the repository fixture directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT_DIR = HERE / "fixtures" / "ftmo_momentum_pullback_history_20260713"
TERMINAL = Path(r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe")
FILES_DIR = Path(r"C:\Users\Sanique Richards\AppData\Roaming\MetaQuotes\Terminal\81A933A9AFC5DE3C23B15CAB19C63850\MQL5\Files")
EXPECTED_SERVER = "FTMO-Demo"
EXPECTED_COMPANY = "FTMO Global Markets Ltd"
MAGICS = frozenset((770077, 771025))
START_UTC = datetime(2020, 1, 1, tzinfo=timezone.utc)
MANIFEST = "MANIFEST.sha256"
TELEMETRY = (
    "MomentumPullback_trades.csv",
    "MomentumPullback_decisions_202607.csv",
    "MomentumPullback_decisions_v130_202607.csv",
    "MomentumPullback_partials_v130.csv",
)
EXPECTED_FILES = frozenset({"README.md", "METADATA.json", "deals.csv", "orders.csv", MANIFEST, *TELEMETRY})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def anon(namespace: str, value: Any) -> str:
    return hashlib.sha256(f"MPB_HISTORY_20260713:{namespace}:{value}".encode("utf-8")).hexdigest()[:20]


def iso_seconds(epoch: int) -> str:
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_milliseconds(epoch_ms: int) -> str:
    return datetime.fromtimestamp(int(epoch_ms) / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def terminal_is_running() -> bool:
    tasklist = subprocess.run(["tasklist", "/FI", "IMAGENAME eq terminal64.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=False)
    return any("terminal64.exe" in line.lower() for line in tasklist.stdout.splitlines())


def values(record: Any, columns: Iterable[str]) -> dict[str, Any]:
    raw = record._asdict()
    return {column: raw[column] for column in columns}


def deal_rows(deals: Iterable[Any]) -> list[dict[str, Any]]:
    rows = []
    for deal in sorted(deals, key=lambda item: (item.time_msc, item.ticket)):
        row = values(deal, ("type", "entry", "reason", "magic", "volume", "price", "commission", "swap", "profit", "fee", "symbol"))
        row.update({
            "deal_id": anon("deal", deal.ticket),
            "order_id": anon("order", deal.order),
            "position_id": anon("position", deal.position_id),
            "time_utc": iso_seconds(deal.time),
            "time_msc_utc": iso_milliseconds(deal.time_msc),
        })
        rows.append(row)
    return rows


def order_rows(orders: Iterable[Any]) -> list[dict[str, Any]]:
    rows = []
    for order in sorted(orders, key=lambda item: (item.time_setup_msc, item.ticket)):
        row = values(order, ("type", "state", "reason", "magic", "volume_initial", "volume_current", "price_open", "sl", "tp", "price_current", "symbol"))
        row.update({
            "order_id": anon("order", order.ticket),
            "position_id": anon("position", order.position_id),
            "time_setup_utc": iso_seconds(order.time_setup),
            "time_setup_msc_utc": iso_milliseconds(order.time_setup_msc),
            "time_done_utc": iso_seconds(order.time_done),
            "time_done_msc_utc": iso_milliseconds(order.time_done_msc),
        })
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def copy_sanitized_telemetry(source: Path, target: Path) -> dict[str, Any]:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    sanitized = []
    for row in rows:
        cleaned = dict(row)
        if "deal" in cleaned:
            cleaned["deal_id"] = anon("deal", cleaned.pop("deal"))
        if "position_id" in cleaned:
            cleaned["position_id"] = anon("position", cleaned["position_id"])
        sanitized.append(cleaned)
    out_fields = list(sanitized[0]) if sanitized else [field for field in fields if field != "deal"]
    with target.open("x", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=out_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sanitized)
    return {"source_file": source.name, "rows": len(sanitized), "source_sha256": sha256_file(source), "sanitized_sha256": sha256_file(target)}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_readme(path: Path) -> None:
    path.write_text(
        "# FTMO Momentum Pullback execution-history snapshot\n\n"
        "This is a sanitized, immutable fixture for validating the live EA against "
        "broker history and its own telemetry. It is not a substitute for candle data.\n\n"
        "- `deals.csv`: all broker deals whose magic is 770077 or 771025.\n"
        "- `orders.csv`: all corresponding broker orders.\n"
        "- `MomentumPullback_*.csv`: EA telemetry captured at export time.\n"
        "- `METADATA.json`: venue, schema, count, and retrieval provenance without account credentials or login.\n"
        "- `MANIFEST.sha256`: SHA256 hashes for every file above.\n\n"
        "Ticket, order, and position identifiers are deterministic one-way snapshot identifiers; "
        "comments, external IDs, account number, terminal data path, and credentials are excluded.\n\n"
        "Cursor setup: run `git lfs pull`, then `python backtest/verify_data.py` and "
        "`python backtest/export_ftmo_momentum_history_snapshot.py --verify`.\n",
        encoding="utf-8", newline="\n",
    )


def manifest_body(directory: Path) -> str:
    names = {path.name for path in directory.iterdir()}
    expected_without_manifest = EXPECTED_FILES - {MANIFEST}
    if names != expected_without_manifest:
        raise RuntimeError(f"unexpected snapshot files: expected={sorted(expected_without_manifest)} actual={sorted(names)}")
    return "".join(f"{sha256_file(directory / name)}  {name}\n" for name in sorted(expected_without_manifest, key=str.lower))


def verify_directory(directory: Path) -> None:
    actual = {path.name for path in directory.iterdir()}
    if actual != EXPECTED_FILES:
        raise RuntimeError(f"snapshot file-set mismatch: missing={sorted(EXPECTED_FILES - actual)} extra={sorted(actual - EXPECTED_FILES)}")
    paths = list(directory.iterdir())
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise RuntimeError("snapshot contains non-regular or symlinked entries")
    rows = (directory / MANIFEST).read_text(encoding="ascii").splitlines()
    expected = EXPECTED_FILES - {MANIFEST}
    if len(rows) != len(expected):
        raise RuntimeError("manifest row count mismatch")
    seen: set[str] = set()
    for row in rows:
        digest, sep, name = row.partition("  ")
        if sep != "  " or len(digest) != 64 or name not in expected or name in seen:
            raise RuntimeError(f"malformed manifest row: {row!r}")
        if sha256_file(directory / name) != digest:
            raise RuntimeError(f"manifest hash mismatch: {name}")
        seen.add(name)
    if seen != expected:
        raise RuntimeError("manifest file set incomplete")


def export() -> None:
    import MetaTrader5 as mt5

    if OUT_DIR.exists():
        raise RuntimeError(f"snapshot destination already exists: {OUT_DIR}")
    if not terminal_is_running():
        raise RuntimeError("terminal64.exe is not already running; refusing to launch a terminal")
    OUT_DIR.parent.mkdir(parents=True, exist_ok=True)
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
        end = datetime.now(timezone.utc)
        deals = [deal for deal in (mt5.history_deals_get(START_UTC, end) or []) if int(deal.magic) in MAGICS]
        orders = [order for order in (mt5.history_orders_get(START_UTC, end) or []) if int(order.magic) in MAGICS]
        deal_data, order_data = deal_rows(deals), order_rows(orders)
        write_csv(staging / "deals.csv", deal_data)
        write_csv(staging / "orders.csv", order_data)
        telemetry = {}
        for name in TELEMETRY:
            source = FILES_DIR / name
            if not source.is_file():
                raise RuntimeError(f"required telemetry file missing: {name}")
            telemetry[name] = copy_sanitized_telemetry(source, staging / name)
        metadata = {
            "retrieval_utc": end.isoformat(), "history_start_utc": START_UTC.isoformat(),
            "venue": {"server": account.server, "company": account.company},
            "terminal_build": int(terminal.build), "mt5_version": list(mt5.version()),
            "target_magics": sorted(MAGICS), "deals": len(deal_data), "orders": len(order_data),
            "symbols": sorted({row["symbol"] for row in deal_data} | {row["symbol"] for row in order_data}),
            "read_only_mt5_calls": ["initialize", "account_info", "terminal_info", "version", "history_deals_get", "history_orders_get", "last_error", "shutdown"],
            "telemetry": telemetry,
            "redactions": ["account login", "terminal data path", "broker ticket/order/position IDs", "comments", "external IDs", "credentials"],
        }
        write_json(staging / "METADATA.json", metadata)
        write_readme(staging / "README.md")
        body = manifest_body(staging)
        (staging / MANIFEST).write_text(body, encoding="ascii", newline="\n")
        verify_directory(staging)
        staging.rename(OUT_DIR)
        published = True
        verify_directory(OUT_DIR)
        print(f"exported Momentum Pullback snapshot: {len(deal_data)} deals, {len(order_data)} orders, {len(telemetry)} telemetry files")
    finally:
        if initialized:
            mt5.shutdown()
        if not published and staging.exists():
            shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true", help="verify an existing immutable snapshot")
    args = parser.parse_args()
    if args.verify:
        verify_directory(OUT_DIR)
        print(f"verified Momentum Pullback snapshot {len(EXPECTED_FILES)} OK, 0 missing, 0 mismatched, 0 extra")
    else:
        export()


if __name__ == "__main__":
    main()
