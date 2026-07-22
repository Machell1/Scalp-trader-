"""R2a Stage B: two-book paired account MC (C1-H1 + overnight sleeve vs C1-H1).

Pre-registered: M30_FAMILIES_R2_SPEC (709a6bdd) Stage-B per M30_FAMILIES_SPEC
(6ac24154): sleeve risk 0.10%; era gates hard<=0.37% and paired lower > 0;
20k screen -> 100k confirmation on pass. Swap folded into per-trade cost from
the measured FTMO rates. Combined-book seat rule: an overnight entry is
DROPPED if two H1-book trades are active at its entry moment (respects the
kernel's global-capacity invariant; drops counted and reported).
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_h1_universe_tape as B
from build_h1_universe_tape import build_h1_universe_tape, ftmo_metas
from run_h1_universe_account import common_bootstrap, configure_symbols
from run_h1_universe_screen import META_PATH
from m30_families_study import Sym
import v130_pass_policy_csharp as csharp_engine
from v130_pass_policy import CompactRun, PassTape, RiskPolicy

KW_H1 = dict(stress=True, partial_fraction=0.75, target_atr=1.5,
             reference_same_bar_partial=True, momentum_atr_mult=2.0)
SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
ON_SOURCES = ("Japan_225", "US_Tech_100")
SWAP_PRICE = {"US_Tech_100": -6.2145, "Japan_225": -8.2192}
BASE_RISK = {"US30.cash": 0.0030, "US100.cash": 0.0030, "JP225.cash": 0.0030,
             "USDJPY": 0.0005}
SLEEVE = 0.0010
GATE_HARD = 0.003700
CHUNK = 500
BINS = 48


def overnight_events(meta, h1_intervals):
    """Build R2a events; drop entries when 2 H1 trades active."""
    events, seq, dropped, kept = [], 10_000_000, 0, 0
    rows = []
    for source in ON_SOURCES:
        s = Sym(source, meta)
        t = s.tf
        symbol = s.symbol + "#ON"
        cluster = "ON_" + s.symbol
        days = sorted(set(s.day.tolist()))
        for di, d in enumerate(days[:-1]):
            bt = s.bar_at(d, (s.open_bin + 12) % BINS)
            b0d = s.bar_at(d, s.open_bin)
            if bt < 0 or b0d < 0 or t.c[bt] < t.o[b0d]:
                continue
            nxt = -1
            for d2 in days[di + 1:di + 4]:
                cand = s.bar_at(d2, s.open_bin)
                if cand > bt:
                    nxt = cand
                    break
            if nxt < 0:
                continue
            a = float(t.atr[bt])
            if not np.isfinite(a) or a <= 0:
                continue
            entry_epoch = int(t.ep[bt]) + 1799
            active = sum(1 for (st, en) in h1_intervals if st <= entry_epoch <= en)
            if active >= 2:
                dropped += 1
                continue
            nights = 0.0
            for dd in range(int(t.ep[bt]) // 86400, int(t.ep[nxt]) // 86400):
                wd = pd.Timestamp(dd * 86400, unit="s").weekday()
                nights += 3.0 if wd == 4 else 1.0
            swap_r = abs(SWAP_PRICE[source]) * nights / a
            cost_side = s.cost_e2 + swap_r / 2.0     # fold swap into per-side cost
            entry = float(t.c[bt])
            exitp = float(t.o[nxt])
            tid = f"H1U:{symbol}:{bt}"
            ev = B._event
            seq += 1
            events.append(ev(f"{tid}:open", tid, symbol, cluster, 1,
                             entry_epoch - 1, seq, "pending_open", price=entry,
                             stop_distance=a, fixed_slippage_r=0.0,
                             remaining_fraction=1.0, mark_role="neutral"))
            seq += 1
            events.append(ev(f"{tid}:entry", tid, symbol, cluster, 1,
                             entry_epoch, seq, "entry", price=entry,
                             stop_distance=a, fixed_slippage_r=cost_side,
                             remaining_fraction=1.0, mark_role="neutral"))
            seq += 1
            events.append(ev(f"{tid}:final", tid, symbol, cluster, 1,
                             int(t.ep[nxt]), seq, "final", price=exitp,
                             stop_distance=a, fixed_slippage_r=0.0,
                             remaining_fraction=0.0, mark_role="neutral"))
            kept += 1
            rows.append((source, (exitp - entry) / a - 2 * cost_side))
    df = pd.DataFrame(rows, columns=["source", "r"])
    print(f"overnight sleeve: kept={kept} dropped_at_capacity={dropped} "
          f"swapnet exp={df.r.mean():+.4f}")
    for src, g in df.groupby("source"):
        print(f"    {src}: n={len(g)} exp={g.r.mean():+.4f}")
    return events


def h1_trade_intervals(tape):
    iv = {}
    for e in tape.events:
        k = e.normalized_kind().value
        if k in ("entry", "final", "pending_cancel"):
            st, en = iv.get(e.trade_id, (None, None))
            if k == "entry":
                iv[e.trade_id] = (e.epoch, en if en else e.epoch)
            else:
                iv[e.trade_id] = (st, e.epoch) if st else (e.epoch, e.epoch)
    return [(s, e) for (s, e) in iv.values() if s is not None and e is not None]


def run_chunks(tape, metas, policy, boot, paths, label):
    out = []
    for start in range(0, paths, CHUNK):
        count = min(CHUNK, paths - start)
        part = csharp_engine.run_csharp_monte_carlo(
            tape, metas, (policy,), paths=count, path_start=start,
            bootstrap=boot)[policy.name]
        out.append(part.rows)
        if (start + count) % 10000 == 0:
            print(f"MC {label} {start + count}/{paths}", flush=True)
    return CompactRun(policy, np.concatenate(out))


def paired_stage(control_tape, cand_tape, metas, policy_c, policy_k, paths, label):
    boot = common_bootstrap(control_tape, cand_tape)
    print(f"{label}: common blocks={len(boot.eligible_block_starts)}")
    ctl = run_chunks(control_tape, metas, policy_c, boot, paths, f"{label}:ctl")
    cand = run_chunks(cand_tape, metas, policy_k, boot, paths, f"{label}:cand")
    cs, ks = ctl.summary(), cand.summary()
    lower, n10, n01, _, _ = cand.paired_delta_lower(ctl)
    p = (float(binomtest(n10, n10 + n01, 0.5, alternative="greater").pvalue)
         if n10 + n01 else 1.0)
    print(f"  CONTROL H1-only: both={cs.both_probability:.4%} hard={cs.hard_probability:.4%} "
          f"timeout={cs.timeout_probability:.4%} med={cs.median_total_days_success:.0f}d")
    print(f"  TWO-BOOK:        both={ks.both_probability:.4%} hard={ks.hard_probability:.4%} "
          f"timeout={ks.timeout_probability:.4%} med={ks.median_total_days_success:.0f}d")
    gates = dict(hard=ks.hard_probability <= GATE_HARD, paired=lower > 0)
    verdict = "PASS" if all(gates.values()) else "no"
    print(f"  paired lower={lower:+.6f} n10={n10} n01={n01} McNemar p={p:.3g} "
          f"| hard={'Y' if gates['hard'] else 'N'} paired={'Y' if gates['paired'] else 'N'} "
          f"-> {verdict}", flush=True)
    return verdict == "PASS"


def main():
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    control, ccounts = build_h1_universe_tape(SOURCES, **KW_H1)
    print(f"C1-H1 control counts: {ccounts}")
    iv = h1_trade_intervals(control)
    on_events = overnight_events(meta, iv)

    union = tuple(list(control.events) + on_events)
    cand_tape = PassTape.from_events(union, first_day=control.first_day,
                                     last_day=control.last_day)

    base_metas = ftmo_metas(SOURCES)
    metas = dict(base_metas)
    for src in ON_SOURCES:
        sym = {"Japan_225": "JP225.cash", "US_Tech_100": "US100.cash"}[src]
        metas[sym + "#ON"] = replace(base_metas[sym], symbol=sym + "#ON")
    configure_symbols(tuple(metas))

    ctl_risk = dict(BASE_RISK)
    ctl_risk.update({k: 1e-9 for k in metas if k.endswith("#ON")})
    cand_risk = dict(BASE_RISK)
    cand_risk.update({k: SLEEVE for k in metas if k.endswith("#ON")})
    pol_c = RiskPolicy("H1_ONLY", ctl_risk, ctl_risk)
    pol_k = RiskPolicy("TWO_BOOK", cand_risk, cand_risk)

    if paired_stage(control, cand_tape, metas, pol_c, pol_k, 20_000, "SCREEN-20k"):
        print("\nscreen PASS -> running 100k confirmation...")
        ok = paired_stage(control, cand_tape, metas, pol_c, pol_k, 100_000, "CONFIRM-100k")
        print(f"\nCONFIRMATION: {'PASS' if ok else 'FAIL'}")
    else:
        print("\nscreen FAIL - no confirmation run")


if __name__ == "__main__":
    main()
