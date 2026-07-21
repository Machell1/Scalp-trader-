"""Capture the registered v1.36-A1 FTMO execution context read-only.

This utility is intentionally narrow.  It connects to the one documented
FTMO terminal, verifies the frozen account identity before symbol reads, and
writes one JSON artifact under the repository.  It does not request prices,
history, positions, orders, or deals and exposes no trading operation.

The optional partial-close CSV is read as an immutable input and embedded in
the JSON so the subsequent census can use the exact bytes that were frozen.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
TERMINAL_EXECUTABLE = Path(
    r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
)
EXPECTED_LOGIN = 1513946641
EXPECTED_SERVER = "FTMO-Demo"
FROZEN_SYMBOLS = ("US30.cash", "US100.cash", "JP225.cash", "USDJPY")

SYMBOL_FLOAT_FIELDS = (
    "point",
    "trade_tick_size",
    "trade_tick_value",
    "trade_tick_value_profit",
    "trade_tick_value_loss",
    "volume_min",
    "volume_step",
    "volume_max",
)
SYMBOL_NONNEGATIVE_INT_FIELDS = (
    "digits",
    "trade_stops_level",
    "trade_freeze_level",
)
PARTIAL_REQUIRED_COLUMNS = (
    "time",
    "deal",
    "position_id",
    "symbol",
    "dir",
    "initial_volume",
    "target_volume",
    "deal_volume",
    "level",
    "fill",
    "slippage_price",
    "slippage_R",
    "state",
    "trigger_tag",
)


class ValidationError(RuntimeError):
    """A frozen identity, metadata, input, or output condition was violated."""


class CaptureError(RuntimeError):
    """A capture failed after one or more journaled external calls."""

    def __init__(self, message: str, journal: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.journal = journal


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValidationError("journal timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _required_attr(record: Any, field: str, context: str) -> Any:
    if record is None or not hasattr(record, field):
        raise ValidationError(f"{context} missing required field {field!r}")
    return getattr(record, field)


def _strict_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer, got boolean")
    try:
        converted = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer, got {value!r}") from exc
    try:
        exact = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be numeric, got {value!r}") from exc
    if not math.isfinite(exact) or exact != converted or converted < minimum:
        raise ValidationError(
            f"{field} must be an integer >= {minimum}, got {value!r}"
        )
    return converted


def _positive_float(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be positive, got boolean")
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be numeric, got {value!r}") from exc
    if not math.isfinite(converted) or converted <= 0.0:
        raise ValidationError(f"{field} must be finite and > 0, got {value!r}")
    return converted


def validate_account_identity(account: Any) -> dict[str, Any]:
    """Validate and return only the frozen account identity fields."""
    login = _strict_int(_required_attr(account, "login", "account"), "account.login")
    server = str(_required_attr(account, "server", "account"))
    if login != EXPECTED_LOGIN:
        raise ValidationError(
            f"wrong FTMO login: expected={EXPECTED_LOGIN} actual={login}"
        )
    if server != EXPECTED_SERVER:
        raise ValidationError(
            f"wrong FTMO server: expected={EXPECTED_SERVER!r} actual={server!r}"
        )
    company = str(getattr(account, "company", ""))
    return {"login": login, "server": server, "company": company}


def validate_terminal_identity(terminal: Any) -> dict[str, Any]:
    """Validate the terminal connection and return non-account-state identity."""
    build = _strict_int(
        _required_attr(terminal, "build", "terminal"), "terminal.build", minimum=1
    )
    connected = _required_attr(terminal, "connected", "terminal")
    if not isinstance(connected, (bool, int)) or not bool(connected):
        raise ValidationError(f"terminal.connected must be true, got {connected!r}")
    install_path = Path(
        str(_required_attr(terminal, "path", "terminal"))
    ).resolve(strict=False)
    expected_install_path = TERMINAL_EXECUTABLE.parent.resolve(strict=False)
    if install_path != expected_install_path:
        raise ValidationError(
            "wrong terminal installation: "
            f"expected={expected_install_path} actual={install_path}"
        )
    return {
        "build": build,
        "connected": True,
        "name": str(getattr(terminal, "name", "")),
        "company": str(getattr(terminal, "company", "")),
        "install_path": str(install_path),
    }


def validate_symbol_info(symbol: str, info: Any) -> dict[str, int | float | str]:
    """Validate the exact broker fields registered by the fidelity spec."""
    if info is None:
        raise ValidationError(f"FTMO symbol unavailable: {symbol}")
    actual_name = str(_required_attr(info, "name", f"symbol {symbol}"))
    if actual_name != symbol:
        raise ValidationError(
            f"symbol identity mismatch: requested={symbol!r} actual={actual_name!r}"
        )

    result: dict[str, int | float | str] = {"name": actual_name}
    for field in SYMBOL_FLOAT_FIELDS:
        result[field] = _positive_float(
            _required_attr(info, field, f"symbol {symbol}"), f"{symbol}.{field}"
        )
    for field in SYMBOL_NONNEGATIVE_INT_FIELDS:
        result[field] = _strict_int(
            _required_attr(info, field, f"symbol {symbol}"), f"{symbol}.{field}"
        )

    if float(result["volume_min"]) > float(result["volume_max"]):
        raise ValidationError(
            f"{symbol}.volume_min exceeds {symbol}.volume_max"
        )
    if float(result["volume_step"]) > float(result["volume_max"]):
        raise ValidationError(
            f"{symbol}.volume_step exceeds {symbol}.volume_max"
        )
    return result


def parse_partial_csv_bytes(data: bytes) -> dict[str, Any]:
    """Parse an immutable partial CSV byte string without normalizing its rows."""
    encoding = "utf-8-sig"
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        encoding = "cp1252"
        text = data.decode(encoding)

    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = list(reader.fieldnames or [])
    if not header:
        raise ValidationError("partial CSV has no header")
    if len(header) != len(set(header)):
        raise ValidationError(f"partial CSV has duplicate columns: {header!r}")
    missing = [column for column in PARTIAL_REQUIRED_COLUMNS if column not in header]
    if missing:
        raise ValidationError(f"partial CSV missing required columns: {missing}")

    rows: list[dict[str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValidationError(f"partial CSV row {row_number} has extra fields")
        if any(row.get(column) is None for column in header):
            raise ValidationError(f"partial CSV row {row_number} has missing fields")
        normalized = {column: str(row[column]) for column in header}
        if all(value == "" for value in normalized.values()):
            continue
        rows.append(normalized)
    return {"encoding": encoding, "header": header, "rows": rows}


def resolve_repo_output(raw_path: str | Path, repo_root: Path = REPO_ROOT) -> Path:
    """Resolve a non-existing JSON output and prove it remains in the repo."""
    root = repo_root.resolve()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationError(
            f"output must be inside repository {root}: {candidate}"
        ) from exc
    if candidate == root:
        raise ValidationError("output must be a file below the repository root")
    if candidate.suffix.lower() != ".json":
        raise ValidationError(f"output must use a .json suffix: {candidate}")
    if candidate.exists():
        raise ValidationError(f"refusing to overwrite existing output: {candidate}")
    return candidate


def describe_input_path(path: Path, repo_root: Path = REPO_ROOT) -> str:
    """Identify an input without publishing an external terminal data path."""
    resolved = path.resolve(strict=True)
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return f"external:{resolved.name}"


def _journal_entry(
    clock: Callable[[], datetime], operation: str, target: str, status: str, **detail: Any
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "utc": iso_utc(clock()),
        "operation": operation,
        "target": target,
        "status": status,
    }
    if detail:
        entry["detail"] = detail
    return entry


def capture_context(
    mt5: Any,
    *,
    partials_csv: Path | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> dict[str, Any]:
    """Perform the constrained reads; ``mt5`` is injected for auditable tests."""
    journal: list[dict[str, Any]] = []
    initialized = False
    failure: BaseException | None = None
    account_payload: dict[str, Any] | None = None
    terminal_payload: dict[str, Any] | None = None
    symbols_payload: dict[str, Any] = {}

    try:
        executable_exists = TERMINAL_EXECUTABLE.is_file()
        journal.append(
            _journal_entry(
                clock,
                "verify_terminal_executable",
                str(TERMINAL_EXECUTABLE),
                "ok" if executable_exists else "failed",
            )
        )
        if not executable_exists:
            raise ValidationError(
                f"documented FTMO terminal executable missing: {TERMINAL_EXECUTABLE}"
            )
        ok = bool(mt5.initialize(path=str(TERMINAL_EXECUTABLE), timeout=30_000))
        journal.append(
            _journal_entry(
                clock,
                "initialize",
                str(TERMINAL_EXECUTABLE),
                "ok" if ok else "failed",
                timeout_ms=30_000,
            )
        )
        if not ok:
            raise ValidationError("MetaTrader5 initialize failed")
        initialized = True

        account = mt5.account_info()
        journal.append(_journal_entry(clock, "account_info", "account", "returned"))
        account_payload = validate_account_identity(account)

        terminal = mt5.terminal_info()
        journal.append(
            _journal_entry(clock, "terminal_info", "terminal", "returned")
        )
        terminal_payload = validate_terminal_identity(terminal)

        for symbol in FROZEN_SYMBOLS:
            info = mt5.symbol_info(symbol)
            journal.append(
                _journal_entry(clock, "symbol_info", symbol, "returned")
            )
            symbols_payload[symbol] = validate_symbol_info(symbol, info)
    except Exception as exc:  # retain a complete journal before re-raising
        failure = exc
    finally:
        if initialized:
            try:
                mt5.shutdown()
                journal.append(
                    _journal_entry(clock, "shutdown", "MetaTrader5 API", "ok")
                )
            except Exception as exc:
                journal.append(
                    _journal_entry(
                        clock,
                        "shutdown",
                        "MetaTrader5 API",
                        "failed",
                        error_type=type(exc).__name__,
                    )
                )
                if failure is None:
                    failure = exc

    if failure is not None:
        raise CaptureError(str(failure), journal) from failure
    assert account_payload is not None and terminal_payload is not None

    partial_payload: dict[str, Any] | None = None
    if partials_csv is not None:
        source = partials_csv.expanduser()
        source_label = f"external:{source.name}"
        try:
            source = source.resolve(strict=True)
            source_label = describe_input_path(source)
            if not source.is_file():
                raise ValidationError(f"partial CSV is not a regular file: {source}")
            stat_before = source.stat()
            data = source.read_bytes()
            stat_after = source.stat()
            if (
                stat_before.st_size != stat_after.st_size
                or stat_before.st_mtime_ns != stat_after.st_mtime_ns
            ):
                raise ValidationError("partial CSV changed while it was being read")
            parsed = parse_partial_csv_bytes(data)
        except Exception as exc:
            journal.append(
                _journal_entry(
                    clock,
                    "read_partial_csv",
                    source_label,
                    "failed",
                    error_type=type(exc).__name__,
                )
            )
            raise CaptureError(str(exc), journal) from exc
        digest = hashlib.sha256(data).hexdigest()
        journal.append(
            _journal_entry(
                clock,
                "read_partial_csv",
                source_label,
                "ok",
                bytes=len(data),
                rows=len(parsed["rows"]),
                sha256=digest,
            )
        )
        partial_payload = {
            "source": source_label,
            "sha256": digest,
            "bytes": len(data),
            **parsed,
        }

    return {
        "schema": "v136_a1_execution_context_v1",
        "captured_utc": iso_utc(clock()),
        "access_mode": "READ_ONLY",
        "terminal_executable": str(TERMINAL_EXECUTABLE),
        "expected_identity": {
            "login": EXPECTED_LOGIN,
            "server": EXPECTED_SERVER,
        },
        "account": account_payload,
        "terminal": terminal_payload,
        "symbols": symbols_payload,
        "partial_csv": partial_payload,
        "read_journal": journal,
        "mt5_calls_permitted": [
            "initialize",
            "account_info",
            "terminal_info",
            "symbol_info",
            "shutdown",
        ],
    }


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> str:
    """Write exactly one new repository JSON and return its SHA256."""
    body = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(body)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        help="new JSON path under this repository (existing files are never overwritten)",
    )
    parser.add_argument(
        "--partials-csv",
        type=Path,
        help="optional existing partial-close CSV to read and embed without modification",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = resolve_repo_output(args.output)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        print(f"ERROR: MetaTrader5 import failed: {exc}", file=sys.stderr)
        return 2

    try:
        payload = capture_context(mt5, partials_csv=args.partials_csv)
        digest = write_json_exclusive(output, payload)
    except (CaptureError, ValidationError, FileExistsError, OSError) as exc:
        if isinstance(exc, CaptureError):
            print(
                "READ_JOURNAL " + json.dumps(exc.journal, sort_keys=True),
                file=sys.stderr,
            )
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {output}")
    print(f"sha256 {digest}")
    print(f"journaled reads {len(payload['read_journal'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
