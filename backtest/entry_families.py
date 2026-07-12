"""Four entry-family screen from the owner's research paste.

Pre-registered: docs/ENTRY_FAMILIES_SPEC_2026-07-13.md
  (SHA256 de3b503ae47f2e6a2e4f122f54f608daaf8edd71eefc87e3f5871c6c464895ae)

Live-parity enumeration, symmetric long/short, real cost, trio + holdout.
SCREEN: all cells reported; promotions need the full gate + forward validation.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nearmiss_decisions import daylist, challenge_mc
from scalper_backtest import wilder_atr, ema
from walkforward_dsr import real_cost_per_side

TRIO = [("Wall_Street_30", "derivM15_spreadgated"), ("US_Tech_100", "derivM15_spreadgated"),
        ("Japan_225", "derivM15_spreadgated")]
HOLDOUT = [("Germany_40", "derivM15_spreadgated"), ("US_SP_500", "derivM15_spreadgated"),
           ("UK_100", "derivM15_spreadgated"), ("France_40", "derivM15_spreadgated"),
           ("US_Small_Cap_2000", "derivM15_spreadgated"), ("Australia_200", "derivM15_diverse"),
           ("Hong_Kong_50", "derivM15_diverse"), ("EURUSD", "derivM15_diverse"),
           ("XAUUSD", "derivM15_diverse"), ("XAGUSD", "derivM15_diverse")]

WINDOW = 4       # stop-entry rest window (live pending semantics)
SAFETY_HOLD = 96
LOOKBACK = 96    # swing machinery
TRAIL_A = 3.0


def rma(x, n):
    out = np.full_like(x, np.nan, dtype=float)
    if len(x) <= n:
        return out
    out[n] = np.nanmean(x[1:n + 1])
    a = 1.0 / n
    for i in range(n + 1, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out


def rsi(c, n):
    d = np.diff(c, prepend=c[0])
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    au, ad = rma(up, n), rma(dn, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = au / ad
        out = 100.0 - 100.0 / (1.0 + rs)
    out[np.isnan(au) | np.isnan(ad)] = np.nan
    out[(ad == 0) & np.isfinite(au)] = 100.0
    return out


def sma(x, n):
    s = pd.Series(x).rolling(n).mean().to_numpy()
    return s


def stoch(h, l, c, n=14, k_s=3, d_s=3):
    hh = pd.Series(h).rolling(n).max().to_numpy()
    ll = pd.Series(l).rolling(n).min().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        fast = 100.0 * (c - ll) / (hh - ll)
    k = sma(fast, k_s)
    d = sma(k, d_s)
    return k, d


def adx(h, l, c, n=14):
    up = np.diff(h, prepend=h[0])
    dn = -np.diff(l, prepend=l[0])
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    prev_c = np.roll(c, 1)
    prev_c[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atrn = rma(tr, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100.0 * rma(plus_dm, n) / atrn
        mdi = 100.0 * rma(minus_dm, n) / atrn
        dx = 100.0 * np.abs(pdi - mdi) / (pdi + mdi)
    return rma(dx, n), pdi, mdi


class Sym:
    def __init__(self, key, sub):
        raw = pd.read_csv(os.path.join(HERE, "data", sub, key + ".csv"))
        nm = {c.lower(): c for c in raw.columns}
        df = raw.rename(columns={nm[k]: k for k in ("time", "open", "high", "low", "close") if k in nm})
        self.name = key
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        cost = real_cost_per_side(raw)
        self.cost = cost if np.isfinite(cost) else 0.03
        dt = pd.to_datetime(df["time"])
        if getattr(dt.dt, "tz", None) is not None:
            dt = dt.dt.tz_convert("UTC").dt.tz_localize(None)
        self.ep = ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy().astype(np.int64)
        q = pd.PeriodIndex(dt, freq="Q")
        qs = sorted(q.unique())
        oq = set(qs[int(len(qs) * 0.7):])
        self.oos = np.array([qq in oq for qq in q])
        c_, h_, l_ = self.c, self.h, self.l
        self.atr = wilder_atr(h_, l_, c_, 14)
        self.sma200 = sma(c_, 200)
        self.sma50 = sma(c_, 50)
        self.ema20 = ema(c_, 20)
        self.ema50 = ema(c_, 50)
        self.rsi2 = rsi(c_, 2)
        self.rsi14 = rsi(c_, 14)
        self.stk, self.std_ = stoch(h_, l_, c_)
        m12, m26 = ema(c_, 12), ema(c_, 26)
        self.macd = m12 - m26
        self.macds = ema(self.macd, 9)
        self.adx14, self.pdi, self.mdi = adx(h_, l_, c_)
        # swing machinery per bar (long side; mirrored inline for shorts)
        self.sh_idx = pd.Series(self.h).rolling(LOOKBACK).apply(np.argmax, raw=True).to_numpy()
        self.sl_idx = pd.Series(self.l).rolling(LOOKBACK).apply(np.argmin, raw=True).to_numpy()


def swing_long(s, t):
    """(swing_low, swing_high, pullback_low) for the up-leg ending near t."""
    w0 = t - LOOKBACK + 1
    if w0 < 0:
        return None
    shi = int(s.sh_idx[t]) + w0
    sh = s.h[shi]
    if shi <= w0:
        return None
    sl = s.l[w0:shi].min()
    if not np.isfinite(sh - sl) or (sh - sl) < 2.0 * s.atr[t]:
        return None
    pl = s.l[shi:t + 1].min()
    return sl, sh, pl


def swing_short(s, t):
    w0 = t - LOOKBACK + 1
    if w0 < 0:
        return None
    sli = int(s.sl_idx[t]) + w0
    slo = s.l[sli]
    if sli <= w0:
        return None
    sh = s.h[w0:sli].max()
    if not np.isfinite(sh - slo) or (sh - slo) < 2.0 * s.atr[t]:
        return None
    ph = s.h[sli:t + 1].max()
    return slo, sh, ph


def fin(*xs):
    return all(np.isfinite(x) for x in xs)


def signal(s, t, fam):
    """Return (side, entry_kind, entry_px, stop_px) or None. entry_kind:
    'stop' (rest WINDOW bars) or 'market' (fill at o[t+1])."""
    a = s.atr[t]
    if not fin(a) or a <= 0:
        return None
    for sd in (1, -1):
        c = s.c[t] * sd
        if sd > 0:
            trend200 = fin(s.sma200[t]) and s.c[t] > s.sma200[t]
            ema_stack = fin(s.ema20[t], s.ema50[t]) and s.c[t] > s.ema20[t] > s.ema50[t]
            e5_gt_s2 = fin(s.ema50[t], s.sma200[t]) and s.ema50[t] > s.sma200[t]
            pa = s.c[t] > s.h[t - 1]
        else:
            trend200 = fin(s.sma200[t]) and s.c[t] < s.sma200[t]
            ema_stack = fin(s.ema20[t], s.ema50[t]) and s.c[t] < s.ema20[t] < s.ema50[t]
            e5_gt_s2 = fin(s.ema50[t], s.sma200[t]) and s.ema50[t] < s.sma200[t]
            pa = s.c[t] < s.l[t - 1]
        if not pa:
            continue

        if fam == "F1":
            if not (trend200 and fin(s.sma50[t], s.sma50[t - 5])):
                continue
            rising = (s.sma50[t] > s.sma50[t - 5]) if sd > 0 else (s.sma50[t] < s.sma50[t - 5])
            touch = ((s.l[t] <= s.ema20[t] or s.l[t] <= s.ema50[t]) if sd > 0
                     else (s.h[t] >= s.ema20[t] or s.h[t] >= s.ema50[t]))
            osold = ((s.rsi2[t] < 15 or 40 <= s.rsi14[t] <= 50) if sd > 0
                     else (s.rsi2[t] > 85 or 50 <= s.rsi14[t] <= 60))
            if not (rising and touch and fin(s.rsi14[t]) and osold):
                continue
            entry = s.h[t] if sd > 0 else s.l[t]
            stop = (min(s.l[t] - 0.5 * a, entry - 2.0 * a) if sd > 0
                    else max(s.h[t] + 0.5 * a, entry + 2.0 * a))
            return sd, "stop", entry, stop

        if fam == "F2":
            if not e5_gt_s2:
                continue
            sw = swing_long(s, t) if sd > 0 else swing_short(s, t)
            if sw is None:
                continue
            slo, shi, _ = sw
            retr = ((shi - s.l[t]) / (shi - slo)) if sd > 0 else ((s.h[t] - slo) / (shi - slo))
            k1, k0, d0 = s.stk[t - 1], s.stk[t], s.std_[t]
            if not fin(retr, k1, k0, d0) or not (0.382 <= retr <= 0.618):
                continue
            cross = (k1 < 20 and k0 > 20 and k0 > d0) if sd > 0 else (k1 > 80 and k0 < 80 and k0 < d0)
            if not cross:
                continue
            entry = s.h[t] if sd > 0 else s.l[t]
            stop = (min(slo - 1.5 * a, s.l[t] - 0.5 * a) if sd > 0
                    else max(shi + 1.5 * a, s.h[t] + 0.5 * a))
            return sd, "stop", entry, stop

        if fam == "F3":
            macd_ok = ((s.macd[t] > s.macds[t] and s.macd[t] > 0) if sd > 0
                       else (s.macd[t] < s.macds[t] and s.macd[t] < 0))
            if not (e5_gt_s2 and fin(s.adx14[t]) and s.adx14[t] > 25 and macd_ok):
                continue
            sw = swing_long(s, t) if sd > 0 else swing_short(s, t)
            if sw is None:
                continue
            slo, shi, pull = sw
            retr = ((shi - s.l[t]) / (shi - slo)) if sd > 0 else ((s.h[t] - slo) / (shi - slo))
            at_ema = (s.c[t] >= s.ema50[t]) if sd > 0 else (s.c[t] <= s.ema50[t])
            if not (fin(retr) and retr <= 0.382 and at_ema):
                continue
            stop = (pull - 2.0 * a) if sd > 0 else (pull + 2.0 * a)
            return sd, "market", np.nan, stop

        if fam == "F4":
            if not (ema_stack and fin(s.sma200[t]) and
                    ((s.ema50[t] > s.sma200[t]) if sd > 0 else (s.ema50[t] < s.sma200[t]))):
                continue
            win = s.rsi14[t - 5:t]
            if not (fin(s.adx14[t]) and s.adx14[t] > 20 and np.isfinite(win).all()):
                continue
            dipped = ((40 <= win.min() <= 50) if sd > 0 else (50 <= win.max() <= 60))
            accel = (s.rsi14[t] > 50) if sd > 0 else (s.rsi14[t] < 50)
            if not (dipped and accel):
                continue
            entry = np.nan
            ref = s.c[t]
            stop = (min(s.l[t] - 0.5 * a, ref - 1.75 * a) if sd > 0
                    else max(s.h[t] + 0.5 * a, ref + 1.75 * a))
            return sd, "market", entry, stop
    return None


def manage(s, fam, sd, j, entry, stop, a_sig):
    """Bar-by-bar management per family. Returns (exit_bar, r_total)."""
    risk = (entry - stop) * sd
    if risk <= 0:
        return j, 0.0
    banked, frac = 0.0, 1.0
    partial1_done = partial2_done = False
    be_moved = False
    hi_close = -np.inf
    below_ema = 0
    n = len(s.c)
    cost_r = 2.0 * s.cost * a_sig / risk
    sl = stop
    for k in range(j, min(j + SAFETY_HOLD, n)):
        # intrabar: stop first (pessimistic)
        if sd > 0 and s.l[k] <= sl:
            return k, banked + frac * (sl - entry) * sd / risk - cost_r
        if sd < 0 and s.h[k] >= sl:
            return k, banked + frac * (sl - entry) * sd / risk - cost_r
        prog = (s.h[k] - entry) * sd / risk if sd > 0 else (entry - s.l[k]) / risk
        if fam == "F1" and not partial1_done and prog >= 1.5:
            banked += 0.5 * 1.5
            frac -= 0.5
            partial1_done = True
            sl = entry  # break-even
        if fam == "F2":
            if not partial1_done and prog >= 1.0:
                banked += 0.33 * 1.0
                frac -= 0.33
                partial1_done = True
            if not partial2_done and prog >= 2.0:
                banked += 0.33 * 2.0
                frac -= 0.33
                partial2_done = True
        if fam == "F3" and not partial1_done and prog >= 2.0:
            banked += 0.33 * 2.0
            frac -= 0.33
            partial1_done = True
        # end-of-bar management: 3xATR trail off the best close (signed space)
        hi_close = max(hi_close, s.c[k] * sd)
        if sd > 0:
            sl = max(sl, hi_close - TRAIL_A * s.atr[k])
        else:
            sl = min(sl, -hi_close + TRAIL_A * s.atr[k])
        # family close-out rules at bar close
        if fam == "F1" and ((s.c[k] < s.ema20[k]) if sd > 0 else (s.c[k] > s.ema20[k])):
            if (s.c[k] - entry) * sd > 0:
                return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r
        if fam == "F3":
            macd_off = ((s.macd[k] < s.macds[k] and s.c[k] < s.ema20[k]) if sd > 0
                        else (s.macd[k] > s.macds[k] and s.c[k] > s.ema20[k]))
            if macd_off:
                return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r
        if fam == "F4":
            below = (s.c[k] < s.ema20[k]) if sd > 0 else (s.c[k] > s.ema20[k])
            below_ema = below_ema + 1 if below else 0
            if below_ema >= 2:
                return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r
    k = min(j + SAFETY_HOLD - 1, n - 1)
    return k, banked + frac * (s.c[k] - entry) * sd / risk - cost_r


def run_family(s, fam):
    out = []
    n = len(s.c)
    START = 220
    i = START
    while i < n - 1:
        sig = signal(s, i, fam)
        if sig is None:
            i += 1
            continue
        sd, kind, entry, stop = sig
        a = s.atr[i]
        if kind == "market":
            j = i + 1
            entry = s.o[j]
            if (entry - stop) * sd <= 0:
                i += 1
                continue
        else:
            j = -1
            for b in range(i + 1, min(i + 1 + WINDOW, n)):
                if (sd > 0 and s.h[b] >= entry) or (sd < 0 and s.l[b] <= entry):
                    j = b
                    break
            if j < 0:
                i = i + WINDOW
                continue
        xb, r = manage(s, fam, sd, j, entry, stop, a)
        out.append((int(s.ep[i]), r, bool(s.oos[i])))
        i = xb + 1
    return out


def report(tape, label):
    if not tape:
        print(f"  {label}: no trades")
        return
    r = np.array([x[1] for x in tape])
    ro = np.array([x[1] for x in tape if x[2]])
    both, bust, med = challenge_mc(daylist(sorted((e, rr) for (e, rr, _) in tape)))
    print(f"  {label}: n={len(r):5d} exp={r.mean():+.4f} win={(r > 0).mean():.1%} "
          f"| OOS n={len(ro)} exp={(ro.mean() if len(ro) else float('nan')):+.4f} "
          f"| MC both={both:.1%} bust={bust:.1%}", flush=True)


def main():
    trio = [Sym(k, sub) for k, sub in TRIO]
    hold = [Sym(k, sub) for k, sub in HOLDOUT]
    # sanity line
    s0 = trio[0]
    print(f"sanity {s0.name}: RSI14 med={np.nanmedian(s0.rsi14):.1f} "
          f"ADX med={np.nanmedian(s0.adx14):.1f} StochK med={np.nanmedian(s0.stk):.1f}")
    for fam in ("F1", "F2", "F3", "F4"):
        print(f"\n=== {fam} ===")
        t = []
        for s in trio:
            t += run_family(s, fam)
        report(t, "TRIO")
        hh = []
        for s in hold:
            hh += run_family(s, fam)
        report(hh, "HOLDOUT-10")


if __name__ == "__main__":
    main()
