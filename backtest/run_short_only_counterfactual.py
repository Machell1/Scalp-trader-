"""Registered both-sides versus short-only FTMO-holdout C1 counterfactual."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from freeze_ftmo_v130_blind import verify_manifest
from parity_engine import run_live
from v130_coupled import (
    CAPS, F1_PER_BAR, F2_STRICT_ASK_2X, V130Execution, CoupledTape, W2,
    ea_server_day, load_ftmo_split, normalized_event_bytes, replay_invariants,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "SHORT_ONLY_COUNTERFACTUAL_SPEC_2026-07-14.md"
OUT = HERE / "short_only_counterfactual_holdout_results.json"


def protocol_hash() -> str:
    data = SPEC.read_bytes()
    marker = b"\n\n**Recorded protocol SHA256:**"
    return hashlib.sha256(data[: data.index(marker) + 1]).hexdigest()


def directional_inputs(inputs, shorts_only: bool):
    if not shorts_only:
        return inputs
    symbols = tuple(replace(s, side=np.where(s.side < 0, s.side, 0).astype(np.int8)) for s in inputs.symbols)
    return replace(inputs, symbols=symbols)


def run_variant(inputs, mode: str) -> CoupledTape:
    events = []
    execution = V130Execution(inputs.spreads, mode)
    trades, census = run_live(
        list(inputs.symbols), thr=W2, caps=CAPS, queue=False, reverse_scan=False,
        window=4, replace_on_signal=False, execution=execution,
        event_sink=events.append, day_key=ea_server_day,
    )
    replay = replay_invariants(events)
    if replay["completed"] != len(trades):
        raise AssertionError("event replay and trade tape disagree")
    return CoupledTape(mode, tuple(trades), tuple(events), census, hashlib.sha256(normalized_event_bytes(events)).hexdigest())


def summary(tape: CoupledTape, frame_end: int) -> dict:
    rows = [{"symbol": t.sym, "side": "long" if t.side > 0 else "short", "r": float(t.r),
             "quarter": str(pd.Timestamp(int(t.ep_sig), unit="s", tz="UTC").to_period("Q"))}
            for t in tape.trades]
    def stats(items):
        values = np.asarray([x["r"] for x in items], float)
        return {"n": int(len(values)), "expectancy_r": float(values.mean()) if len(values) else None,
                "win_rate": float((values > 0).mean()) if len(values) else None,
                "total_r": float(values.sum()) if len(values) else 0.0}
    complete_cutoff = str(pd.Timestamp(int(frame_end), unit="s", tz="UTC").to_period("Q"))
    quarters = {quarter: stats([x for x in rows if x["quarter"] == quarter]) for quarter in sorted({x["quarter"] for x in rows})}
    complete = [q for q in sorted(quarters) if q < complete_cutoff]
    return {
        **stats(rows),
        "by_side": {side: stats([x for x in rows if x["side"] == side]) for side in ("long", "short")},
        "by_symbol": {symbol: stats([x for x in rows if x["symbol"] == symbol]) for symbol in sorted({x["symbol"] for x in rows})},
        "quarters": quarters, "complete_quarters": complete,
        "final_complete_quarter": complete[-1] if complete else None,
        "final_complete_quarter_expectancy_r": quarters[complete[-1]]["expectancy_r"] if complete else None,
        "event_tape_sha256": tape.normalized_sha256,
        "events": len(tape.events),
    }


def main() -> None:
    expected = "8b4e81360ed37631933785eb09ce9510aa7f94687987ea14a79ac81d0df51b0a"
    actual = protocol_hash()
    if actual != expected:
        raise RuntimeError(f"protocol hash mismatch: {actual}")
    verify_manifest()
    inputs = load_ftmo_split("holdout", authorize_blind=True)
    frame_end = max(int(s.ep[-1]) for s in inputs.symbols)
    output = {"protocol_sha256": actual, "split": "holdout", "modes": {}}
    for label, mode in (("E1_MEASURED", F1_PER_BAR), ("E2_STRESS", F2_STRICT_ASK_2X)):
        control = run_variant(directional_inputs(inputs, False), mode)
        short = run_variant(directional_inputs(inputs, True), mode)
        c0, s1 = summary(control, frame_end), summary(short, frame_end)
        if s1["by_side"]["long"]["n"] != 0:
            raise AssertionError("short-only candidate emitted a long trade")
        output["modes"][label] = {"C0_both_sides": c0, "S1_short_only": s1,
                                   "expectancy_delta_s1_minus_c0": s1["expectancy_r"] - c0["expectancy_r"]}
        print(label, "C0", c0["n"], c0["expectancy_r"], "S1", s1["n"], s1["expectancy_r"], flush=True)
    stress = output["modes"]["E2_STRESS"]
    s1, c0 = stress["S1_short_only"], stress["C0_both_sides"]
    output["trade_tape_pass"] = bool(
        s1["expectancy_r"] is not None and s1["expectancy_r"] > 0.0
        and stress["expectancy_delta_s1_minus_c0"] > 0.0
        and s1["final_complete_quarter_expectancy_r"] is not None
        and s1["final_complete_quarter_expectancy_r"] >= 0.0
    )
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RESULT_FILE={OUT}")


if __name__ == "__main__":
    main()
