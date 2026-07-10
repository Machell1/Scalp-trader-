"""S0 — order-flow proxy features per M15 bar (VPOF_SPEC_2026-07-10).

The only 'order flow' retail MT5 CFD feeds expose: candle-signed tick volume.
Feature semantics ported from OrderFlowLite v1.11 (Deriv terminal indicator):
signed delta, CVD slope, buyer pressure share, plus delta acceleration.
All causal: features at bar t use bars <= t.
"""
import numpy as np
import pandas as pd

SHARE_LOOKBACK = 20   # OrderFlowLite InpReadLookback
CVD_SLOPE_BARS = 50   # OrderFlowLite InpCvdSlopeBars


def of_features(df):
    o = df["open"].to_numpy(float)
    c = df["close"].to_numpy(float)
    v = df["volume"].to_numpy(float) if "volume" in df else np.ones(len(df))
    sign = np.sign(c - o)
    delta = sign * v                                   # candle-signed tick volume
    absd = np.abs(delta)
    cvd = np.cumsum(delta)

    s = pd.Series(delta)
    sa = pd.Series(absd)
    pos = s.clip(lower=0.0)

    share = (pos.rolling(SHARE_LOOKBACK).sum()
             / sa.rolling(SHARE_LOOKBACK).sum().replace(0, np.nan)) * 100.0
    cvd_s = pd.Series(cvd)
    cvd_slope = (cvd_s - cvd_s.shift(CVD_SLOPE_BARS))
    cvd_slope = cvd_slope / (sa.rolling(CVD_SLOPE_BARS).mean().replace(0, np.nan) * CVD_SLOPE_BARS)
    dstd = s.rolling(SHARE_LOOKBACK).std().replace(0, np.nan)
    delta_z = s / dstd                                  # normalized bar delta
    accel = (s - s.shift(1)) / dstd                     # delta acceleration

    return pd.DataFrame({
        "of_share": share.to_numpy(),          # 0..100, 50 = balanced
        "of_cvd_slope": cvd_slope.to_numpy(),  # ~[-1, 1]
        "of_delta_z": delta_z.to_numpy(),
        "of_accel": accel.to_numpy(),
    })


def shuffle_within_day(feat_df, times):
    """S1.5 control (c): permute feature ROWS within each calendar day —
    marginal distributions preserved, intraday timing destroyed."""
    day = pd.to_datetime(pd.Series(times), unit="s").dt.floor("D").to_numpy()
    out = feat_df.copy()
    rng = np.random.default_rng(20260710)
    idx = np.arange(len(feat_df))
    for d in np.unique(day):
        m = np.where(day == d)[0]
        perm = rng.permutation(m)
        out.iloc[m] = feat_df.iloc[perm].to_numpy()
    return out
