"""Fill-realism reconciliation for the pullback LIMIT entry (HANDOFF backlog #3 / brief P1).

The harness assumes the limit fills AT its price whenever the bar range touches it
within pending_expiry_bars. Live day-1 showed 75% fill rate vs ~59% modeled and
frequent price improvement (conservative) — but N=20. This tool makes the
reconciliation repeatable so it can be run weekly as live N accumulates.

Three layers, reconciled per pending order (from MT5 history, magic 770077):
  1. PLACEMENT: every limit order the EA placed (filled OR canceled/expired).
  2. LIVE OUTCOME: did it fill? at what price vs the limit (improvement/slippage)?
  3. HARNESS PREDICTION: replay the same M15 bars — would simulate_symbol_c's fill
     rule (bar low<=limit for buys / bar high>=limit for sells, within
     pending_expiry_bars of placement) have predicted a fill?

Optionally parses EA Experts logs (--logs <dir-or-file>) for SIGNAL lines to catch
signals that never became placements (lot refusal, retcode failures) — those are
invisible to order history.

Output: confusion matrix (live fill x harness fill), fill-rate comparison,
price-improvement stats in ATR and R, and the pessimistic-fill deltas the
acceptance criterion needs (non-filling impulses counted as missed winners).

Acceptance (HANDOFF #3): harness fill model shown conservative or corrected;
edge sign unchanged under pessimistic fill.

Run on the machine with the MT5 terminal open:  python fill_realism.py
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import re
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

MAGIC = 770077
FRM = datetime(2026, 6, 29)
PENDING_EXPIRY_BARS = 3        # matches InpPendingExpiryBars / CParams.pending_expiry_bars
M15_MIN = 15

SIGNAL_RE = re.compile(
    r"SIGNAL (?P<sym>.+?) (?P<tag>BUY LIMIT|SELL LIMIT|BUY STOP|SELL STOP) "
    r"(?P<lots>[\d.]+) lots entry=(?P<entry>[\d.]+) \(anchor=(?P<anchor>[\d.]+)\) "
    r"SL=(?P<sl>[\d.]+) TP=(?P<tp>[\d.]+) \| ATR=(?P<atr>[\d.]+) "
    r"impulse=(?P<imp>-?[\d.]+) spread/ATR/side=(?P<spr>[\d.]+)")


def parse_signal_logs(path):
    """SIGNAL lines from EA Experts log file(s); returns list of dicts."""
    files = []
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "*.log")))
    elif os.path.isfile(path):
        files = [path]
    out = []
    for fn in files:
        with open(fn, errors="replace") as f:
            for line in f:
                m = SIGNAL_RE.search(line)
                if m:
                    out.append({k: m.group(k) for k in
                                ("sym", "tag", "lots", "entry", "anchor", "sl", "tp",
                                 "atr", "imp", "spr")})
    return out


def harness_would_fill(sym, t_setup, limit, is_buy, expiry_bars=PENDING_EXPIRY_BARS):
    """Replay the harness fill rule on the symbol's own M15 bars after placement.

    The harness checks bars i+1 .. i+expiry_bars after the signal bar; live
    placement happens right after the signal bar closes, so the window here is the
    expiry_bars bars that OPEN at/after the placement time."""
    r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M15, t_setup - timedelta(minutes=M15_MIN),
                             t_setup + timedelta(minutes=M15_MIN * (expiry_bars + 1)))
    if r is None or len(r) == 0:
        return None
    df = pd.DataFrame(r)
    setup_ts = int(t_setup.timestamp())
    # Bars whose OPEN time is at/after the placement bar's open (the placement bar
    # itself counts: the harness fill window starts at the bar after the signal bar,
    # which is the bar the order goes live in).
    live = df[df.time >= setup_ts // (M15_MIN * 60) * (M15_MIN * 60)].head(expiry_bars)
    if live.empty:
        return None
    if is_buy:
        return bool((live.low <= limit).any())
    return bool((live.high >= limit).any())


def main():
    ap = argparse.ArgumentParser(description="Pullback-limit fill realism reconciliation")
    ap.add_argument("--logs", default=None, help="EA Experts log file or directory (optional)")
    ap.add_argument("--frm", default=None, metavar="YYYY-MM-DD",
                    help=f"history start (default {FRM:%Y-%m-%d})")
    args = ap.parse_args()
    frm = datetime.strptime(args.frm, "%Y-%m-%d") if args.frm else FRM

    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    now = datetime.now() + timedelta(days=1)
    orders = [o for o in (mt5.history_orders_get(frm, now) or []) if o.magic == MAGIC]

    recs = []
    for o in orders:
        if o.type not in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT):
            continue
        is_buy = o.type == mt5.ORDER_TYPE_BUY_LIMIT
        t_setup = datetime.fromtimestamp(o.time_setup)
        filled = o.state == mt5.ORDER_STATE_FILLED
        # fill price: entry deal of the position
        fill_px = None
        if filled and o.position_id:
            for d in (mt5.history_deals_get(position=o.position_id) or []):
                if d.entry == mt5.DEAL_ENTRY_IN:
                    fill_px = d.price
                    break
        pred = harness_would_fill(o.symbol, t_setup, o.price_open, is_buy)
        risk = abs(o.price_open - o.sl) if o.sl else None
        # price improvement in R: positive = filled better than the limit
        impr_r = None
        if fill_px is not None and risk:
            impr_r = ((o.price_open - fill_px) if is_buy else (fill_px - o.price_open)) / risk
        recs.append(dict(
            ticket=o.ticket, sym=o.symbol, side="BUY" if is_buy else "SELL",
            t_setup=str(t_setup), limit=o.price_open, sl=o.sl, tp=o.tp,
            state={mt5.ORDER_STATE_FILLED: "FILLED", mt5.ORDER_STATE_CANCELED: "CANCELED",
                   mt5.ORDER_STATE_EXPIRED: "EXPIRED"}.get(o.state, str(o.state)),
            live_filled=filled, fill_px=fill_px,
            harness_predicts_fill=pred,
            improvement_r=None if impr_r is None else round(impr_r, 4),
        ))
    mt5.shutdown()

    with open("fill_realism.json", "w") as f:
        json.dump(recs, f, indent=1, default=str)

    if not recs:
        print("No pullback limit orders in history - nothing to reconcile.")
        return

    n = len(recs)
    live_fills = [r for r in recs if r["live_filled"]]
    known = [r for r in recs if r["harness_predicts_fill"] is not None]
    print(f"PULLBACK LIMIT ORDERS: {n}   live fill rate {len(live_fills)}/{n} = "
          f"{len(live_fills)/n*100:.0f}%")
    if known:
        pred_fills = [r for r in known if r["harness_predicts_fill"]]
        print(f"harness-predicted fill rate (same orders, M15 replay): "
              f"{len(pred_fills)}/{len(known)} = {len(pred_fills)/len(known)*100:.0f}%")
        # confusion matrix
        both = sum(1 for r in known if r["live_filled"] and r["harness_predicts_fill"])
        live_only = sum(1 for r in known if r["live_filled"] and not r["harness_predicts_fill"])
        pred_only = sum(1 for r in known if not r["live_filled"] and r["harness_predicts_fill"])
        neither = sum(1 for r in known if not r["live_filled"] and not r["harness_predicts_fill"])
        print("\n              harness:fill  harness:no-fill")
        print(f"live:fill     {both:12d}  {live_only:15d}")
        print(f"live:no-fill  {pred_only:12d}  {neither:15d}")
        if live_only:
            print(f"\n{live_only} live fills the harness would NOT predict (harness conservative "
                  "on fills = harness misses winners it would not have counted - safe direction).")
        if pred_only:
            print(f"{pred_only} harness-predicted fills that did NOT fill live (harness optimistic "
                  "- the dangerous direction; if this grows, correct the fill model):")
            for r in known:
                if not r["live_filled"] and r["harness_predicts_fill"]:
                    print(f"    {r['t_setup'][5:16]} {r['sym']:14s} {r['side']:4s} "
                          f"limit {r['limit']} [{r['state']}]")
    imps = [r["improvement_r"] for r in recs if r["improvement_r"] is not None]
    if imps:
        a = np.array(imps)
        print(f"\nprice improvement vs limit (R): median {np.median(a):+.4f}  "
              f"mean {a.mean():+.4f}  worst {a.min():+.4f}  "
              f"(positive = better than limit; harness assumes 0)")

    if args.logs:
        signals = parse_signal_logs(args.logs)
        print(f"\nSIGNAL lines parsed from logs: {len(signals)} "
              f"(vs {n} placements in history)")
        if len(signals) > n:
            print(f"  {len(signals) - n} signals never became history placements "
                  "(lot refusal / retcode failure) - inspect the log lines around them.")

    print("\nACCEPTANCE (HANDOFF #3): keep running weekly; the harness fill model is "
          "acceptable while 'live:no-fill x harness:fill' stays ~0 and improvement >= 0. "
          "The pessimistic-fill backtest (non-fills as missed winners) is the "
          "harness-side half - run experiment.py with entry_style='limit' unchanged; "
          "the sign must not flip.")


if __name__ == "__main__":
    main()
