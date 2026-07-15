"""Stage A of the preregistered order-flow overlay screen (2026-07-15).

Spec: docs/ORDERFLOW_OVERLAY_SPEC_2026-07-15.md (committed before this file).
Reuses the registered v1.30/v1.31 geometry verbatim (prep_symbol / resolve_v130
/ run_cell loop) and conditions each conditioned trade's decision time on
tick-rule order-flow states computed causally from the frozen FTMO tick
parquets. Two fixed arms; permutation gates; no sweeps.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from parity_engine import START, prep_symbol
from run_h1_timeframe_screen import run_cell
from run_h1_universe_screen import aggregate_h1_fast, load_symbol, source_path
from session_study import resolve_v130

HERE = Path(__file__).resolve().parent
META_PATH = HERE / "h1_universe_broker_meta.json"
RESULT_PATH = HERE / "orderflow_overlay_results.json"
TICK_DIR = Path(r"C:\Users\Sanique Richards\Documents\Homework Heroes\Pokemon\orderflow-ea\data")
NY = ZoneInfo("America/New_York")
SEED = 13020260715
N_PERM = 10_000

CONDITIONED = {
    "US_Tech_100": dict(ftmo="US100.cash", ticks="US100_cash_ticks.parquet", fp=0.25,
                        sha="3ea00484508af85b73a7fc123ee8d03c6fa0ad52fb3288680ee12c0699dfa733"),
    "Wall_Street_30": dict(ftmo="US30.cash", ticks="US30_cash_ticks.parquet", fp=1.0,
                           sha="f83d41f2600f9b061bf8992519621cd003e958ee411aa2403eca10f24b8ba1a2"),
}


# ---------------- tape trades (registered geometry, extended record) ---------
def run_cell_trades(s):
    """Verbatim run_cell loop with side/fill added; parity-asserted below."""
    out = []
    i = START
    while i < len(s.c) - 1:
        side = int(s.side[i])
        if side == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < 0.30:
            i += 1
            continue
        entry = s.c[i] - 0.6 * s.atr[i] * side
        j = -1
        for b in range(i + 1, min(i + 4, len(s.c))):
            if (side > 0 and s.l[b] <= entry) or (side < 0 and s.h[b] >= entry):
                j = b
                break
        if j < 0:
            i += 4
            continue
        xb, r = resolve_v130(s, j, side, entry, s.atr[i])
        out.append(dict(ep=int(s.ep[i]), side=side, fill_ep=int(s.ep[j]),
                        r=float(r), oos=bool(s.oos[i])))
        i = xb + 1
    return out


def build_trades(source: str, meta: dict) -> list[dict]:
    loaded = load_symbol(source, meta)
    trades = {}
    for name, mult in (("E1", 1.0), ("E2", 2.0)):
        prepared = prep_symbol(loaded.h1, loaded.cost_e1 * mult, source)
        prepared.oos = np.arange(len(loaded.h1)) >= int(len(loaded.h1) * 0.7)
        rows_ref = run_cell(prepared, market=False)
        recs = run_cell_trades(prepared)
        assert [(t["ep"], t["r"], t["oos"]) for t in recs] == \
               [(int(a), float(b), bool(c)) for a, b, c in rows_ref], \
               f"parity break vs run_cell on {source}/{name}"
        trades[name] = recs
    # E1/E2 trade lists must align one-to-one (same signals, different cost R)
    assert [(t["ep"], t["side"]) for t in trades["E1"]] == \
           [(t["ep"], t["side"]) for t in trades["E2"]]
    out = []
    for t1, t2 in zip(trades["E1"], trades["E2"]):
        out.append(dict(ep=t2["ep"], side=t2["side"], fill_ep=t2["fill_ep"],
                        r_e1=t1["r"], r_e2=t2["r"], oos=t2["oos"]))
    return out


# ---------------- causal tick states -----------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def tick_rule_deltas(bid: np.ndarray, fp: float) -> np.ndarray:
    """Per-tick signed step on the futures grid; anchor resets handled per-bar
    by the caller (bar loop) exactly as the EA engine does."""
    return bid  # placeholder (unused; logic lives in day_states)


def day_states(tms_s, bid, fp, open_s, t_decs):
    """For one session: returns {t_dec: (covered, session_delta, last_bar_delta,
    avg_abs_delta)} computed causally from ticks <= t_dec.

    Bars accumulate from open_s - 1800 (09:00 ET) per the runner convention
    declared in the results doc; session delta accumulates from the first tick
    at/after open_s. Zero-delta minutes are dropped from the completed-bar list
    (EA convention). Tick-rule: bucket threshold 0.4*fp, anchor resets each
    minute (EA convention).
    """
    t0 = open_s - 1800
    a = int(np.searchsorted(tms_s, t0))
    z = int(np.searchsorted(tms_s, max(t_decs) + 1))
    tt = tms_s[a:z]
    bb = bid[a:z]
    n = len(tt)
    out = {}
    if n == 0:
        return {td: (False, 0, 0, 0.0) for td in t_decs}

    # coverage: a tick at/before the open, and no gap > 600s in [open, t_dec]
    def covered(td):
        if tt[0] > open_s:
            return False
        lo = int(np.searchsorted(tt, open_s, side="right")) - 1   # last tick <= open
        hi = int(np.searchsorted(tt, td, side="right"))
        if hi - lo < 2:
            return False
        gaps = np.diff(tt[lo:hi])
        return gaps.max() <= 600

    # per-tick signed step with per-minute anchor reset (EA convention)
    minute = tt // 60
    step = np.zeros(n, dtype=np.int64)
    thresh = fp * 0.4
    anchor = 0.0
    cur_min = -1
    for i in range(n):
        if minute[i] != cur_min:
            cur_min = minute[i]
            anchor = 0.0
        b = bb[i]
        s = 0
        if anchor > 0:
            if b > anchor + thresh:
                s = 1
            elif b < anchor - thresh:
                s = -1
        if s != 0 or anchor == 0:
            anchor = b            # EA convention: anchor moves on a step or first tick
        step[i] = s

    # completed-bar deltas (zero-delta minutes dropped)
    bar_ids = np.unique(minute)
    bar_delta = {}
    for m in bar_ids:
        d = int(step[minute == m].sum())
        if d != 0:
            bar_delta[int(m)] = d

    # session cumulative delta from first tick >= open
    sess_mask = tt >= open_s
    cum = np.cumsum(np.where(sess_mask, step, 0))

    for td in t_decs:
        ok = covered(td)
        hi = int(np.searchsorted(tt, td, side="right"))
        sd = int(cum[hi - 1]) if hi > 0 else 0
        # completed bars: bins with start+60 <= td, from ticks < td (ticks at
        # td are excluded from the last bin by construction of hi)
        last_m = td // 60 - 1
        comp = [(m, d) for m, d in sorted(bar_delta.items()) if (m + 1) * 60 <= td]
        lastd = comp[-1][1] if comp else 0
        tail = [abs(d) for _, d in comp[-30:]]
        avg = float(np.mean(tail)) if len(tail) >= 5 else 0.0
        out[td] = (ok, sd, lastd, avg)
    return out


def condition_trades(trades: list[dict], tick_file: Path, fp: float) -> list[dict]:
    df = pd.read_parquet(tick_file, columns=["time_msc", "bid"])
    tms_s = (df["time_msc"].values // 1000).astype(np.int64)
    bid = df["bid"].values.astype(np.float64)
    lo_cov, hi_cov = tms_s[0], tms_s[-1]

    # group candidate trades by NY session date
    by_day = {}
    for t in trades:
        t_dec = t["ep"] + 3600
        if not (lo_cov <= t_dec <= hi_cov):
            continue
        dt = datetime.fromtimestamp(t_dec, timezone.utc).astimezone(NY)
        if dt.weekday() >= 5:
            continue
        open_ny = dt.replace(hour=9, minute=30, second=0, microsecond=0)
        close_ny = dt.replace(hour=11, minute=30, second=0, microsecond=0)
        if not (open_ny <= dt <= close_ny):
            continue
        open_s = int(open_ny.timestamp())
        by_day.setdefault((dt.date(), open_s), []).append(t)

    conditioned = []
    for (d, open_s), ts in sorted(by_day.items()):
        t_decs = [t["ep"] + 3600 for t in ts]
        states = day_states(tms_s, bid, fp, open_s, t_decs)
        for t in ts:
            ok, sd, lastd, avg = states[t["ep"] + 3600]
            if not ok:
                continue
            rec = dict(t)
            rec["session_delta"] = sd
            rec["last_bar_delta"] = lastd
            rec["avg_abs_delta"] = avg
            # Arm P: session-delta agreement (zero delta = veto)
            rec["p_confirm"] = bool(sd * t["side"] > 0)
            # Arm S: opposing-aggression veto (no baseline -> confirm)
            rec["s_confirm"] = not (avg > 0 and t["side"] * lastd <= -1.5 * avg)
            conditioned.append(rec)
    return conditioned


# ---------------- statistics --------------------------------------------------
def arm_stats(cond: list[dict], key: str, rng) -> dict:
    r = np.array([t["r_e2"] for t in cond])
    sym = np.array([t["symbol"] for t in cond])
    conf = np.array([t[key] for t in cond])
    n, nc, nv = len(r), int(conf.sum()), int((~conf).sum())
    res = dict(n_conditioned=n, n_confirmed=nc, n_vetoed=nv)
    if n == 0 or nv == 0 or nc == 0:
        res["gap"] = None
        res["perm_p"] = None
        res["mean_r_confirmed"] = float(r[conf].mean()) if nc else None
        res["mean_r_vetoed"] = float(r[~conf].mean()) if nv else None
        res["mean_r_all"] = float(r.mean()) if n else None
        return res
    g_obs = r[conf].mean() - r[~conf].mean()
    perm = np.empty(N_PERM)
    for k in range(N_PERM):
        pconf = np.empty(n, dtype=bool)
        for s in np.unique(sym):
            m = sym == s
            pconf[m] = rng.permutation(conf[m])
        # within-symbol permutation preserves overall veto count -> both groups
        # are guaranteed non-empty (nc>0 and nv>0 checked above)
        perm[k] = r[pconf].mean() - r[~pconf].mean()
    res.update(
        mean_r_all=float(r.mean()),
        mean_r_confirmed=float(r[conf].mean()),
        mean_r_vetoed=float(r[~conf].mean()),
        gap=float(g_obs),
        perm_p=float((perm >= g_obs).mean()),
    )
    # OOS-only secondary split
    oos = np.array([t["oos"] for t in cond])
    if oos.any():
        ro, co = r[oos], conf[oos]
        res["oos"] = dict(
            n=int(oos.sum()),
            n_vetoed=int((~co).sum()),
            mean_r_confirmed=float(ro[co].mean()) if co.any() else None,
            mean_r_vetoed=float(ro[~co].mean()) if (~co).any() else None,
        )
    return res


def gates(p: dict) -> tuple[str, list[str]]:
    fails = []
    if p["n_conditioned"] < 40 or p["n_vetoed"] < 10:
        return "INSUFFICIENT_SAMPLE", [f"n_cond={p['n_conditioned']}", f"n_veto={p['n_vetoed']}"]
    if p["mean_r_vetoed"] is None or p["mean_r_vetoed"] >= 0:
        fails.append("VETOED_MEAN_R_NOT_NEGATIVE")
    if p["perm_p"] is None or p["perm_p"] > 0.05:
        fails.append("PERMUTATION_P_GT_0.05")
    if p["mean_r_confirmed"] is None or p["mean_r_confirmed"] <= p["mean_r_all"]:
        fails.append("OVERLAY_NOT_ABOVE_CONTROL")
    return ("PASS" if not fails else "FAIL"), fails


def main() -> None:
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    rng = np.random.default_rng(SEED)

    all_cond = []
    provenance = {}
    for source, info in CONDITIONED.items():
        tick_file = TICK_DIR / info["ticks"]
        sha = sha256_file(tick_file)
        assert sha == info["sha"], f"tick hash mismatch for {info['ticks']}: {sha}"
        provenance[info["ticks"]] = sha
        trades = build_trades(source, meta)
        cond = condition_trades(trades, tick_file, info["fp"])
        for t in cond:
            t["symbol"] = info["ftmo"]
        print(f"{info['ftmo']}: tape trades={len(trades)} conditioned={len(cond)} "
              f"(P-vetoed={sum(1 for t in cond if not t['p_confirm'])}, "
              f"S-vetoed={sum(1 for t in cond if not t['s_confirm'])})", flush=True)
        all_cond.extend(cond)

    arm_p = arm_stats(all_cond, "p_confirm", rng)
    arm_s = arm_stats(all_cond, "s_confirm", rng)
    verdict, fails = gates(arm_p)

    out = dict(
        spec="docs/ORDERFLOW_OVERLAY_SPEC_2026-07-15.md",
        engine_commit="61f42c9",
        tick_provenance=provenance,
        seed=SEED,
        n_permutations=N_PERM,
        arm_p_primary=arm_p,
        arm_s_secondary=arm_s,
        stage_a_verdict=verdict,
        gate_failures=fails,
        conditioned_trades=[
            {k: t[k] for k in ("symbol", "ep", "side", "r_e1", "r_e2", "oos",
                                "session_delta", "last_bar_delta", "avg_abs_delta",
                                "p_confirm", "s_confirm")}
            for t in all_cond
        ],
    )
    RESULT_PATH.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("ARM_P", json.dumps({k: v for k, v in arm_p.items() if k != "oos"}))
    print("ARM_S", json.dumps({k: v for k, v in arm_s.items() if k != "oos"}))
    print("STAGE_A_VERDICT", verdict, ",".join(fails) if fails else "all gates met")
    print("RESULT_FILE", RESULT_PATH)


if __name__ == "__main__":
    main()
