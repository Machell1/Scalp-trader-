"""S1 — level-violation events + walk-forward calibrated probability model
(VPOF_SPEC_2026-07-10, pre-registered grid: k in {0.15,0.30} ATR, h in {4,8}).

Event: price TOUCHES a level (close within 0.15 ATR), label Y=1 if within h
bars a bar CLOSES beyond the level by >= k*ATR on the far side (relative to
the approach side). Features at the touch bar only (instant, causal).

Model: ridge logistic (numpy IRLS) + isotonic (PAV) calibration, walk-forward
monthly folds after a 40% burn-in. Metrics: rank AUC + Brier, out-of-fold.
"""
import numpy as np
import pandas as pd

TOUCH_TOL_ATR = 0.15
COOLDOWN = 8   # bars between events on the same level


# ------------------------- events -------------------------

def build_touches(df, atr, vp_dict, window=192, step=4):
    """Vectorized touch scan: for each recompute block (levels constant inside),
    find (bar, level) pairs with |close - level| <= tol*ATR, cooldown-deduped.
    Returns a DataFrame WITHOUT labels (labels are k/h-specific, added later)."""
    c = df["close"].to_numpy(float)
    t_arr = df["time"].to_numpy()
    n = len(c)
    rows = []
    last_touch = {}
    keys = sorted(vp_dict.keys())
    for ki, t0 in enumerate(keys):
        levels = vp_dict[t0]
        if not levels:
            continue
        t1 = min(keys[ki + 1] if ki + 1 < len(keys) else t0 + step, n)
        if t0 >= n:
            break
        lp = np.array([x[0] for x in levels])
        st = np.array([x[1] for x in levels])
        tg = [x[2] for x in levels]
        cs = c[t0:t1]
        aa = atr[t0:t1]
        ok = np.isfinite(aa) & (aa > 0)
        d = cs[:, None] - lp[None, :]                       # (B, L)
        hit = ok[:, None] & (np.abs(d) <= TOUCH_TOL_ATR * aa[:, None])
        bi, li = np.where(hit)
        for b, j in zip(bi, li):
            t = t0 + b
            if t < window + 4 or t >= n:
                continue
            key = round(lp[j], 6)
            if t - last_touch.get(key, -10 ** 9) < COOLDOWN:
                continue
            last_touch[key] = t
            approach = np.sign(c[t - 3:t].mean() - lp[j])
            if approach == 0:
                approach = np.sign(d[b, j]) if d[b, j] != 0 else 1.0
            rows.append((t_arr[t], t, lp[j], tg[j], st[j],
                         d[b, j] / atr[t], approach))
    return pd.DataFrame(rows, columns=["time", "bar", "level", "tag",
                                       "strength", "dist_atr", "approach"])


def label_and_featurize(touches, df, atr, feat, k_atr, h_bars):
    """Add the (k,h)-specific violation label + touch-bar OF features."""
    c = df["close"].to_numpy(float)
    n = len(c)
    ev = touches[touches["bar"] < n - h_bars - 1].copy()
    bars = ev["bar"].to_numpy(int)
    lp = ev["level"].to_numpy(float)
    ap = ev["approach"].to_numpy(float)
    a = atr[bars]
    # violation: any CLOSE beyond level by k*ATR on the far side within h bars
    y = np.zeros(len(ev), int)
    for h in range(1, h_bars + 1):
        far = (c[bars + h] - lp) * (-ap)
        y |= (far >= k_atr * a).astype(int)
    ev["y"] = y
    f = feat.iloc[bars].reset_index(drop=True)
    ev = ev.reset_index(drop=True)
    ev["of_share"] = f["of_share"]
    ev["of_cvd_slope"] = f["of_cvd_slope"]
    ev["of_delta_z"] = f["of_delta_z"]
    ev["of_accel"] = f["of_accel"]
    ev["flow_thru"] = -ev["approach"] * ev["of_delta_z"]
    ev["cvd_thru"] = -ev["approach"] * ev["of_cvd_slope"]
    return ev


# ------------------------- model -------------------------

FEATS_FULL = ["strength", "dist_atr", "flow_thru", "cvd_thru", "of_share", "of_accel"]
FEATS_STRENGTH = ["strength", "dist_atr"]           # shield-arm gate: levels only
FEATS_OF = ["flow_thru", "cvd_thru", "of_share", "of_accel"]   # cut-arm increment


