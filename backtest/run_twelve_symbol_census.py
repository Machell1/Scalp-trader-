"""Census for the preregistered twelve-symbol H1 universe diagnostic."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from build_h1_universe_tape import CLUSTERS, build_h1_universe_tape


HERE = Path(__file__).resolve().parent
RESULT = HERE / "twelve_symbol_census_results.json"
PRAGUE = ZoneInfo("Europe/Prague")
CONTROL = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
CANDIDATE = CONTROL + (
    "US_SP_500", "France_40", "Australia_200", "EURUSD",
    "XAUUSD", "XCUUSD", "XPTUSD", "LTCUSD",
)


def day(epoch: int):
    return datetime.fromtimestamp(int(epoch), timezone.utc).astimezone(PRAGUE).date()


def lifecycles(tape):
    grouped = defaultdict(list)
    for event in tape.events:
        grouped[event.trade_id].append(event)
    output = []
    for trade_id, rows in grouped.items():
        entry = next((row for row in rows if row.kind == "entry"), None)
        final = next((row for row in rows if row.kind == "final"), None)
        if entry is None or final is None:
            continue
        fraction = 1.0
        gross_r = 0.0
        for partial in sorted((row for row in rows if row.kind == "partial"), key=lambda x: x.sequence):
            closed = fraction - float(partial.remaining_fraction)
            gross_r += closed * (partial.price - entry.price) * entry.side / entry.stop_distance
            fraction = float(partial.remaining_fraction)
        gross_r += fraction * (final.price - entry.price) * entry.side / entry.stop_distance
        per_side = float(entry.fixed_slippage_r)
        output.append({
            "trade_id": trade_id,
            "symbol": entry.symbol,
            "cluster": entry.cluster,
            "entry_epoch": int(entry.epoch),
            "gross_r": gross_r,
            "account_tape_r": gross_r - per_side,
            "registered_roundtrip_r": gross_r - 2.0 * per_side,
            "per_side_cost_r": per_side,
        })
    return output


def expectancy(rows, field):
    values = np.asarray([row[field] for row in rows], dtype=float)
    return float(values.mean()) if len(values) else None


def summarize(name, sources):
    tape, accepted = build_h1_universe_tape(sources, stress=True)
    rows = lifecycles(tape)
    opens = [event for event in tape.events if event.kind == "pending_open"]
    cancels = [event for event in tape.events if event.kind == "pending_cancel"]
    entries = [event for event in tape.events if event.kind == "entry"]
    dates = []
    cursor = tape.first_day
    while cursor <= tape.last_day:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor += timedelta(days=1)
    counts = Counter(day(event.epoch) for event in entries)
    weekday_counts = np.asarray([counts[value] for value in dates], dtype=float)
    per_symbol = {}
    for symbol in sorted({row["symbol"] for row in rows}):
        subset = [row for row in rows if row["symbol"] == symbol]
        per_symbol[symbol] = {
            "cluster": CLUSTERS[symbol],
            "entries": len(subset),
            "account_tape_expectancy": expectancy(subset, "account_tape_r"),
            "registered_roundtrip_expectancy": expectancy(subset, "registered_roundtrip_r"),
            "win_rate_roundtrip": float(np.mean([row["registered_roundtrip_r"] > 0 for row in subset])),
        }
    per_cluster = Counter(CLUSTERS[row["symbol"]] for row in rows)
    summary = {
        "name": name,
        "sources": list(sources),
        "calendar_days": tape.n_days,
        "weekdays": len(dates),
        "accepted_pending_lifecycles": len(opens),
        "actual_entries": len(entries),
        "weekday_entries": int(weekday_counts.sum()),
        "weekend_entries": len(entries) - int(weekday_counts.sum()),
        "unfilled_cancellations": len(cancels),
        "fill_rate": len(entries) / len(opens),
        "mean_fills_per_calendar_day": len(entries) / tape.n_days,
        "mean_fills_per_weekday": float(weekday_counts.mean()),
        "median_fills_per_weekday": float(np.median(weekday_counts)),
        "p10_fills_per_weekday": float(np.quantile(weekday_counts, 0.10)),
        "p90_fills_per_weekday": float(np.quantile(weekday_counts, 0.90)),
        "max_fills_per_weekday": int(weekday_counts.max()),
        "zero_fill_weekdays": int(np.sum(weekday_counts == 0)),
        "weekdays_ge_6_fraction": float(np.mean(weekday_counts >= 6)),
        "account_tape_expectancy": expectancy(rows, "account_tape_r"),
        "registered_roundtrip_expectancy": expectancy(rows, "registered_roundtrip_r"),
        "cost_reconciliation_gap_r": expectancy(rows, "account_tape_r") - expectancy(rows, "registered_roundtrip_r"),
        "accepted_attempts_by_symbol": accepted,
        "entries_by_cluster": dict(sorted(per_cluster.items())),
        "per_symbol": per_symbol,
    }
    print(
        name,
        f"symbols={len(sources)}",
        f"opens={len(opens)}",
        f"entries={len(entries)}",
        f"weekday_entries={int(weekday_counts.sum())}",
        f"weekday_rate={weekday_counts.mean():.6f}",
        f"days_ge6={np.mean(weekday_counts >= 6):.6f}",
        f"account_exp={summary['account_tape_expectancy']:+.6f}",
        f"roundtrip_exp={summary['registered_roundtrip_expectancy']:+.6f}",
        flush=True,
    )
    for symbol, row in per_symbol.items():
        print(
            "SYMBOL", name, symbol,
            f"n={row['entries']}",
            f"exp={row['registered_roundtrip_expectancy']:+.6f}",
            f"win={row['win_rate_roundtrip']:.6f}",
            flush=True,
        )
    return summary


def main():
    output = {
        "spec_sha256": "ab5e4be70b5cd76cec22579a1e0839522365d41b946a3844cb35ff94e01b0872",
        "control": summarize("CONTROL4", CONTROL),
        "candidate": summarize("CANDIDATE12", CANDIDATE),
    }
    output["frequency_delta_per_weekday"] = (
        output["candidate"]["mean_fills_per_weekday"]
        - output["control"]["mean_fills_per_weekday"]
    )
    output["candidate_frequency_gate"] = output["candidate"]["mean_fills_per_weekday"] >= 6.0
    output["cost_reconciliation_exact"] = all(
        abs(output[key]["cost_reconciliation_gap_r"]) < 1e-12
        for key in ("control", "candidate")
    )
    RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"FREQUENCY_GATE {'PASS' if output['candidate_frequency_gate'] else 'FAIL'}")
    print(f"COST_RECONCILIATION {'PASS' if output['cost_reconciliation_exact'] else 'FAIL'}")
    print(f"RESULT_SHA256 {hashlib.sha256(RESULT.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
