"""Walk-forward optimization of the W2 configuration (loops, no overfitting).

Pre-registered: docs/WFO_SPEC_2026-07-11.md
  (SHA256 580036f3c64785e1a90f84a4c2a204531f5a904c2b092e62ff278a6b51f00161)
Phase 1: one full-history sim per (config x symbol), 4-way multiprocessing.
Phase 2: expanding-window WF selection loop (LCB) + shuffled-selection control
         + plateau check + verdicts + challenge MC + risk sweep.
"""
import itertools
import os
import pickle
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr, Params, simulate_symbol
from walkforward_dsr import load_spreadgated, real_cost_per_side
from prop_mc_scalper import challenge

STOPS = (0.8, 1.0, 1.25)
TPS = (2.5, 3.0, 3.5, 4.0)
HOLDS = (6, 8, 12, 16)
OFFS = (0.5, 0.6, 0.7)
THRS = (0.25, 0.30, 0.40, 0.50)
BASE = (1.0, 3.0, 8, 0.6, 0.30)
GRID = list(itertools.product(STOPS, TPS, HOLDS, OFFS))
TRIO = {"Wall Street 30", "US Tech 100", "Japan 225"}
CACHE = os.path.join(HERE, "wfo_tapes.pkl")


def sim_one(args):
    sym, csv_path, cost, cfg = args
    stop, tp, hold, off = cfg
    raw = pd.read_csv(csv_path)
    n = {c.lower(): c for c in raw.columns}
    df = raw.rename(columns={n[k]: k for k in ("time", "open", "high", "low", "close") if k in n})
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    up = h - np.maximum(o, c); dn = np.minimum(o, c) - l
    q = pd.PeriodIndex(pd.to_datetime(df["time"]), freq="Q")
    quarters = sorted(q.unique())
    qidx = {qq: i for i, qq in enumerate(quarters)}
    ep = ((pd.to_datetime(df["time"]) - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy()
    recs = []
    for costmult, tag in ((1.0, 0), (2.0, 1)):
        p = Params(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
                   entry_style="limit", entry_offset_atr=off, pending_expiry_bars=3,
                   stop_atr=stop, tp_atr=tp, lock_trigger_atr=999.0, trail_atr=0.0,
                   max_hold_bars=hold, cost_atr_frac=cost * costmult)
        sigs = []
        simulate_symbol(df, p, 0, len(df), signals_out=sigs)
        for (i, eb, side, r) in sigs:
            if not (np.isfinite(atr[i]) and atr[i] > 0):
                continue
            w = (up[i] if side > 0 else dn[i]) / atr[i]
            recs.append((tag, qidx[q[i]], float(w), float(r), int(ep[i])))
    return sym, cfg, recs, [str(x) for x in quarters]


def build_tapes():
    data = load_spreadgated()
    costs = {s: real_cost_per_side(pd.read_csv(os.path.join(
        HERE, "data", "derivM15_spreadgated", s.replace(" ", "_") + ".csv"))) for s in data}
    jobs = []
    for sym in data:
        csvp = os.path.join(HERE, "data", "derivM15_spreadgated", sym.replace(" ", "_") + ".csv")
        for cfg in GRID:
            jobs.append((sym, csvp, costs[sym], cfg))
    print(f"phase 1: {len(jobs)} simulations on 4 processes...", flush=True)
    tapes = {}
    quarters_by_sym = {}
    with Pool(4) as pool:
        for k, (sym, cfg, recs, quarters) in enumerate(pool.imap_unordered(sim_one, jobs, chunksize=8)):
            tapes[(sym, cfg)] = recs
            quarters_by_sym[sym] = quarters
            if (k + 1) % 200 == 0:
                print(f"  {k + 1}/{len(jobs)} sims done", flush=True)
    with open(CACHE, "wb") as f:
        pickle.dump((tapes, quarters_by_sym), f)
    return tapes, quarters_by_sym


def cell_trades(tapes, cfg, thr, syms, tag=0):
    """(qidx_global, r, epoch, sym) for a cell across symbols; quarters aligned by label."""
    rows = []
    for sym in syms:
        for (t, qi, w, r, ep) in tapes[(sym, cfg)]:
            if t == tag and w >= thr:
                rows.append((sym, qi, r, ep))
    return rows


def main():
    if os.path.isfile(CACHE):
        print("loading cached tapes", flush=True)
        with open(CACHE, "rb") as f:
            tapes, quarters_by_sym = pickle.load(f)
    else:
        tapes, quarters_by_sym = build_tapes()

    syms = sorted({s for (s, _) in tapes})
    # global quarter labels (union, sorted); per-symbol qidx maps to its own list ->
    # rebuild global mapping per symbol
    glob_q = sorted({qq for qs in quarters_by_sym.values() for qq in qs})
    gidx = {qq: i for i, qq in enumerate(glob_q)}
    remap = {sym: [gidx[qq] for qq in quarters_by_sym[sym]] for sym in syms}

    def trades_of(cfg, thr, universe, tag=0):
        rows = []
        for sym in universe:
            rm = remap[sym]
            for (t, qi, w, r, ep) in tapes[(sym, cfg)]:
                if t == tag and w >= thr:
                    rows.append((sym, rm[qi], r, ep))
        return rows

    nq = len(glob_q)
    oos_qs = list(range(int(nq * 0.7), nq))
    cells = [(cfg, thr) for cfg in GRID for thr in THRS]
    print(f"{len(cells)} cells | {nq} quarters | OOS folds {len(oos_qs)}", flush=True)

    # precompute per-cell arrays once
    cell_data = {}
    for cfg, thr in cells:
        rows = trades_of(cfg, thr, syms)
        cell_data[(cfg, thr)] = np.array([(q, r) for (_, q, r, _) in rows], dtype=float)

    def lcb(arr, upto_q):
        sel = arr[arr[:, 0] < upto_q][:, 1]
        if len(sel) < 300:
            return -9e9
        return sel.mean() - 1.5 * sel.std(ddof=1) / np.sqrt(len(sel))

    def wf_loop(perm_rng=None):
        """Selection loop; returns stitched OOS trades of the selected cells."""
        out = []
        picks = []
        for k in oos_qs:
            best, best_v = None, -9e9
            for cell, arr in cell_data.items():
                if perm_rng is not None:
                    ismask = arr[:, 0] < k
                    a2 = arr.copy()
                    a2[ismask, 1] = perm_rng.permutation(a2[ismask, 1])
                    v = lcb(a2, k)
                else:
                    v = lcb(arr, k)
                if v > best_v:
                    best_v, best = v, cell
            arr = cell_data[best]
            out += list(arr[arr[:, 0] == k][:, 1])
            picks.append((glob_q[k], best))
        return np.array(out), picks

    print("\nWF selection loop (LCB) over OOS folds...", flush=True)
    opt_oos, picks = wf_loop()
    base_arr = cell_data[(BASE[:4], BASE[4])]
    base_oos = base_arr[np.isin(base_arr[:, 0], oos_qs)][:, 1]
    print("per-fold picks:", flush=True)
    for qq, cell in picks:
        print(f"  {qq}: stop/tp/hold/off={cell[0]} thr={cell[1]}", flush=True)
    rel = (opt_oos.mean() / base_oos.mean() - 1) * 100
    print(f"\nWF-OOS pooled-12: OPTIMIZED {opt_oos.mean():+.4f} (n={len(opt_oos)}) vs "
          f"BASELINE {base_oos.mean():+.4f} (n={len(base_oos)}) -> {rel:+.1f}% relative", flush=True)

    # shuffled-selection control
    print("\nshuffled-selection control (20 loops)...", flush=True)
    rng = np.random.default_rng(11)
    sh = []
    for b in range(20):
        so, _ = wf_loop(perm_rng=rng)
        sh.append(so.mean())
    print(f"  shuffled-selection OOS mean: {np.mean(sh):+.4f} (95pct {np.percentile(sh, 95):+.4f}) "
          f"vs baseline {base_oos.mean():+.4f} -> {'CLEAN (no manufactured edge)' if np.percentile(sh, 95) <= base_oos.mean() * 1.1 else 'WARNING: process manufactures edge'}", flush=True)

    # final config: full-history LCB winner with plateau requirement
    print("\nfinal-config selection (full-history LCB + plateau):", flush=True)
    scored = {}
    for cell, arr in cell_data.items():
        scored[cell] = lcb(arr, nq)
    ranked = sorted(scored.items(), key=lambda kv: -kv[1])

    def neighbors(cell):
        (stop, tp, hold, off), thr = cell
        out = []
        for dim, vals, val in (("s", STOPS, stop), ("t", TPS, tp), ("h", HOLDS, hold),
                               ("o", OFFS, off), ("r", THRS, thr)):
            i = vals.index(val)
            for j in (i - 1, i + 1):
                if 0 <= j < len(vals):
                    ncell = list(cell[0])
                    nthr = thr
                    if dim == "s": ncell[0] = vals[j]
                    if dim == "t": ncell[1] = vals[j]
                    if dim == "h": ncell[2] = vals[j]
                    if dim == "o": ncell[3] = vals[j]
                    if dim == "r": nthr = vals[j]
                    out.append((tuple(ncell), nthr))
        return out

    final = None
    for cell, v in ranked[:20]:
        nbs = [scored.get(nb, -9e9) for nb in neighbors(cell)]
        if v > 0 and all(nv > v - abs(v) * 0.20 for nv in nbs if nv > -9e9) and len(nbs) > 0:
            final = cell
            print(f"  plateau winner: stop/tp/hold/off={cell[0]} thr={cell[1]} (LCB {v:+.4f}); "
                  f"neighbors within 20%", flush=True)
            break
        else:
            print(f"  spike rejected: {cell[0]} thr={cell[1]} (LCB {v:+.4f})", flush=True)
    if final is None:
        print("  no plateau winner -> keep live config"); final = (BASE[:4], BASE[4])

    # trio verdicts + MC + 2x cost for final vs baseline
    for tag_lbl, cell in (("BASELINE", (BASE[:4], BASE[4])), ("FINAL", final)):
        tr_trio = trades_of(cell[0], cell[1], [s for s in syms if s in TRIO])
        oosr = np.array([r for (_, q, r, _) in tr_trio if q in oos_qs])
        tr2 = trades_of(cell[0], cell[1], [s for s in syms if s in TRIO], tag=1)
        oos2 = np.array([r for (_, q, r, _) in tr2 if q in oos_qs])
        days = {}
        for (_, q, r, ep) in tr_trio:
            days.setdefault(ep // 86400, []).append(r)
        dl = list(days.values())
        rng2 = np.random.default_rng(7)
        p1 = float(np.mean([challenge(dl, rng2, 0.5, 10.0, 365)[0] == 1 for _ in range(8000)]))
        p2 = float(np.mean([challenge(dl, rng2, 0.5, 5.0, 365)[0] == 1 for _ in range(4000)]))
        print(f"{tag_lbl} trio: OOS {oosr.mean():+.4f} (n={len(oosr)}) | 2x cost {oos2.mean():+.4f} "
              f"| MC both={p1 * p2:.1%}", flush=True)

    # risk sweep on the final trio tape
    tr_trio = trades_of(final[0], final[1], [s for s in syms if s in TRIO])
    days = {}
    for (_, q, r, ep) in tr_trio:
        days.setdefault(ep // 86400, []).append(r)
    dl = list(days.values())
    print("\nrisk%% sweep on FINAL trio tape (no-time-limit both-phases):", flush=True)
    for risk in (0.4, 0.5, 0.6, 0.7, 0.8):
        rng3 = np.random.default_rng(9)
        p1 = float(np.mean([challenge(dl, rng3, risk, 10.0, 365)[0] == 1 for _ in range(6000)]))
        p2 = float(np.mean([challenge(dl, rng3, risk, 5.0, 365)[0] == 1 for _ in range(3000)]))
        bust = 1 - p1 - float(np.mean([challenge(dl, rng3, risk, 10.0, 365)[0] == -1 for _ in range(2000)]))
        print(f"  risk {risk:.1f}%: both={p1 * p2:.1%} (P1 {p1:.1%}, P2 {p2:.1%})", flush=True)

    print("\nDONE.", flush=True)


if __name__ == "__main__":
    main()