def _logistic_irls(X, y, ridge=1.0, iters=60):
    Xb = np.hstack([np.ones((len(X), 1)), X])
    w = np.zeros(Xb.shape[1])
    for _ in range(iters):
        z = Xb @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        Wd = np.maximum(p * (1 - p), 1e-6)
        H = (Xb * Wd[:, None]).T @ Xb + ridge * np.eye(Xb.shape[1])
        g = Xb.T @ (y - p) - ridge * w
        try:
            dw = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        w += dw
        if np.max(np.abs(dw)) < 1e-8:
            break
    return w


def _predict(w, X):
    Xb = np.hstack([np.ones((len(X), 1)), X])
    return 1.0 / (1.0 + np.exp(-np.clip(Xb @ w, -30, 30)))


def _pav_isotonic(p_train, y_train):
    """Pool-adjacent-violators; returns (breakpoints, values) step function."""
    order = np.argsort(p_train)
    ps, ys = p_train[order], y_train[order].astype(float)
    vals = ys.copy(); wts = np.ones_like(ys)
    i = 0
    v = list(vals); w = list(wts); px = list(ps)
    stack_v, stack_w, stack_p = [], [], []
    for vi, wi, pi in zip(v, w, px):
        stack_v.append(vi); stack_w.append(wi); stack_p.append(pi)
        while len(stack_v) > 1 and stack_v[-2] > stack_v[-1]:
            v2, w2 = stack_v.pop(), stack_w.pop(); stack_p.pop()
            v1, w1 = stack_v.pop(), stack_w.pop(); p1 = stack_p.pop()
            stack_v.append((v1 * w1 + v2 * w2) / (w1 + w2))
            stack_w.append(w1 + w2); stack_p.append(p1)
    return np.array(stack_p), np.array(stack_v)


def _iso_apply(bp, bv, p):
    idx = np.searchsorted(bp, p, side="right") - 1
    idx = np.clip(idx, 0, len(bv) - 1)
    return bv[idx]


def _standardize(train, test):
    mu, sd = np.nanmean(train, axis=0), np.nanstd(train, axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    return (train - mu) / sd, (test - mu) / sd


def auc_rank(y, p):
    order = np.argsort(p)
    ranks = np.empty(len(p)); ranks[order] = np.arange(1, len(p) + 1)
    n1 = int(y.sum()); n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def walkforward_eval(ev, feats, burn_frac=0.4, label=""):
    """Monthly walk-forward: returns dict with oof AUC, Brier, calibrated preds."""
    ev = ev.sort_values("time").reset_index(drop=True)
    ev = ev.dropna(subset=feats + ["y"]).reset_index(drop=True)
    if len(ev) < 400:
        return dict(label=label, n=len(ev), auc=np.nan, brier=np.nan, preds=None)
    month = pd.to_datetime(ev["time"], unit="s").dt.to_period("M")
    months = month.unique()
    burn = months[max(1, int(len(months) * burn_frac)) - 1]
    y_all, p_all, idx_all = [], [], []
    X = ev[feats].to_numpy(float)
    y = ev["y"].to_numpy(int)
    for m in months:
        if m <= burn:
            continue
        tr = (month < m).to_numpy()
        te = (month == m).to_numpy()
        if tr.sum() < 300 or te.sum() < 10 or y[tr].sum() < 20:
            continue
        Xtr, Xte = _standardize(X[tr], X[te])
        Xtr = np.nan_to_num(Xtr); Xte = np.nan_to_num(Xte)
        w = _logistic_irls(Xtr, y[tr])
        p_tr = _predict(w, Xtr); p_te = _predict(w, Xte)
        bp, bv = _pav_isotonic(p_tr, y[tr])
        p_cal = _iso_apply(bp, bv, p_te)
        y_all.append(y[te]); p_all.append(p_cal); idx_all.append(np.where(te)[0])
    if not y_all:
        return dict(label=label, n=len(ev), auc=np.nan, brier=np.nan, preds=None)
    yy = np.concatenate(y_all); pp = np.concatenate(p_all)
    preds = pd.Series(np.nan, index=ev.index)
    preds.iloc[np.concatenate(idx_all)] = pp
    return dict(label=label, n=int(len(yy)), base=float(yy.mean()),
                auc=float(auc_rank(yy, pp)), brier=float(np.mean((pp - yy) ** 2)),
                preds=preds, events=ev)
