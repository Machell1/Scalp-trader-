"""Confluence-extended scalper simulator.

Wraps the FAITHFUL core (scalper_backtest.simulate_symbol logic) and adds, as
optional and independently-toggleable confluences, exactly the candidates in the
approved plan. Everything is precomputed vectorised and CAUSAL (each indicator at
bar i uses only data <= i; HTF via merge_asof-backward availability-time).

With every confluence OFF, simulate_symbol_c reproduces the baseline harness
output bar-for-bar (verified in experiment.py).

Per-trade records are returned (not just R) so the runner can do the
marginal-contribution / permutation analysis and the entry-geometry non-fill audit.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
import numpy as np
import pandas as pd

from scalper_backtest import wilder_atr, anchored_vwap, session_bar_pos, ema, compute_stats, Stats

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Extended parameters (superset of Params; baseline defaults == original)
# ---------------------------------------------------------------------------
@dataclass
class CParams:
    # --- base (identical defaults to scalper_backtest.Params) ---
    momentum_bars: int = 6
    momentum_atr: float = 2.0
    atr_period: int = 14
    direction: str = "cont"
    entry_style: str = "stop"        # 'stop' | 'market' | 'limit'
    entry_offset_atr: float = 0.05
    pending_expiry_bars: int = 2
    stop_atr: float = 1.0
    tp_atr: float = 1.5
    lock_trigger_atr: float = 0.25
    trail_atr: float = 0.5
    max_hold_bars: int = 8
    cost_atr_frac: float = 0.0
    trend_ema: int = 0
    long_only: bool = False
    short_only: bool = False
    vwap_window: int = 0
    vwap_min_bars: int = 8
    # --- #2 entry geometry: stop mode ---
    stop_mode: str = "atr"           # 'atr' | 'struct' (max of atr-band and impulse-extreme distance)
    # --- #3 ADX/+-DI regime gate ---
    adx_min: float = 0.0             # >0 enables; require ADX>=min
    adx_period: int = 14
    require_di_agree: bool = True    # +DI>-DI for longs (mirror for shorts)
    # --- #4 causal HTF EMA trend alignment ---
    htf_minutes: int = 0             # 0 off; 60=H1, 240=H4 (base TF assumed 15m)
    htf_ema: int = 50
    # --- #5 momentum quality ---
    er_min: float = 0.0              # Kaufman efficiency ratio over the momentum window
    body_frac_min: float = 0.0       # |close-open|/(high-low) of the trigger bar
    persist_min: int = 0             # # of same-direction candles within the window
    # --- #6 volatility-regime percentile band ---
    rv_pct_lo: float = 0.0
    rv_pct_hi: float = 1.0
    rv_win: int = 24
    rv_rank_win: int = 2000
    # --- #7 session/time-of-day gate (ET) ---
    sess_start_hm: int = -1          # e.g. 930; -1 = off
    sess_end_hm: int = -1            # e.g. 1600
    sess_tz: str = "America/New_York"  # "" = use the data's native (server) clock
    # --- #9 tick-volume confirmation (NEGATIVE CONTROL) ---
    vol_gate_k: float = 0.0          # >0 => require vol[i] >= k * SMA(vol,vol_sma)[i]
    vol_sma: int = 20
    # --- pending invalidation (cancel a resting LIMIT when the setup is violated) ---
    cancel_beyond_atr: float = 0.0   # >0: cancel the pending if price runs this many ATR BEYOND
                                     # the signal close (away from the limit) before filling.
                                     # Fill-first within a bar (a broker race resolves to the fill).
    # --- profit-conditional time-exit extension ---
    hold_ext_bars: int = 0           # >max_hold_bars: at the base time-exit bar, EXTEND the hold
    hold_ext_min_r: float = 0.0      # to this many bars if unrealized r >= this (close-based);
                                     # losers/flat trades still exit at max_hold_bars.
    # --- partial scale-out (bank a fraction at a fixed R; runner continues to TP) ---
    scaleout_r: float = 0.0          # >0 enables: close scaleout_frac of the position when price
                                     # touches entry + scaleout_r*risk (intrabar, like a limit TP;
                                     # pessimistic: the SL check on the same bar comes first).
    scaleout_frac: float = 0.5       # fraction banked at the scale-out level
    scaleout_be: bool = False        # move the runner's stop to entry when the scale-out fills
                                     # (close-based convention: effective from the NEXT bar,
                                     # same as the lock/trail engine).
    # --- single pyramiding add (additive scale-in) ---
    pyr_add_r: float = 0.0           # >0 enables: when CLOSE-based unrealized r >= this, add
                                     # pyr_add_frac units at the NEXT bar's open and move the
                                     # whole position's stop to entry (BE). One add per trade.
    pyr_add_frac: float = 1.0        # add size as a fraction of the initial unit
    # --- vol-regime-adaptive TP ---
    tp_rv_split: float = 0.0         # >0 enables: TP multiple = tp_atr_lo_rv if the signal bar's
                                     # rv percentile < split else tp_atr_hi_rv; falls back to
                                     # tp_atr while the percentile is not yet defined (warm-up).
    tp_atr_lo_rv: float = 3.0
    tp_atr_hi_rv: float = 3.0
    # --- TP ratchet (2026-07-03 user idea: "when the TP is about to get hit, move it
    #     further out and trail the SL to where the TP was") ---
    rat_gap_r: float = 0.0           # >0 enables: at bar CLOSE, when unrealized r is within
                                     # this many R of the CURRENT TP, extend the TP by rat_ext_r
                                     # and raise the SL to (old TP - rat_buf_r). Repeats at each
                                     # new rung (the trigger is relative to the current TP).
                                     # Close-based; updates effective from the NEXT bar, same
                                     # convention as the lock/trail engine. A touch of the old
                                     # TP on the trigger bar itself still exits at the old TP
                                     # (exit checks run first - pessimistic).
    rat_ext_r: float = 1.0           # TP extension per ratchet, in R (risk units)
    rat_buf_r: float = 0.5           # SL floor sits this many R below the OLD TP. Legality
                                     # clamp (broker: SL must stay below price for a long):
                                     # floor <= close - 0.05R, mirroring MT5 stops-distance.
    # --- engine ---
    block_overlap: bool = True       # True = faithful one-trade-at-a-time; False = signal-level (for marginal analysis)


# ---------------------------------------------------------------------------
# Vectorised, causal indicator precompute
# ---------------------------------------------------------------------------
def _wilder_smooth(x, p):
    out = np.full(len(x), np.nan)
    if len(x) < p:
        return out
    out[p - 1] = x[:p].sum()
    for i in range(p, len(x)):
        out[i] = out[i - 1] - out[i - 1] / p + x[i]
    return out


def adx_arrays(h, l, c, p=14):
    """Full-series Wilder ADX, +DI, -DI (each aligned to bar index; causal)."""
    n = len(c)
    tr = np.zeros(n); pdm = np.zeros(n); mdm = np.zeros(n)
    up = h[1:] - h[:-1]
    dn = l[:-1] - l[1:]
    pdm[1:] = np.where((up > dn) & (up > 0), up, 0.0)
    mdm[1:] = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    str_ = _wilder_smooth(tr, p)
    sp = _wilder_smooth(pdm, p)
    sm = _wilder_smooth(mdm, p)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100.0 * sp / str_
        mdi = 100.0 * sm / str_
        dx = 100.0 * np.abs(pdi - mdi) / (pdi + mdi)
    adx = np.full(n, np.nan)
    # first ADX = mean of first p DX values (starting where dx is defined)
    first = p - 1  # index where smoothing first defined
    dxv = dx.copy()
    valid = np.where(np.isfinite(dxv))[0]
    if len(valid) >= p:
        s0 = valid[0]
        seed_end = s0 + p
        if seed_end <= n:
            adx[seed_end - 1] = np.nanmean(dxv[s0:seed_end])
            for i in range(seed_end, n):
                if np.isfinite(dxv[i]):
                    adx[i] = (adx[i - 1] * (p - 1) + dxv[i]) / p
                else:
                    adx[i] = adx[i - 1]
    return adx, pdi, mdi


def htf_ema_aligned(df, minutes, ema_period):
    """EMA on the HTF (resampled) close + its previous HTF value, causally aligned
    back onto the base-bar clock (merge_asof backward on availability=HTF close time)."""
    t = pd.to_datetime(df["time"])
    s = pd.DataFrame({"close": df["close"].astype(float).values}, index=t)
    rule = f"{minutes}min"
    htf = s["close"].resample(rule, label="left", closed="left").last().dropna()
    e = htf.ewm(span=ema_period, adjust=False).mean()
    src = pd.DataFrame({"htf_ema": e.values, "htf_ema_prev": e.shift(1).values}, index=htf.index)
    # availability = next HTF bar open (== this bar's close); last one + median delta
    idx = src.index
    delta = idx.to_series().diff().median()
    avail = idx.to_series().shift(-1)
    avail.iloc[-1] = idx[-1] + delta
    tmp = src.copy()
    tmp["avail"] = avail.values
    tmp = tmp.dropna(subset=["avail"]).sort_values("avail")
    left = pd.DataFrame({"time": t.values}).sort_values("time")
    merged = pd.merge_asof(left, tmp, left_on="time", right_on="avail", direction="backward")
    merged = merged.set_index("time").reindex(t.values)
    return merged["htf_ema"].to_numpy(float), merged["htf_ema_prev"].to_numpy(float)


def precompute(df, p: CParams):
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float); o = df["open"].to_numpy(float)
    n = len(c)
    out = {}
    out["atr"] = wilder_atr(h, l, c, p.atr_period)
    out["trend"] = ema(c, p.trend_ema) if p.trend_ema > 0 else None
    out["vwap"] = anchored_vwap(df) if p.vwap_window > 0 else None
    out["sess_pos"] = session_bar_pos(df) if p.vwap_window > 0 else None
    # ADX
    if p.adx_min > 0:
        out["adx"], out["pdi"], out["mdi"] = adx_arrays(h, l, c, p.adx_period)
    # HTF
    if p.htf_minutes > 0:
        out["htf_ema"], out["htf_ema_prev"] = htf_ema_aligned(df, p.htf_minutes, p.htf_ema)
    # momentum quality
    mb = p.momentum_bars
    if p.er_min > 0:
        net = np.abs(c - np.concatenate([np.full(mb - 1, np.nan), c[:-(mb - 1)]]))
        absdiff = np.abs(np.diff(c, prepend=c[0]))
        path = pd.Series(absdiff).rolling(mb - 1).sum().to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            out["er"] = net / path
    if p.body_frac_min > 0:
        rng = (h - l)
        out["body_frac"] = np.where(rng > 0, np.abs(c - o) / rng, 0.0)
    # volatility-regime percentile (rolling rank of rolling std of returns)
    if p.rv_pct_lo > 0.0 or p.rv_pct_hi < 1.0 or p.tp_rv_split > 0.0:
        ret = pd.Series(c).pct_change()
        rv = ret.rolling(p.rv_win).std()
        out["rv_pct"] = rv.rolling(p.rv_rank_win, min_periods=200).rank(pct=True).to_numpy()
    # session hm (ET by default; sess_tz="" keeps the data's native/server clock)
    if p.sess_start_hm >= 0:
        if p.sess_tz:
            t = pd.to_datetime(df["time"], utc=True).dt.tz_convert(p.sess_tz)
        else:
            t = pd.to_datetime(df["time"])
        out["hm"] = (t.dt.hour * 100 + t.dt.minute).to_numpy()
    # tick volume gate
    if p.vol_gate_k > 0 and "volume" in df:
        v = df["volume"].astype(float)
        out["vol"] = v.to_numpy()
        out["vol_sma"] = v.rolling(p.vol_sma).mean().to_numpy()
    return out


# ---------------------------------------------------------------------------
# Simulation (faithful core + confluence gates)
# ---------------------------------------------------------------------------
def simulate_symbol_c(df, p: CParams, lo, hi, ind=None):
    """Return list of per-trade dicts and a counters dict.
    Trade dict: {i, side, r, fill_lag, reason}. Counters: signals, passed_filters, nonfill."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    if ind is None:
        ind = precompute(df, p)
    atr = ind["atr"]; trend = ind["trend"]; vwap = ind["vwap"]; sess_pos = ind["sess_pos"]
    n = len(c); mb = p.momentum_bars
    trades = []
    cnt = dict(signals=0, passed=0, nonfill=0)
    rv_band_on = (p.rv_pct_lo > 0.0 or p.rv_pct_hi < 1.0)   # tp_rv_split alone must NOT gate entries
    start = max(lo, mb + p.atr_period + 1, p.rv_win + 2 if rv_band_on else 0)
    end = min(hi, n - 1)

    i = start
    while i < end:
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            i += 1; continue
        move = c[i - (mb - 1)] - c[i]
        move_atr = move / a
        bear = c[i] < o[i]; bull = c[i] > o[i]
        falling = (move_atr >= p.momentum_atr) and bear
        rising = (-move_atr >= p.momentum_atr) and bull
        if not (falling or rising):
            i += 1; continue
        cnt["signals"] += 1

        if p.direction == "cont":
            go_long, go_short = rising, falling
        else:
            go_long, go_short = falling, rising
        if p.long_only: go_short = False
        if p.short_only: go_long = False

        # --- AVWAP gate ---
        if vwap is not None:
            if sess_pos[i] < p.vwap_min_bars:
                i += 1; continue
            v = vwap[i]
            if np.isfinite(v):
                if go_long and c[i] > v: go_long = False
                if go_short and c[i] < v: go_short = False
        if not (go_long or go_short):
            i += 1; continue

        # --- trend EMA slope ---
        if trend is not None and np.isfinite(trend[i]) and np.isfinite(trend[i - mb]):
            up = trend[i] > trend[i - mb]
            if go_long and not up: i += 1; continue
            if go_short and up: i += 1; continue

        # --- #3 ADX/+-DI regime ---
        if p.adx_min > 0:
            av = ind["adx"][i]
            if not np.isfinite(av) or av < p.adx_min:
                i += 1; continue
            if p.require_di_agree:
                pdi, mdi = ind["pdi"][i], ind["mdi"][i]
                if go_long and not (pdi > mdi): i += 1; continue
                if go_short and not (mdi > pdi): i += 1; continue

        # --- #4 HTF EMA trend alignment ---
        if p.htf_minutes > 0:
            he, hep = ind["htf_ema"][i], ind["htf_ema_prev"][i]
            if not (np.isfinite(he) and np.isfinite(hep)):
                i += 1; continue
            htf_up = (c[i] > he) and (he > hep)
            htf_dn = (c[i] < he) and (he < hep)
            if go_long and not htf_up: i += 1; continue
            if go_short and not htf_dn: i += 1; continue

        # --- #5 momentum quality ---
        if p.er_min > 0:
            erv = ind["er"][i]
            if not np.isfinite(erv) or erv < p.er_min: i += 1; continue
        if p.body_frac_min > 0:
            if ind["body_frac"][i] < p.body_frac_min: i += 1; continue
        if p.persist_min > 0:
            wdir = (c[i - (mb - 1): i + 1] > o[i - (mb - 1): i + 1]) if (go_long) else (c[i - (mb - 1): i + 1] < o[i - (mb - 1): i + 1])
            if wdir.sum() < p.persist_min: i += 1; continue

        # --- #6 vol-regime band ---
        if rv_band_on and "rv_pct" in ind:
            rp = ind["rv_pct"][i]
            if not np.isfinite(rp) or rp < p.rv_pct_lo or rp > p.rv_pct_hi: i += 1; continue

        # --- #7 session window (ET) ---
        if p.sess_start_hm >= 0:
            hm = ind["hm"][i]
            if p.sess_start_hm <= p.sess_end_hm:
                if not (p.sess_start_hm <= hm < p.sess_end_hm): i += 1; continue
            else:
                if not (hm >= p.sess_start_hm or hm < p.sess_end_hm): i += 1; continue

        # --- #9 tick-volume gate (negative control) ---
        if p.vol_gate_k > 0 and "vol" in ind:
            vs = ind["vol_sma"][i]
            if not np.isfinite(vs) or vs <= 0 or ind["vol"][i] < p.vol_gate_k * vs:
                i += 1; continue

        cnt["passed"] += 1
        side = 1 if go_long else -1
        offset = p.entry_offset_atr * a
        ref = c[i]

        # --- entry per style ---
        if p.entry_style == "market":
            entry = o[i + 1] if i + 1 < n else c[i]
            entry_bar = i + 1
            if entry_bar >= n:
                i += 1; continue
        else:
            entry = (ref + offset if side > 0 else ref - offset) if p.entry_style == "stop" \
                else (ref - offset if side > 0 else ref + offset)
            viol = None
            if p.cancel_beyond_atr > 0 and p.entry_style == "limit":
                viol = ref + p.cancel_beyond_atr * a if side > 0 else ref - p.cancel_beyond_atr * a
            filled = False; entry_bar = -1
            for j in range(i + 1, min(i + 1 + p.pending_expiry_bars, n)):
                if p.entry_style == "stop":
                    hit = (h[j] >= entry) if side > 0 else (l[j] <= entry)
                else:
                    hit = (l[j] <= entry) if side > 0 else (h[j] >= entry)
                if hit:
                    filled = True; entry_bar = j; break
                # setup-invalidation cancel: checked only after the fill test on the same bar
                # (fill-first = how a live broker race resolves; conservative for the rule)
                if viol is not None:
                    if (side > 0 and h[j] >= viol) or (side < 0 and l[j] <= viol):
                        break
            if not filled:
                cnt["nonfill"] += 1
                i += 1; continue

        # --- #2 stop geometry ---
        if p.stop_mode == "struct":
            w_lo = l[i - (mb - 1): i + 1].min()
            w_hi = h[i - (mb - 1): i + 1].max()
            struct_dist = (entry - w_lo) if side > 0 else (w_hi - entry)
            risk = max(p.stop_atr * a, struct_dist)
        else:
            risk = p.stop_atr * a
        if risk <= 0:
            i += 1; continue

        # Vol-regime-adaptive TP: pick the TP multiple from the SIGNAL bar's realized-vol
        # percentile (causal, precomputed). With tp_rv_split=0 this is exactly p.tp_atr.
        # NOTE: tp_rv_split alone never gates entries — the signal set stays identical
        # to the baseline so the paired per-signal test is sharp.
        tp_mult = p.tp_atr
        if p.tp_rv_split > 0 and "rv_pct" in ind:
            rp_tp = ind["rv_pct"][i]
            if np.isfinite(rp_tp):
                tp_mult = p.tp_atr_lo_rv if rp_tp < p.tp_rv_split else p.tp_atr_hi_rv

        if side > 0:
            sl = entry - risk
            tp = entry + tp_mult * a if tp_mult > 0 else None
        else:
            sl = entry + risk
            tp = entry - tp_mult * a if tp_mult > 0 else None

        lock_trigger = p.lock_trigger_atr * a
        trail_dist = p.trail_atr * a
        cost = p.cost_atr_frac * a

        # Partial scale-out state (level in R = multiples of the initial risk).
        so_price = None
        if p.scaleout_r > 0:
            so_price = entry + p.scaleout_r * risk if side > 0 else entry - p.scaleout_r * risk
        so_filled = False
        so_exit = None
        # Single pyramiding add state: trigger evaluated on bar CLOSE, add executes at the
        # NEXT bar's open (causal); stop-to-BE is applied with the trigger (end-of-bar SL
        # update, same convention as the lock/trail engine). One add per trade.
        pyr_armed = False
        add_price = None

        # Profit-conditional hold extension: at the base time-exit bar, a trade whose
        # CLOSE-based unrealized r >= hold_ext_min_r keeps running until hold_ext_bars;
        # losers/flat trades still time-exit at max_hold_bars (0 = feature off).
        hold = p.max_hold_bars
        base_exit_k = entry_bar + p.max_hold_bars - 1
        exit_price = None; exit_bar = entry_bar
        k = entry_bar
        while k < min(entry_bar + hold, n):      # while-loop: `hold` may grow mid-trade
            # armed pyramid add fills at this bar's OPEN (before the SL/TP scan; the SL
            # already sits at BE from the trigger bar's close, so a same-bar reversal
            # stops the WHOLE position including the fresh add — no free option).
            # Gap races: no add if the bar already opens through the stop (position is
            # dead at the open) or through the TP (position closes at the open) — a live
            # market-order add loses both races.
            if pyr_armed and add_price is None:
                gap_sl = (o[k] <= sl) if side > 0 else (o[k] >= sl)
                gap_tp = tp is not None and ((o[k] >= tp) if side > 0 else (o[k] <= tp))
                if not (gap_sl or gap_tp):
                    add_price = o[k]
            if side > 0:
                if l[k] <= sl: exit_price, exit_bar = sl, k; break
                if so_price is not None and not so_filled and h[k] >= so_price:
                    so_filled = True; so_exit = so_price     # partial banks; runner continues
                if tp is not None and h[k] >= tp: exit_price, exit_bar = tp, k; break
            else:
                if h[k] >= sl: exit_price, exit_bar = sl, k; break
                if so_price is not None and not so_filled and l[k] <= so_price:
                    so_filled = True; so_exit = so_price
                if tp is not None and l[k] <= tp: exit_price, exit_bar = tp, k; break
            price = c[k]
            if side > 0:
                if (price - entry) >= lock_trigger:
                    sl = max(sl, entry); sl = max(sl, price - trail_dist)
            else:
                if (entry - price) >= lock_trigger:
                    sl = min(sl, entry); sl = min(sl, price + trail_dist)
            # scale-out BE: runner's stop to entry, effective from the next bar
            if so_filled and p.scaleout_be:
                sl = max(sl, entry) if side > 0 else min(sl, entry)
            # pyramid trigger on bar close: arm the add + move the stop to BE
            if p.pyr_add_r > 0 and not pyr_armed:
                unreal_pyr = ((price - entry) if side > 0 else (entry - price)) / risk
                if unreal_pyr >= p.pyr_add_r:
                    pyr_armed = True
                    sl = max(sl, entry) if side > 0 else min(sl, entry)
            if (p.hold_ext_bars > p.max_hold_bars and hold == p.max_hold_bars
                    and k == base_exit_k):
                unreal = ((price - entry) if side > 0 else (entry - price)) / risk
                if unreal >= p.hold_ext_min_r:
                    hold = p.hold_ext_bars       # winner earns more time
            # TP ratchet on bar close: within rat_gap_r of the CURRENT TP -> extend the TP
            # by rat_ext_r and raise the SL toward the old TP (old TP - rat_buf_r, clamped
            # to 0.05R below this close so the stop stays broker-legal). The intrabar exit
            # checks above ran FIRST, so a same-bar touch of the old TP exits at the old TP
            # (pessimistic); the ratchet earns from the NEXT bar. SL only ever moves up.
            if p.rat_gap_r > 0 and tp is not None:
                unreal_rat = ((price - entry) if side > 0 else (entry - price)) / risk
                cur_tp_r = ((tp - entry) if side > 0 else (entry - tp)) / risk
                if unreal_rat >= cur_tp_r - p.rat_gap_r:
                    floor_r = min(cur_tp_r - p.rat_buf_r, unreal_rat - 0.05)
                    if side > 0:
                        sl = max(sl, entry + floor_r * risk)
                        tp = entry + (cur_tp_r + p.rat_ext_r) * risk
                    else:
                        sl = min(sl, entry - floor_r * risk)
                        tp = entry - (cur_tp_r + p.rat_ext_r) * risk
            k += 1

        if exit_price is None:
            exit_bar = min(entry_bar + hold - 1, n - 1)
            exit_price = c[exit_bar]

        gross = (exit_price - entry) * side
        if so_filled or add_price is not None:
            # Per-signal R in units of the INITIAL 1-unit risk (paired-comparable with
            # the baseline). Total notional in/out matches, so cost = 2*cost per unit.
            if so_filled:
                num = (p.scaleout_frac * (so_exit - entry) * side
                       + (1.0 - p.scaleout_frac) * gross - 2 * cost)
            else:
                num = gross - 2 * cost
            if add_price is not None:
                num += p.pyr_add_frac * ((exit_price - add_price) * side - 2 * cost)
            r = num / risk
        else:
            r = (gross - 2 * cost) / risk
        trades.append(dict(i=i, side=side, r=r, fill_lag=entry_bar - i, exit_i=exit_bar))

        i = max(exit_bar + 1, i + 1) if p.block_overlap else (i + 1)

    return trades, cnt


def rs_of(trades):
    return [t["r"] for t in trades]
