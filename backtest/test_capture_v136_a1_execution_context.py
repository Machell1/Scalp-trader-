from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import capture_v136_a1_execution_context as capture


def account(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "login": capture.EXPECTED_LOGIN,
        "server": capture.EXPECTED_SERVER,
        "company": "FTMO Global Markets Ltd",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def symbol(name: str = "US30.cash", **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "name": name,
        "point": 0.01,
        "digits": 2,
        "trade_tick_size": 0.01,
        "trade_stops_level": 0,
        "trade_freeze_level": 0,
        "trade_tick_value": 1.0,
        "trade_tick_value_profit": 1.0,
        "trade_tick_value_loss": 1.0,
        "volume_min": 0.01,
        "volume_step": 0.01,
        "volume_max": 100.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def sample_partial_csv() -> bytes:
    return (
        ",".join(capture.PARTIAL_REQUIRED_COLUMNS)
        + "\r\n"
        + "2026.07.18 19:00:00,d1,p1,US30.cash,BUY,1.00,0.75,0.75,"
        "45000.0,45000.1,0.1,0.01,DONE,normal-tick\r\n"
    ).encode("utf-8")


def test_account_identity_is_fail_closed() -> None:
    assert capture.validate_account_identity(account())["login"] == capture.EXPECTED_LOGIN
    with pytest.raises(capture.ValidationError, match="wrong FTMO login"):
        capture.validate_account_identity(account(login=123))
    with pytest.raises(capture.ValidationError, match="wrong FTMO server"):
        capture.validate_account_identity(account(server="FTMO-Other"))


def test_terminal_requires_positive_build_and_connection() -> None:
    terminal = SimpleNamespace(
        build=5000,
        connected=True,
        path=str(capture.TERMINAL_EXECUTABLE.parent),
        name="MetaTrader 5",
        company="FTMO",
    )
    assert capture.validate_terminal_identity(terminal)["build"] == 5000
    with pytest.raises(capture.ValidationError, match="terminal.build"):
        capture.validate_terminal_identity(
            SimpleNamespace(
                build=0,
                connected=True,
                path=str(capture.TERMINAL_EXECUTABLE.parent),
            )
        )
    with pytest.raises(capture.ValidationError, match="terminal.connected"):
        capture.validate_terminal_identity(
            SimpleNamespace(
                build=5000,
                connected=False,
                path=str(capture.TERMINAL_EXECUTABLE.parent),
            )
        )
    with pytest.raises(capture.ValidationError, match="wrong terminal installation"):
        capture.validate_terminal_identity(
            SimpleNamespace(build=5000, connected=True, path=r"C:\Wrong Terminal")
        )


def test_symbol_metadata_validation_accepts_zero_distance_levels() -> None:
    result = capture.validate_symbol_info("US30.cash", symbol())
    assert result["trade_stops_level"] == 0
    assert result["trade_freeze_level"] == 0
    assert result["volume_step"] == pytest.approx(0.01)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("point", 0.0),
        ("trade_tick_size", -0.01),
        ("trade_tick_value", float("nan")),
        ("trade_tick_value_profit", 0.0),
        ("trade_tick_value_loss", 0.0),
        ("volume_min", 0.0),
        ("volume_step", 0.0),
        ("volume_max", 0.0),
        ("trade_stops_level", -1),
        ("trade_freeze_level", -1),
    ],
)
def test_symbol_metadata_rejects_invalid_registered_fields(field: str, value: object) -> None:
    with pytest.raises(capture.ValidationError, match=field):
        capture.validate_symbol_info("US30.cash", symbol(**{field: value}))


def test_partial_parser_preserves_rows_and_requires_schema() -> None:
    data = sample_partial_csv()
    parsed = capture.parse_partial_csv_bytes(data)
    assert parsed["encoding"] == "utf-8-sig"
    assert parsed["header"] == list(capture.PARTIAL_REQUIRED_COLUMNS)
    assert parsed["rows"][0]["position_id"] == "p1"
    with pytest.raises(capture.ValidationError, match="missing required columns"):
        capture.parse_partial_csv_bytes(b"time,symbol\n")
    short_row = ",".join(capture.PARTIAL_REQUIRED_COLUMNS).encode() + b"\nonly-time\n"
    with pytest.raises(capture.ValidationError, match="missing fields"):
        capture.parse_partial_csv_bytes(short_row)


def test_partial_required_columns_match_v136_a1_ea_header() -> None:
    assert capture.PARTIAL_REQUIRED_COLUMNS == (
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


def test_reading_partial_input_does_not_modify_it(tmp_path: Path) -> None:
    source = tmp_path / "MomentumPullback_partials_v130.csv"
    body = sample_partial_csv()
    source.write_bytes(body)
    before = source.stat()
    parsed = capture.parse_partial_csv_bytes(source.read_bytes())
    after = source.stat()
    assert parsed["rows"]
    assert source.read_bytes() == body
    assert hashlib.sha256(source.read_bytes()).hexdigest() == hashlib.sha256(body).hexdigest()
    assert before.st_size == after.st_size
    assert before.st_mtime_ns == after.st_mtime_ns


def test_output_must_be_new_json_inside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    inside = capture.resolve_repo_output("results/context.json", repo)
    assert inside == (repo / "results" / "context.json").resolve()

    with pytest.raises(capture.ValidationError, match="inside repository"):
        capture.resolve_repo_output(tmp_path / "outside.json", repo)
    with pytest.raises(capture.ValidationError, match=".json suffix"):
        capture.resolve_repo_output("results/context.txt", repo)

    existing = repo / "existing.json"
    existing.write_text("{}", encoding="utf-8")
    with pytest.raises(capture.ValidationError, match="refusing to overwrite"):
        capture.resolve_repo_output(existing, repo)


def test_external_partial_path_is_redacted(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = tmp_path / "MomentumPullback_partials_v130.csv"
    source.write_bytes(sample_partial_csv())
    label = capture.describe_input_path(source, repo)
    assert label == "external:MomentumPullback_partials_v130.csv"
    assert str(tmp_path) not in label


def test_write_json_is_exclusive(tmp_path: Path) -> None:
    output = tmp_path / "context.json"
    digest = capture.write_json_exclusive(output, {"schema": "test"})
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        capture.write_json_exclusive(output, {"schema": "changed"})


def test_pure_helpers_do_not_import_mt5() -> None:
    assert "MetaTrader5" not in sys.modules
