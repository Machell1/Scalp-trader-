"""M30 execution / H4 anchor study.

Pre-registered: docs/M30_H4_ANCHOR_SPEC_2026-07-21.md
  (SHA256 761329a6a731c40eea6028b658c8ea08f481c497e700a893f68dacf79cbe3fab)

Cells: V0 native-M30 book (attribution control), V1 = V0 + H4 direction gate,
V2 = H4-anchor signal with M30 execution (primary). Control = audited C1-H1
tape. Paired 20k MC per candidate on common bootstrap frames; era gates.
Mirrors build_h1_universe_tape's event grammar exactly (TF-parameterized).
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_h1_universe_tape as B
from build_h1_universe_tape import build_h1_universe_tape, ftmo_metas
from run_h1_universe_screen import load_symbol, source_path, META_PATH
from run_h1_universe_account import common_bootstrap, configure_symbols
from snapshot_h1_universe_meta import SOURCE_TO_FTMO
import v130_pass_policy_csharp as csharp_engine
from v130_pass_policy import CompactRun, PassTape, RiskPolicy
from scipy.stats import binomtest
import json

SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
KW_H1 = dict(stress=True, partial_fraction=0.75, target_atr=1.5,
             reference_same_bar_partial=True, momentum_atr_mult=2.0)
BASE_RISK = {"US30.cash": 0.0030, "US100.cash": 0.0030, "JP225.cash": 0.0030,
             "USDJPY": 0.0005}
PATHS = 20_000
CHUNK = 500
GATE_HARD = 0.003700
MB = 6
W2 = 0.30
PART_FRAC = 0.75


def agg(raw: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Completeness-checked aggregation from M15 (mirrors aggregate_h1_fast)."""
    n_sub = minutes // 15
    frame = raw.copy()
    frame["_dt"] = pd.to_datetime(frame["time"])
    frame = frame.sort_values("_dt")
    frame["_bin"] = frame["_dt"].dt.floor(f"{minutes}min")
    frame["_offset"] = (frame["_dt"] - frame["_bin"]).dt.total_seconds().astype(int)
    grouped = frame.groupby("_bin", sort=True)
    checks = grouped["_offset"].agg(["count", "nunique", "min", "max", "sum"])
    exp_sum = sum(900 * k for k in range(n_sub))
    valid = checks.index[(checks["count"] == n_sub) & (checks["nunique"] == n_sub)
                         & (checks["min"] == 0) & (checks["max"] == 900 * (n_sub - 1))
                         & (checks["sum"] == exp_sum)]
    cols = dict(open=("open", "first"), high=("high", "max"),
                low=("low", "min"), close=("close", "last"))
    if "spread_price" in frame.columns:
        cols["spread_price"] = ("spread_price", "median")
    out = grouped.agg(**cols)
    out = out.loc[valid].reset_index().rename(columns={"_bin": "time"})
    return out


def wilder_atr_arr(h, l, c, period=14):
    from scalper_backtest import wilder_atr
    return wilder_atr(h, l, c, period)


def frame_cost(source: str, meta: dict, frame: pd.DataFrame) -> float:
    """cost_e1 (per side, ATR fraction of THIS frame's ATR) - mirrors load_symbol."""
    row = meta["symbols"][source]
    h = frame["high"].to_numpy(float)
    l = frame["low"].to_numpy(float)
    c = frame["close"].to_numpy(float)
    atr = wilder_atr_arr(h, l, c)
    med_atr = float(np.nanmedian(atr))
    if "spread_price" in frame.columns and frame["spread_price"].abs().sum() > 0:
        sp = frame["spread_price"].to_numpy(float)
        src_spread = 0.5 * float(np.median(sp[sp > 0])) / med_atr
    else:
        src_spread = 0.03
    ftmo_spread = 0.5 * float(row["spread_points"]) * float(row["point"]) / med_atr
    commission = row["commission"]
    if commission["kind"] == "zero":
        comm = 0.0
    elif commission["kind"] == "notional_fraction":
        comm = float(commission["per_side_fraction"]) * float(np.nanmedian(c)) / med_atr
    elif commission["kind"] == "usd_per_lot":
        comm = (float(commission["per_side_usd_per_lot"])
                * float(row["trade_tick_size"]) / float(row["trade_tick_value_loss"])) / med_atr
    else:
        raise ValueError(str(commission))
    return max(src_spread, ftmo_spread if ftmo_spread > 0 else 0.0) + comm


