"""One pre-registered exploratory M1 cash-open fair-price reversion cell."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from freeze_video_m1_us100 import OUT_DIR


HERE = Path(__file__).resolve().parent
SPEC = HERE.parent / "docs" / "VIDEO_M1_OPEN_REVERSION_SPEC_2026-07-13.md"
SPEC_SHA256 = "6413ac7c63ea2f629951ba43c7edb1419bf913a2ac4981b59ea6c219f037b872"
FREEZER = HERE / "freeze_video_m1_us100.py"
DATA = OUT_DIR / "US100_cash_M1_98807.npy"
META = OUT_DIR / "METADATA.json"
POINT = None
RESULT = HERE / "video_m1_open_reversion_20260713.json"
MARKER = b"\n\n**Recorded protocol SHA256:**"


@dataclass(frozen=True)
class Trade:
    date: str
    direction: str
    entry_utc: str
    exit_utc: str
    exit_reason: str
    entry: float
    stop: float
    target: float
    exit: float
    r: float


def verify_spec() -> None:
    rel = SPEC.relative_to(HERE.parent).as_posix()
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=HERE.parent).returncode:
        raise RuntimeError("strategy protocol working tree differs from committed HEAD")
    script_rel = Path(__file__).resolve().relative_to(HERE.parent).as_posix()
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", script_rel], cwd=HERE.parent).returncode:
        raise RuntimeError("strategy runner working tree differs from committed HEAD")
    raw = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=HERE.parent)
    boundary = raw.find(MARKER)
    if boundary < 0 or b"\r" in raw:
        raise RuntimeError("strategy protocol is not canonical UTF-8/LF")
    if hashlib.sha256(raw[: boundary + 1]).hexdigest() != SPEC_SHA256:
        raise RuntimeError("strategy protocol hash mismatch")


def verify_freeze() -> None:
    completed = subprocess.run(["python", str(FREEZER), "--verify"], cwd=HERE.parent, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr or completed.stdout)


def utc(epoch: int) -> str:
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def summary(trades: list[Trade]) -> dict[str, float | int | None]:
    if not trades:
        return {"n": 0, "win_rate_pct": None, "mean_r": None, "median_r": None}
    values = np.array([trade.r for trade in trades], dtype=float)
    return {"n": len(trades), "win_rate_pct": float(100 * np.mean(values > 0)), "mean_r": float(np.mean(values)), "median_r": float(np.median(values))}


def close_index(times: np.ndarray, timestamp: int) -> int | None:
    index = int(np.searchsorted(times, timestamp))
    return index if index < len(times) and int(times[index]) == timestamp else None


def run() -> dict[str, object]:
    verify_spec()
    verify_freeze()
    meta = json.loads(META.read_text(encoding="utf-8"))
    point = float(meta["symbol_info"]["point"])
    bars = np.load(DATA, allow_pickle=False)
    times = bars["time"].astype(np.int64)
    start_day = datetime.fromtimestamp(int(times[0]), timezone.utc).date()
    end_day = datetime.fromtimestamp(int(times[-1]), timezone.utc).date()
    dates = np.arange(np.datetime64(start_day), np.datetime64(end_day) + 1, dtype="datetime64[D]")
    counts: Counter[str] = Counter()
    trades: list[Trade] = []
    complete_dates: list[str] = []
    for date64 in dates:
        date = str(date64)
        day = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
        if day.weekday() >= 5:
            continue
        at = lambda hour, minute: close_index(times, int(day.replace(hour=hour, minute=minute).timestamp()))
        required = [at(13, minute) for minute in range(15, 60)] + [at(14, minute) for minute in range(16)] + [at(15, 55)]
        if any(index is None for index in required):
            counts["incomplete_session"] += 1
            continue
        complete_dates.append(date)
        pre = bars[[at(13, minute) for minute in range(15, 30)]]
        anchor = float(bars[at(13, 29)]["close"])
        scale = float(np.median(pre["high"].astype(float) - pre["low"].astype(float)))
        impulse = bars[at(13, 30)]
        delta = float(impulse["close"] - anchor)
        body = float(impulse["close"] - impulse["open"])
        if not np.isfinite(scale) or scale <= 0 or abs(delta) < scale or delta * body <= 0:
            counts["no_impulse"] += 1
            continue
        direction = "short" if delta > 0 else "long"
        consolidation = bars[[at(13, minute) for minute in range(31, 35)]]
        con_high = float(np.max(consolidation["high"]))
        con_low = float(np.min(consolidation["low"]))
        impulse_side = bool(np.all(consolidation["low"] >= anchor)) if direction == "short" else bool(np.all(consolidation["high"] <= anchor))
        compact = con_high - con_low <= 1.5 * scale
        fade = float(np.mean(consolidation["tick_volume"])) <= float(impulse["tick_volume"])
        if not (impulse_side and compact and fade):
            counts["no_consolidation"] += 1
            continue
        signal_index = None
        for minute in list(range(35, 60)) + list(range(0, 16)):
            index = at(13, minute) if minute >= 35 else at(14, minute)
            close = float(bars[index]["close"])
            if (direction == "short" and close < con_low) or (direction == "long" and close > con_high):
                signal_index = index
                break
        if signal_index is None:
            counts["no_structure_break"] += 1
            continue
        signal = bars[signal_index]
        spread = float(signal["spread"]) * point
        if direction == "short":
            entry, stop = float(signal["close"]), con_high + 0.10 * scale
            risk = stop - entry
            target = entry - 3 * risk
            enough_room = target >= anchor
        else:
            entry, stop = float(signal["close"]) + spread, con_low - 0.10 * scale
            risk = entry - stop
            target = entry + 3 * risk
            enough_room = target <= anchor
        if risk <= 0 or not enough_room:
            counts["fair_price_under_3r"] += 1
            continue
        if signal_index + 1 >= len(bars):
            counts["no_exit_bar"] += 1
            continue
        exit_price, exit_reason, exit_index = None, "timeout", at(15, 55)
        for index in range(signal_index + 1, at(15, 55) + 1):
            bar = bars[index]
            ask_high = float(bar["high"]) + float(bar["spread"]) * point
            bid_low, bid_high = float(bar["low"]), float(bar["high"])
            hit_stop = ask_high >= stop if direction == "short" else bid_low <= stop
            hit_target = bid_low <= target if direction == "short" else bid_high >= target
            if hit_stop or hit_target:
                exit_reason, exit_index = ("stop", index) if hit_stop else ("target", index)
                exit_price = stop if hit_stop else target
                break
        if exit_price is None:
            close_bar = bars[exit_index]
            exit_price = float(close_bar["close"]) + float(close_bar["spread"]) * point if direction == "short" else float(close_bar["close"])
        r = (entry - exit_price) / risk if direction == "short" else (exit_price - entry) / risk
        trades.append(Trade(date, direction, utc(times[signal_index]), utc(times[exit_index]), exit_reason, entry, stop, target, float(exit_price), float(r)))
        counts["trade"] += 1
    split = int(np.floor(0.60 * len(complete_dates)))
    early_dates = set(complete_dates[:split])
    payload: dict[str, object] = {
        "spec_sha256": SPEC_SHA256, "freeze_manifest": "backtest/ftmo_m1_us100_video_20260713.manifest.sha256", "complete_session_dates": complete_dates,
        "candidate_counts": dict(sorted(counts.items())), "all": summary(trades), "first_60pct_dates": summary([trade for trade in trades if trade.date in early_dates]),
        "final_40pct_dates": summary([trade for trade in trades if trade.date not in early_dates]), "trades": [asdict(trade) for trade in trades],
    }
    RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: payload[key] for key in ("candidate_counts", "all", "first_60pct_dates", "final_40pct_dates")}, sort_keys=True))
    return payload


if __name__ == "__main__":
    run()
