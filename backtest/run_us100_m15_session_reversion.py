"""Run the preregistered US100 M15 session-open mean-reversion proxy.

Protocol: docs/US100_M15_SESSION_REVERSION_SPEC_2026-07-13.md
SHA256: 26810e10f82d65bc2c68a284e8acb663bb6f9cac1d95d8ffec489d3ce338b2f1

The module is standalone.  It reuses only the repository's Wilder ATR and
DSR helpers; it does not modify or call the existing signal simulators.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "US100_M15_SESSION_REVERSION_SPEC_2026-07-13.md"
DATA = HERE / "data" / "derivM15_spreadgated" / "US_Tech_100.csv"
CALENDAR = HERE / "calendars" / "us_equities_session_exclusions_2024_2026.csv"

PROTOCOL_SHA256 = "26810e10f82d65bc2c68a284e8acb663bb6f9cac1d95d8ffec489d3ce338b2f1"
DATA_SHA256 = "f62bf95c4a7a6ef1e3cd56582db24d5f6a713815647b1beda4098b91dfd946d9"
CALENDAR_SHA256 = "a019c12412906f681b7d5fd9279f30ac850548f1acd21c24ca5fdf6f87f89791"
EXPECTED_COLUMNS = [
    "time", "open", "high", "low", "close", "volume", "spread", "spread_price"
]
VERIFY_LINE = "verified 46 OK, 0 missing, 0 mismatched"
NY_TZ = "America/New_York"
REQUIRED_CLOCKS = tuple(
    (pd.Timestamp("2000-01-01 09:15") + pd.Timedelta(minutes=15 * i)).strftime("%H:%M")
    for i in range(19)
)
BOX_CLOCKS = ("09:45", "10:00", "10:15")
TRIGGER_CLOCKS = ("10:30", "10:45")
ENTRY_CLOCK = {"10:30": "10:45", "10:45": "11:00"}
BINDING_QUARTERS = ("2025Q3", "2025Q4", "2026Q1", "2026Q2")
OOS_START = "2025-07-01"
OOS_END = "2026-06-30"
SEED = 13020260713
N_BOOT = 20_000
BLOCK = 5
N_TRIALS = 278
COSTS = {"E0_EXEC": 0.0, "E1_MEASURED": 0.02, "E2_STRESS": 0.04}
COMMITTED_PREOUTCOME_FILES = (
    SPEC,
    CALENDAR,
    Path(__file__).resolve(),
    HERE / "test_us100_m15_session_reversion.py",
)

sys.path.insert(0, str(HERE))
from experiment import psr  # noqa: E402
from scalper_backtest import wilder_atr  # noqa: E402
from walkforward_dsr import dsr_hurdle  # noqa: E402


@dataclass(frozen=True)
class Prepared:
    raw: pd.DataFrame
    epochs: np.ndarray
    local_date: np.ndarray
    local_clock: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    volume: np.ndarray
    spread: np.ndarray
    atr: np.ndarray


@dataclass(frozen=True)
class Setup:
    session_date: str
    side: int
    anchor: float
    atr: float
    impulse: float
    trigger_clock: str
    trigger_index: int
    entry_index: int
    time_exit_index: int
    entry_bid: float
    entry_spread: float
    reward_distance: float
    risk_distance: float


@dataclass(frozen=True)
class Trade:
    cell: str
    session_date: str
    side: int
    trigger_clock: str
    entry_epoch: int
    exit_epoch: int
    entry_index: int
    exit_index: int
    entry_exec: float
    target: float
    stop: float
    exit_exec: float
    exit_reason: str
    risk_distance: float
    reward_distance: float
    entry_spread: float
    entry_spread_r: float
    holding_bars: int
    r0: float


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=check
    )


def verify_tracked_clean() -> None:
    unstaged = _git("diff", "--quiet", "HEAD", "--", check=False)
    staged = _git("diff", "--cached", "--quiet", check=False)
    if unstaged.returncode != 0 or staged.returncode != 0:
        raise RuntimeError("tracked working tree differs from committed HEAD")
    for path in COMMITTED_PREOUTCOME_FILES:
        rel = path.relative_to(ROOT).as_posix()
        tracked = _git("ls-files", "--error-unmatch", "--", rel, check=False)
        if tracked.returncode != 0:
            raise RuntimeError(f"required pre-outcome file is not tracked: {rel}")
        head_blob = _git("rev-parse", f"HEAD:{rel}", check=False)
        if head_blob.returncode != 0:
            raise RuntimeError(f"required pre-outcome file is absent from HEAD: {rel}")
        working_blob = _git("hash-object", "--path", rel, str(path), check=False)
        if working_blob.returncode != 0 or working_blob.stdout.strip() != head_blob.stdout.strip():
            raise RuntimeError(f"working file differs from Git-normalized HEAD: {rel}")


def verify_protocol_hash() -> None:
    rel = SPEC.relative_to(ROOT).as_posix()
    if _git("diff", "--quiet", "HEAD", "--", rel, check=False).returncode != 0:
        raise RuntimeError("working protocol differs from committed HEAD")
    shown = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=ROOT)
    if b"\r" in shown:
        raise RuntimeError("committed protocol is not UTF-8/LF")
    try:
        text = shown.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("committed protocol is not UTF-8") from exc
    marker = b"\n\n**Recorded protocol SHA256:**"
    boundary = shown.find(marker)
    if boundary < 0:
        raise RuntimeError("protocol hash boundary missing")
    actual = hashlib.sha256(shown[: boundary + 1]).hexdigest()
    found = re.search(r"\*\*Recorded protocol SHA256:\*\* `([0-9a-f]{64})`", text)
    if found is None:
        raise RuntimeError("recorded protocol SHA256 line missing or malformed")
    recorded = found.group(1)
    if actual != PROTOCOL_SHA256 or recorded != PROTOCOL_SHA256:
        raise RuntimeError(
            f"protocol hash mismatch: constant={PROTOCOL_SHA256} "
            f"recorded={recorded} recomputed={actual}"
        )


def verify_canonical_manifest() -> str:
    proc = subprocess.run(
        [sys.executable, str(HERE / "verify_data.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    output = proc.stdout.rstrip("\r\n")
    if proc.returncode != 0 or output != VERIFY_LINE:
        detail = (proc.stdout + proc.stderr).rstrip()
        raise RuntimeError(f"canonical verification failed verbatim:\n{detail}")
    return output


def load_exclusions() -> set[str]:
    actual = file_sha256(CALENDAR)
    if actual != CALENDAR_SHA256:
        raise RuntimeError(
            f"calendar hash mismatch: expected={CALENDAR_SHA256} actual={actual}"
        )
    table = pd.read_csv(CALENDAR, dtype=str)
    if list(table.columns) != ["session_date", "status"]:
        raise RuntimeError("calendar schema mismatch")
    if table["session_date"].duplicated().any():
        raise RuntimeError("calendar has duplicate session_date")
    dates = pd.to_datetime(table["session_date"], format="%Y-%m-%d", errors="raise")
    if (dates.dt.weekday >= 5).any():
        raise RuntimeError("calendar exclusion contains a weekend")
    if not table["status"].astype(str).str.len().gt(0).all():
        raise RuntimeError("calendar has blank status")
    return set(table["session_date"].tolist())


def validate_exact_m15_opens(times: pd.Series) -> None:
    floored = times.dt.floor("15min")
    if not bool((times == floored).all()):
        raise RuntimeError("source contains a bar not aligned to an exact M15 open")


def load_input() -> Prepared:
    actual = file_sha256(DATA)
    if actual != DATA_SHA256:
        raise RuntimeError(f"primary data hash mismatch: expected={DATA_SHA256} actual={actual}")
    raw = pd.read_csv(DATA)
    if list(raw.columns) != EXPECTED_COLUMNS:
        raise RuntimeError(
            f"primary schema mismatch: expected={EXPECTED_COLUMNS!r} actual={list(raw.columns)!r}"
        )
    times = pd.to_datetime(raw["time"], utc=True, errors="raise")
    validate_exact_m15_opens(times)
    # Pandas 3 may parse to datetime64[us] rather than datetime64[ns], so an
    # integer-unit division is not portable.  Timestamp.timestamp() is always
    # epoch seconds and the source bars are second-aligned.
    epochs = np.asarray([int(value.timestamp()) for value in times], dtype=np.int64)
    if len(epochs) < 100 or np.any(np.diff(epochs) <= 0):
        raise RuntimeError("timestamps are not strictly increasing and unique")

    o, h, l, c = (raw[name].to_numpy(float) for name in ("open", "high", "low", "close"))
    matrix = np.column_stack((o, h, l, c))
    if not np.all(np.isfinite(matrix)) or np.any(matrix <= 0):
        raise RuntimeError("OHLC contains nonfinite or nonpositive value")
    if not np.all((l <= o) & (l <= c) & (h >= o) & (h >= c) & (l <= h)):
        raise RuntimeError("OHLC invariant failure")
    volume = raw["volume"].to_numpy(float)
    spread_points = raw["spread"].to_numpy(float)
    spread = raw["spread_price"].to_numpy(float)
    if not np.all(np.isfinite(volume)) or np.any(volume < 0):
        raise RuntimeError("tick volume contains nonfinite or negative value")
    if not np.all(np.isfinite(spread_points)) or np.any(spread_points < 0):
        raise RuntimeError("spread points contain nonfinite or negative value")
    if not np.all(np.isfinite(spread)) or np.any(spread < 0):
        raise RuntimeError("spread_price contains nonfinite or negative value")

    local = times.dt.tz_convert(NY_TZ)
    return Prepared(
        raw=raw,
        epochs=epochs,
        local_date=local.dt.strftime("%Y-%m-%d").to_numpy(str),
        local_clock=local.dt.strftime("%H:%M").to_numpy(str),
        o=o,
        h=h,
        l=l,
        c=c,
        volume=volume,
        spread=spread,
        atr=wilder_atr(h, l, c, 14),
    )


def candidate_dates(data: Prepared, exclusions: set[str]) -> list[str]:
    start = pd.Timestamp(data.local_date[0])
    end = pd.Timestamp(data.local_date[-1])
    out = []
    for day in pd.date_range(start, end, freq="D"):
        label = day.strftime("%Y-%m-%d")
        if day.weekday() < 5 and label not in exclusions:
            out.append(label)
    return out


def session_index(data: Prepared, date: str) -> dict[str, int] | None:
    idx = np.flatnonzero(data.local_date == date)
    if idx.size == 0:
        return None
    result: dict[str, int] = {}
    for clock in REQUIRED_CLOCKS:
        matches = idx[data.local_clock[idx] == clock]
        if matches.size != 1:
            return None
        result[clock] = int(matches[0])
    ordered = np.asarray([result[x] for x in REQUIRED_CLOCKS], dtype=int)
    if not np.all(np.diff(data.epochs[ordered]) == 900):
        return None
    return result


def detect_setup(data: Prepared, date: str, bars: dict[str, int]) -> tuple[Setup | None, str]:
    anchor_i = bars["09:15"]
    open_i = bars["09:30"]
    a = float(data.atr[anchor_i])
    if not np.isfinite(a) or a <= 0:
        return None, "atr"
    f = float(data.c[anchor_i])
    impulse = float(data.c[open_i] - f)
    if abs(impulse) < a or impulse == 0:
        return None, "impulse"
    up = impulse > 0

    box_i = np.asarray([bars[x] for x in BOX_CLOCKS], dtype=int)
    width = float(np.max(data.h[box_i]) - np.min(data.l[box_i]))
    closes = data.c[box_i]
    side_ok = bool(np.all(closes > f)) if up else bool(np.all(closes < f))
    if width > a or not side_ok:
        return None, "box"

    volume_i = np.r_[open_i, box_i]
    volume = data.volume[volume_i]
    if not np.all(np.isfinite(volume)) or not np.all(volume > 0):
        return None, "volume"
    if not (float(np.median(data.volume[box_i])) < float(data.volume[open_i])):
        return None, "volume"
    if not (float(data.volume[box_i[-1]]) < float(data.volume[box_i[0]])):
        return None, "volume"

    box_low = float(np.min(data.l[box_i]))
    box_high = float(np.max(data.h[box_i]))
    trigger_clock = None
    trigger_i = None
    for clock in TRIGGER_CLOCKS:
        i = bars[clock]
        close = float(data.c[i])
        qualifies = (close < box_low and close > f) if up else (close > box_high and close < f)
        if qualifies:
            trigger_clock = clock
            trigger_i = i
            break
    if trigger_i is None or trigger_clock is None:
        return None, "trigger"

    entry_i = bars[ENTRY_CLOCK[trigger_clock]]
    p = float(data.o[entry_i])
    spread = float(data.spread[entry_i])
    side = -1 if up else 1
    entry_exec = p + spread if side > 0 else p
    reward = (f - entry_exec) if side > 0 else (entry_exec - f)
    if not np.isfinite(reward) or reward <= 0:
        return None, "reward"
    risk = reward / 3.0
    return Setup(
        session_date=date,
        side=side,
        anchor=f,
        atr=a,
        impulse=impulse,
        trigger_clock=trigger_clock,
        trigger_index=int(trigger_i),
        entry_index=int(entry_i),
        time_exit_index=int(bars["13:45"]),
        entry_bid=p,
        entry_spread=spread,
        reward_distance=reward,
        risk_distance=risk,
    ), "trade"


def _execution_geometry(data: Prepared, setup: Setup, cell: str) -> tuple[int, float, float, float]:
    if cell == "MR3":
        side = setup.side
        entry = setup.entry_bid + setup.entry_spread if side > 0 else setup.entry_bid
        target = setup.anchor
        stop = entry - side * setup.risk_distance
        return side, entry, target, stop
    if cell == "C1":
        side = -setup.side
        entry = setup.entry_bid + setup.entry_spread if side > 0 else setup.entry_bid
        target = entry + side * 3.0 * setup.risk_distance
        stop = entry - side * setup.risk_distance
        return side, entry, target, stop
    raise ValueError(f"unknown cell: {cell}")


def resolve_trade(data: Prepared, setup: Setup, cell: str) -> Trade:
    side, entry, target, stop = _execution_geometry(data, setup, cell)
    exit_i = setup.time_exit_index
    exit_px = float("nan")
    reason = "TIME"
    for i in range(setup.entry_index, setup.time_exit_index + 1):
        spread = float(data.spread[i])
        bid_open, bid_high, bid_low = float(data.o[i]), float(data.h[i]), float(data.l[i])
        ask_open, ask_high, ask_low = bid_open + spread, bid_high + spread, bid_low + spread
        if side > 0:
            if bid_low <= stop:
                exit_i = i
                exit_px = min(stop, bid_open)
                reason = "STOP"
                break
            if bid_high >= target:
                exit_i = i
                exit_px = target
                reason = "TARGET"
                break
        else:
            if ask_high >= stop:
                exit_i = i
                exit_px = max(stop, ask_open)
                reason = "STOP"
                break
            if ask_low <= target:
                exit_i = i
                exit_px = target
                reason = "TARGET"
                break
    if reason == "TIME":
        exit_px = float(data.c[exit_i]) if side > 0 else float(data.c[exit_i] + data.spread[exit_i])
    r0 = side * (exit_px - entry) / setup.risk_distance
    return Trade(
        cell=cell,
        session_date=setup.session_date,
        side=side,
        trigger_clock=setup.trigger_clock,
        entry_epoch=int(data.epochs[setup.entry_index]),
        exit_epoch=int(data.epochs[exit_i]),
        entry_index=setup.entry_index,
        exit_index=int(exit_i),
        entry_exec=float(entry),
        target=float(target),
        stop=float(stop),
        exit_exec=float(exit_px),
        exit_reason=reason,
        risk_distance=float(setup.risk_distance),
        reward_distance=float(setup.reward_distance),
        entry_spread=float(setup.entry_spread),
        entry_spread_r=float(setup.entry_spread / setup.risk_distance),
        holding_bars=int(exit_i - setup.entry_index + 1),
        r0=float(r0),
    )


def enumerate_trades(data: Prepared, exclusions: set[str]) -> tuple[list[str], dict[str, int], list[Setup], dict[str, list[Trade]]]:
    candidates = candidate_dates(data, exclusions)
    funnel = {
        "candidate_sessions": len(candidates),
        "complete_sessions": 0,
        "valid_atr": 0,
        "opening_impulse": 0,
        "consolidation_box": 0,
        "volume_fade": 0,
        "structure_trigger": 0,
        "valid_reward": 0,
        "completed_trades": 0,
    }
    eligible: list[str] = []
    setups: list[Setup] = []
    trades = {"MR3": [], "C1": []}
    stage_order = ["atr", "impulse", "box", "volume", "trigger", "reward", "trade"]
    stage_key = {
        "atr": "valid_atr",
        "impulse": "opening_impulse",
        "box": "consolidation_box",
        "volume": "volume_fade",
        "trigger": "structure_trigger",
        "reward": "valid_reward",
        "trade": "completed_trades",
    }
    for date in candidates:
        bars = session_index(data, date)
        if bars is None:
            continue
        eligible.append(date)
        funnel["complete_sessions"] += 1
        setup, failed_at = detect_setup(data, date, bars)
        stop_pos = stage_order.index(failed_at)
        for passed_stage in stage_order[:stop_pos]:
            funnel[stage_key[passed_stage]] += 1
        if setup is None:
            continue
        for passed_stage in stage_order[stop_pos:]:
            funnel[stage_key[passed_stage]] += 1
        setups.append(setup)
        trades["MR3"].append(resolve_trade(data, setup, "MR3"))
        trades["C1"].append(resolve_trade(data, setup, "C1"))
    if len(trades["MR3"]) != len(trades["C1"]) or len(trades["MR3"]) != len(setups):
        raise RuntimeError("paired trade enumeration mismatch")
    return eligible, funnel, setups, trades


def longest_negative_streak(values: np.ndarray) -> int:
    best = current = 0
    for value in values:
        current = current + 1 if value < 0 else 0
        best = max(best, current)
    return int(best)


def stats(values: Iterable[float]) -> dict[str, Any]:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        return {
            "n": 0,
            "expectancy": None,
            "win_rate": None,
            "profit_factor": None,
            "total_r": 0.0,
            "max_drawdown_r": 0.0,
            "median_r": None,
            "longest_loss_streak": 0,
        }
    gains = float(arr[arr > 0].sum())
    losses = float(-arr[arr < 0].sum())
    equity = np.r_[0.0, np.cumsum(arr)]
    peaks = np.maximum.accumulate(equity)
    pf = gains / losses if losses > 0 else None
    return {
        "n": int(arr.size),
        "expectancy": float(arr.mean()),
        "win_rate": float(np.mean(arr > 0)),
        "profit_factor": float(pf) if pf is not None and np.isfinite(pf) else None,
        "total_r": float(arr.sum()),
        "max_drawdown_r": float(np.max(peaks - equity)),
        "median_r": float(np.median(arr)),
        "longest_loss_streak": longest_negative_streak(arr),
    }


def trade_r(trade: Trade, mode: str) -> float:
    return float(trade.r0 - COSTS[mode])


def frame_dates(eligible_dates: list[str]) -> dict[str, set[str]]:
    cut = int(math.floor(0.70 * len(eligible_dates)))
    return {
        "FULL": set(eligible_dates),
        "DEVELOPMENT": {x for x in eligible_dates if x < OOS_START},
        "BINDING_OOS": {x for x in eligible_dates if OOS_START <= x <= OOS_END},
        "DIAGNOSTIC_70": set(eligible_dates[:cut]),
        "DIAGNOSTIC_30": set(eligible_dates[cut:]),
        "POST_OOS_PARTIAL": {x for x in eligible_dates if x > OOS_END},
    }


def summarize_cells(trades: dict[str, list[Trade]], frames: dict[str, set[str]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cell, rows in trades.items():
        out[cell] = {}
        for mode in COSTS:
            out[cell][mode] = {}
            for frame, dates in frames.items():
                out[cell][mode][frame] = stats(
                    trade_r(t, mode) for t in rows if t.session_date in dates
                )
    return out


def binding_quarter_table(trades: dict[str, list[Trade]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cell, rows in trades.items():
        out[cell] = {}
        for mode in COSTS:
            qrows: dict[str, list[float]] = {q: [] for q in BINDING_QUARTERS}
            for trade in rows:
                q = str(pd.Period(trade.session_date, freq="Q"))
                if q in qrows:
                    qrows[q].append(trade_r(trade, mode))
            out[cell][mode] = {q: stats(qrows[q]) for q in BINDING_QUARTERS}
    return out


def bootstrap_lower_bounds(primary: np.ndarray, delta: np.ndarray) -> tuple[float | None, float | None]:
    if primary.size == 0 or primary.size != delta.size:
        return None, None
    rng = np.random.default_rng(SEED)
    n = int(primary.size)
    n_blocks = int(math.ceil(n / BLOCK))
    offsets = np.arange(BLOCK, dtype=int)
    pmeans = np.empty(N_BOOT, dtype=float)
    dmeans = np.empty(N_BOOT, dtype=float)
    for b in range(N_BOOT):
        starts = rng.integers(0, n, size=n_blocks)
        idx = ((starts[:, None] + offsets[None, :]) % n).ravel()[:n]
        pmeans[b] = float(np.mean(primary[idx]))
        dmeans[b] = float(np.mean(delta[idx]))
    return (
        float(np.quantile(pmeans, 0.05, method="linear")),
        float(np.quantile(dmeans, 0.05, method="linear")),
    )


def sign_flip_pvalue(delta: np.ndarray) -> float | None:
    if delta.size == 0:
        return None
    rng = np.random.default_rng(SEED)
    observed = float(np.mean(delta))
    exceed = 0
    for _ in range(N_BOOT):
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=delta.size, replace=True)
        exceed += int(float(np.mean(delta * signs)) >= observed)
    return float((1 + exceed) / (N_BOOT + 1))


def inference_and_gates(
    trades: dict[str, list[Trade]], cells: dict[str, Any], quarters: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, bool], str]:
    mr = np.asarray(
        [trade_r(t, "E2_STRESS") for t in trades["MR3"] if OOS_START <= t.session_date <= OOS_END],
        dtype=float,
    )
    c1 = np.asarray(
        [trade_r(t, "E2_STRESS") for t in trades["C1"] if OOS_START <= t.session_date <= OOS_END],
        dtype=float,
    )
    if mr.size != c1.size:
        raise RuntimeError("OOS pair mismatch")
    delta = mr - c1
    primary_lb, delta_lb = bootstrap_lower_bounds(mr, delta)
    pvalue = sign_flip_pvalue(delta)
    dsr = None
    if mr.size >= 5 and float(np.std(mr, ddof=1)) > 0:
        dsr = float(psr(mr, dsr_hurdle(n_trials=N_TRIALS, n_obs=int(mr.size))))

    e1 = cells["MR3"]["E1_MEASURED"]["BINDING_OOS"]["expectancy"]
    e2 = cells["MR3"]["E2_STRESS"]["BINDING_OOS"]["expectancy"]
    delta_mean = float(delta.mean()) if delta.size else None
    qtab = quarters["MR3"]["E2_STRESS"]
    q_counts_ok = all(int(qtab[q]["n"]) >= 10 for q in BINDING_QUARTERS)
    q_positive = sum(
        int(qtab[q]["expectancy"] is not None and qtab[q]["expectancy"] > 0)
        for q in BINDING_QUARTERS
    )
    latest_positive = bool(
        qtab["2026Q2"]["expectancy"] is not None and qtab["2026Q2"]["expectancy"] > 0
    )
    gates = {
        "G1_oos_n_at_least_50": bool(mr.size >= 50),
        "G2_e1_and_e2_expectancy_positive": bool(
            e1 is not None and e2 is not None and e1 > 0 and e2 > 0
        ),
        "G3_e2_bootstrap_lower_above_zero": bool(primary_lb is not None and primary_lb > 0),
        "G4_paired_delta_and_lower_bound": bool(
            delta_mean is not None
            and delta_mean >= 0.03
            and delta_lb is not None
            and delta_lb > 0
        ),
        "G5_sign_flip_p_at_most_005": bool(pvalue is not None and pvalue <= 0.05),
        "G6_quarter_count_and_sign": bool(q_counts_ok and q_positive >= 3 and latest_positive),
        "G7_dsr_at_least_095": bool(dsr is not None and dsr >= 0.95),
    }
    inference = {
        "seed": SEED,
        "rng": "numpy.default_rng_PCG64",
        "bootstrap_replicates": N_BOOT,
        "block_length_trades": BLOCK,
        "oos_pairs": int(mr.size),
        "mr3_e2_expectancy": float(mr.mean()) if mr.size else None,
        "mr3_e2_bootstrap_95_lower": primary_lb,
        "paired_e2_mean_delta": delta_mean,
        "paired_e2_bootstrap_95_lower": delta_lb,
        "paired_sign_flip_pvalue": pvalue,
        "dsr_trials": N_TRIALS,
        "mr3_e2_dsr": dsr,
        "positive_binding_quarters": int(q_positive),
        "latest_binding_quarter_positive": latest_positive,
    }
    verdict = "HISTORICAL PASS" if all(gates.values()) else "KILL — NO ACCOUNT TEST"
    return inference, gates, verdict


def frequency_and_geometry(
    eligible: list[str], setups: list[Setup], trades: dict[str, list[Trade]]
) -> dict[str, Any]:
    dates = [t.session_date for t in trades["MR3"]]
    if eligible:
        eligible_week = pd.Series(pd.to_datetime(eligible)).dt.to_period("W").astype(str)
        trade_week = pd.Series(pd.to_datetime(dates)).dt.to_period("W").astype(str) if dates else pd.Series([], dtype="string")
        counts = trade_week.value_counts().reindex(sorted(eligible_week.unique()), fill_value=0)
        trades_per_calendar_week = float(counts.mean())
    else:
        trades_per_calendar_week = 0.0
    risk = np.asarray([s.risk_distance for s in setups], dtype=float)
    spread_r = np.asarray([t.entry_spread_r for t in trades["MR3"]], dtype=float)
    holds = np.asarray([t.holding_bars for t in trades["MR3"]], dtype=float)
    return {
        "eligible_complete_sessions": int(len(eligible)),
        "qualifying_sessions": int(len(setups)),
        "trades_per_eligible_session": float(len(setups) / len(eligible)) if eligible else 0.0,
        "trades_per_five_eligible_sessions": float(5.0 * len(setups) / len(eligible)) if eligible else 0.0,
        "mean_trades_per_eligible_calendar_week": trades_per_calendar_week,
        "long_trades": int(sum(t.side > 0 for t in trades["MR3"])),
        "short_trades": int(sum(t.side < 0 for t in trades["MR3"])),
        "risk_distance_min_median_max": (
            [float(np.min(risk)), float(np.median(risk)), float(np.max(risk))] if risk.size else []
        ),
        "entry_spread_r_min_median_max": (
            [float(np.min(spread_r)), float(np.median(spread_r)), float(np.max(spread_r))]
            if spread_r.size
            else []
        ),
        "holding_bars_min_median_max": (
            [int(np.min(holds)), float(np.median(holds)), int(np.max(holds))] if holds.size else []
        ),
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False, default=json_ready
    ) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def run() -> dict[str, Any]:
    verify_tracked_clean()
    verify_protocol_hash()
    verified = verify_canonical_manifest()
    exclusions = load_exclusions()
    data = load_input()
    eligible, funnel, setups, trades = enumerate_trades(data, exclusions)
    frames = frame_dates(eligible)
    cells = summarize_cells(trades, frames)
    quarters = binding_quarter_table(trades)
    inference, gates, verdict = inference_and_gates(trades, cells, quarters)
    commit = _git("rev-parse", "HEAD").stdout.strip()
    return {
        "study": "US100_M15_SESSION_REVERSION_MR3",
        "provenance": {
            "commit": commit,
            "protocol_sha256": PROTOCOL_SHA256,
            "data_sha256": DATA_SHA256,
            "calendar_sha256": CALENDAR_SHA256,
            "canonical_verification": verified,
            "rows": int(len(data.raw)),
            "first_utc": pd.to_datetime(int(data.epochs[0]), unit="s", utc=True).isoformat(),
            "last_utc": pd.to_datetime(int(data.epochs[-1]), unit="s", utc=True).isoformat(),
        },
        "frames": {
            name: {
                "eligible_dates": int(len(dates)),
                "first_date": min(dates) if dates else None,
                "last_date": max(dates) if dates else None,
            }
            for name, dates in frames.items()
        },
        "funnel": funnel,
        "frequency_and_geometry": frequency_and_geometry(eligible, setups, trades),
        "cells": cells,
        "binding_quarters": quarters,
        "inference": inference,
        "gates": gates,
        "verdict": verdict,
        "trial_ledger": {
            "global_start_derived": 276,
            "charged_cells": ["MR3", "C1"],
            "increment": 2,
            "global_after_derived": 278,
        },
        "trades": {
            cell: [
                {
                    **asdict(t),
                    "r": {mode: trade_r(t, mode) for mode in COSTS},
                }
                for t in rows
            ]
            for cell, rows in trades.items()
        },
    }


def print_summary(result: dict[str, Any]) -> None:
    print(result["provenance"]["canonical_verification"])
    print(f"commit {result['provenance']['commit']}")
    print(f"protocol {result['provenance']['protocol_sha256']}")
    print(f"data {result['provenance']['data_sha256']}")
    print(f"calendar {result['provenance']['calendar_sha256']}")
    print("funnel " + json.dumps(result["funnel"], sort_keys=True))
    for cell in ("MR3", "C1"):
        for mode in COSTS:
            s = result["cells"][cell][mode]["BINDING_OOS"]
            exp = "NA" if s["expectancy"] is None else f"{s['expectancy']:+.6f}"
            win = "NA" if s["win_rate"] is None else f"{s['win_rate']:.6%}"
            print(f"{cell} {mode} OOS n={s['n']} expectancy={exp} win={win}")
    print("inference " + json.dumps(result["inference"], sort_keys=True))
    for name, passed in result["gates"].items():
        print(f"{name}={'PASS' if passed else 'FAIL'}")
    print("VERDICT " + result["verdict"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "us100_m15_session_reversion_results.json",
    )
    args = parser.parse_args()
    result = run()
    write_json(args.output, result)
    print_summary(result)
    print(f"results_sha256 {file_sha256(args.output)}")


if __name__ == "__main__":
    main()