class TF:
    def __init__(self, source, meta, minutes):
        raw = pd.read_csv(source_path(source))
        if "spread_price" not in raw.columns:
            raw["spread_price"] = 0.0
        self.frame = agg(raw, minutes)
        self.minutes = minutes
        self.sec = minutes * 60
        f = self.frame
        self.o = f["open"].to_numpy(float)
        self.h = f["high"].to_numpy(float)
        self.l = f["low"].to_numpy(float)
        self.c = f["close"].to_numpy(float)
        self.ep = (pd.to_datetime(f["time"]).astype("int64") // 10**9).to_numpy()
        # NOTE: house epoch law - avoid .astype on tz frames; agg produced naive UTC-like
        self.ep = ((pd.to_datetime(f["time"]) - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy()
        self.atr = wilder_atr_arr(self.h, self.l, self.c)
        self.cost_e1 = frame_cost(source, meta, self.frame)


def signal_arrays(tf: TF):
    n = len(tf.c)
    move = np.full(n, np.nan)
    move[MB - 1:] = tf.c[:n - (MB - 1)] - tf.c[MB - 1:]
    with np.errstate(invalid="ignore", divide="ignore"):
        ma = move / tf.atr
    valid = np.isfinite(tf.atr) & (tf.atr > 0) & (np.arange(n) >= 21)
    falling = valid & (ma >= 2.0) & (tf.c < tf.o)
    rising = valid & (-ma >= 2.0) & (tf.c > tf.o)
    side = np.zeros(n, dtype=np.int8)
    side[falling] = -1
    side[rising] = 1
    up = tf.h - np.maximum(tf.o, tf.c)
    dn = np.minimum(tf.o, tf.c) - tf.l
    watr = np.full(n, np.nan)
    watr[rising] = up[rising] / tf.atr[rising]
    watr[falling] = dn[falling] / tf.atr[falling]
    return side, watr


def emit_trade(events, seq, trade_id, symbol, cluster, side, sig_atr, cost,
               entry, pend_epoch, cancel_epoch, fill_idx, exec_tf, fill_bar,
               exit_bar, exit_price, partial_bar, bar_off):
    """Append the audited event grammar for one trade on the EXECUTION frame."""
    ev = B._event
    seq += 1
    events.append(ev(f"{trade_id}:open", trade_id, symbol, cluster, side,
                     pend_epoch, seq, "pending_open", price=entry,
                     stop_distance=sig_atr, fixed_slippage_r=0.0,
                     remaining_fraction=1.0, mark_role="neutral"))
    if fill_bar is None:
        seq += 1
        events.append(ev(f"{trade_id}:cancel", trade_id, symbol, cluster, side,
                         cancel_epoch, seq, "pending_cancel", price=entry,
                         stop_distance=sig_atr, fixed_slippage_r=0.0,
                         remaining_fraction=1.0, mark_role="neutral"))
        return seq, None
    seq += 1
    events.append(ev(f"{trade_id}:entry", trade_id, symbol, cluster, side,
                     int(exec_tf.ep[fill_bar]), seq, "entry", price=entry,
                     stop_distance=sig_atr, fixed_slippage_r=cost,
                     remaining_fraction=1.0, mark_role="neutral"))
    for bar in range(fill_bar, exit_bar):
        if partial_bar == bar:
            seq += 1
            events.append(ev(f"{trade_id}:partial", trade_id, symbol, cluster, side,
                             int(exec_tf.ep[bar]) + bar_off, seq, "partial",
                             price=entry + side * sig_atr, stop_distance=sig_atr,
                             fixed_slippage_r=0.0, remaining_fraction=1.0 - PART_FRAC,
                             mark_role="favorable"))
            continue
        mp = float(exec_tf.c[bar])
        seq += 1
        events.append(ev(f"{trade_id}:mark:{bar}", trade_id, symbol, cluster, side,
                         int(exec_tf.ep[bar]) + bar_off, seq, "mark", price=mp,
                         stop_distance=sig_atr, fixed_slippage_r=0.0,
                         remaining_fraction=(1.0 - PART_FRAC
                                             if partial_bar is not None and bar > partial_bar
                                             else 1.0),
                         mark_role="favorable" if (mp - entry) * side > 0 else "adverse"))
    final_epoch = int(exec_tf.ep[exit_bar]) + bar_off
    if partial_bar == exit_bar:
        seq += 1
        events.append(ev(f"{trade_id}:partial", trade_id, symbol, cluster, side,
                         final_epoch, seq, "partial", price=entry + side * sig_atr,
                         stop_distance=sig_atr, fixed_slippage_r=0.0,
                         remaining_fraction=1.0 - PART_FRAC, mark_role="favorable"))
    seq += 1
    events.append(ev(f"{trade_id}:final", trade_id, symbol, cluster, side,
                     final_epoch, seq, "final", price=float(exit_price),
                     stop_distance=sig_atr, fixed_slippage_r=0.0,
                     remaining_fraction=0.0, mark_role="neutral"))
    return seq, final_epoch


def resolve_exec(exec_tf, start_bar, side, entry, sl, tp, part_lvl, max_bars):
    """Walk EXECUTION bars: SL first, then partial touch, then TP (per bar)."""
    partial_bar = None
    n = len(exec_tf.c)
    for bar in range(start_bar, min(start_bar + max_bars, n)):
        if side > 0:
            if exec_tf.l[bar] <= sl:
                return bar, sl, partial_bar
            if partial_bar is None and exec_tf.h[bar] >= part_lvl:
                partial_bar = bar
            if exec_tf.h[bar] >= tp:
                return bar, tp, partial_bar
        else:
            if exec_tf.h[bar] >= sl:
                return bar, sl, partial_bar
            if partial_bar is None and exec_tf.l[bar] <= part_lvl:
                partial_bar = bar
            if exec_tf.l[bar] <= tp:
                return bar, tp, partial_bar
    k = min(start_bar + max_bars - 1, n - 1)
    return k, float(exec_tf.c[k]), partial_bar


def arbitrate(events, sources):
    grouped = {}
    for event in events:
        grouped.setdefault(event.trade_id, []).append(event)
    extra = sorted(set(SOURCE_TO_FTMO[s] for s in sources) - set(B.BASE_ORDER))
    order = dict(B.BASE_ORDER)
    order.update({sym: 3 + i for i, sym in enumerate(extra)})
    intervals = []
    for tid, rows in grouped.items():
        opening = next(r for r in rows if r.kind == "pending_open")
        ending = max(r.epoch for r in rows if r.kind in ("pending_cancel", "final"))
        intervals.append((opening.epoch, order[opening.symbol], tid,
                          opening.symbol, opening.cluster, ending))
    active, accepted = [], set()
    for placement, prio, tid, sym, cluster, ending in sorted(intervals):
        active = [a for a in active if a[5] >= placement]
        if any(a[3] == sym for a in active):
            continue
        if any(a[4] == cluster for a in active) or len(active) >= 2:
            continue
        accepted.add(tid)
        active.append((placement, prio, tid, sym, cluster, ending))
    kept = [e for e in events if e.trade_id in accepted]
    from datetime import datetime, timezone
    firsts = min(e.epoch for e in kept)
    lasts = max(e.epoch for e in kept)
    fd = datetime.fromtimestamp(firsts, timezone.utc).astimezone(B.PRAGUE).date()
    ld = datetime.fromtimestamp(lasts, timezone.utc).astimezone(B.PRAGUE).date()
    counts = {}
    for tid in accepted:
        sym = tid.split(":")[1]
        counts[sym] = counts.get(sym, 0) + 1
    return PassTape.from_events(kept, first_day=fd, last_day=ld), counts


def build_cell(meta, cell):
    """cell in {'V0','V1','V2'}; returns (tape, counts, trade_rows)."""
    events, seq = [], 0
    rows = []
    for source in SOURCES:
        symbol = SOURCE_TO_FTMO[source]
        cluster = B.CLUSTERS[symbol]
        m30 = TF(source, meta, 30)
        h4 = TF(source, meta, 240)
        cost_m30 = m30.cost_e1 * 2.0     # E2 study currency
        cost_h4 = h4.cost_e1 * 2.0
        if cell in ("V0", "V1"):
            side_a, watr_a = signal_arrays(m30)
            sig_tf, exec_tf, cost = m30, m30, cost_m30
            window, hold, bar_off = 4, 8, m30.sec - 1
        else:
            side_a, watr_a = signal_arrays(h4)
            sig_tf, exec_tf, cost = h4, m30, cost_h4
            window, hold, bar_off = 4 * 8, 8 * 8, m30.sec - 1  # in M30 bars
        h4_side, _ = signal_arrays(h4)
        n = len(sig_tf.c)
        i = 21
        while i < n - 1:
            sd = int(side_a[i])
            if sd == 0 or not (np.isfinite(watr_a[i]) and watr_a[i] >= W2):
                i += 1
                continue
            if cell == "V1":
                # last CLOSED H4 bar at the M30 signal close
                sig_close = int(sig_tf.ep[i]) + sig_tf.sec
                j = int(np.searchsorted(h4.ep + h4.sec, sig_close, side="right")) - 1
                if j < MB or not np.isfinite(h4.c[j]) or not np.isfinite(h4.c[j - MB]):
                    i += 1
                    continue
                if np.sign(h4.c[j] - h4.c[j - MB]) != sd:
                    i += 1
                    continue
            a = float(sig_tf.atr[i])
            entry = float(sig_tf.c[i] - 0.6 * a * sd)
            sl = entry - a * sd
            tp = entry + 1.5 * a * sd
            part = entry + 1.0 * a * sd
            sig_close_ep = int(sig_tf.ep[i]) + sig_tf.sec
            if cell == "V2":
                w_start = int(np.searchsorted(exec_tf.ep, sig_close_ep, side="left"))
            else:
                w_start = i + 1
            fill_bar = None
            for bar in range(w_start, min(w_start + window, len(exec_tf.c))):
                if (sd > 0 and exec_tf.l[bar] <= entry) or (sd < 0 and exec_tf.h[bar] >= entry):
                    fill_bar = bar
                    break
            tid = f"H1U:{symbol}:{cell}:{i}"
            pend_epoch = sig_close_ep - 1
            cancel_bar = min(w_start + window, len(exec_tf.c) - 1)
            cancel_epoch = int(exec_tf.ep[cancel_bar])
            if fill_bar is None:
                seq, _ = emit_trade(events, seq, tid, symbol, cluster, sd, a, cost,
                                    entry, pend_epoch, cancel_epoch, None, exec_tf,
                                    None, None, None, None, bar_off)
                # live re-arm: 4 signal-TF bars in both constructions
                i += 4
                continue
            exit_bar, exit_px, partial_bar = resolve_exec(
                exec_tf, fill_bar, sd, entry, sl, tp, part, hold)
            seq, _ = emit_trade(events, seq, tid, symbol, cluster, sd, a, cost,
                                entry, pend_epoch, cancel_epoch, None, exec_tf,
                                fill_bar, exit_bar, exit_px, partial_bar, bar_off)
            banked = PART_FRAC * 1.0 if partial_bar is not None else 0.0
            frac = 1.0 - PART_FRAC if partial_bar is not None else 1.0
            r = banked + frac * (exit_px - entry) * sd / a - 2.0 * cost
            rows.append(dict(source=source, symbol=symbol, cell=cell, sig=i,
                             ep=int(sig_tf.ep[i]), r=r))
            if cell == "V2":
                # resume at the H4 bar after the exec exit bar
                nxt = int(np.searchsorted(sig_tf.ep, exec_tf.ep[exit_bar], side="right"))
                i = max(nxt, i + 1)
            else:
                i = max(int(np.searchsorted(sig_tf.ep, exec_tf.ep[exit_bar], side="left")) + 1,
                        i + 1)
            continue
        # end symbol
    tape, counts = arbitrate(events, SOURCES)
    return tape, counts, rows


def run_chunks(tape, metas, policy, boot, label):
    out = []
    for start in range(0, PATHS, CHUNK):
        count = min(CHUNK, PATHS - start)
        part = csharp_engine.run_csharp_monte_carlo(
            tape, metas, (policy,), paths=count, path_start=start,
            bootstrap=boot)[policy.name]
        out.append(part.rows)
        done = start + count
        if done % 5000 == 0:
            print(f"MC {label} {done}/{PATHS}", flush=True)
    return CompactRun(policy, np.concatenate(out))


def main():
    chk = subprocess.run([sys.executable, str(HERE / "verify_data.py")],
                         capture_output=True, text=True)
    line = (chk.stdout + chk.stderr).strip().splitlines()[-1]
    print("verify_data:", line)
    assert "46 OK" in line, "data verification failed"

    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    control, ccounts = build_h1_universe_tape(SOURCES, **KW_H1)
    print(f"control C1-H1 counts: {ccounts}")

    metas = ftmo_metas(SOURCES)
    configure_symbols(tuple(metas))
    policy = RiskPolicy("M30H4", dict(BASE_RISK), dict(BASE_RISK))

    for cell in ("V0", "V1", "V2"):
        tape, counts, rows = build_cell(meta, cell)
        df = pd.DataFrame(rows)
        q = pd.to_datetime(df.ep, unit="s").dt.to_period("Q")
        oos_qs = sorted(q.unique())[int(len(q.unique()) * 0.7):]
        oos = df[q.isin(oos_qs)]
        print(f"\n=== {cell} ===")
        print(f"  accepted counts: {counts}")
        print(f"  raw trades n={len(df)} expE2={df.r.mean():+.4f} "
              f"| OOS n={len(oos)} exp={oos.r.mean() if len(oos) else float('nan'):+.4f}")
        for sym, g in df.groupby("symbol"):
            print(f"    {sym}: n={len(g)} exp={g.r.mean():+.4f}")
        boot = common_bootstrap(control, tape)
        ctl = run_chunks(control, metas, policy, boot, f"{cell}:ctlH1")
        cand = run_chunks(tape, metas, policy, boot, f"{cell}:cand")
        cs, ks = ctl.summary(), cand.summary()
        lower, n10, n01, _, _ = cand.paired_delta_lower(ctl)
        p = (float(binomtest(n10, n10 + n01, 0.5, alternative="greater").pvalue)
             if n10 + n01 else 1.0)
        print(f"  CONTROL H1: both={cs.both_probability:.4%} hard={cs.hard_probability:.4%} "
              f"timeout={cs.timeout_probability:.4%} med={cs.median_total_days_success:.0f}d")
        print(f"  {cell}:      both={ks.both_probability:.4%} hard={ks.hard_probability:.4%} "
              f"timeout={ks.timeout_probability:.4%} med={ks.median_total_days_success:.0f}d")
        gates = dict(hard=ks.hard_probability <= GATE_HARD, paired=lower > 0)
        print(f"  paired lower={lower:+.6f} n10={n10} n01={n01} McNemar p={p:.3g} "
              f"| gates hard={'Y' if gates['hard'] else 'N'} paired>{'Y' if gates['paired'] else 'N'} "
              f"-> {'PASS' if all(gates.values()) else 'no'}", flush=True)

    print("\nScreen complete. Any PASS advances to 100k confirmation per spec.")


if __name__ == "__main__":
    main()
