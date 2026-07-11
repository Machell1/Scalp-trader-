"""S0 — rolling Volume Profile engine (VPOF_SPEC_2026-07-10, pre-registered).

Causal: levels reported at bar t are computed ONLY from bars [t-window, t).
Data reality: M15 bars with tick volume, each bar's volume spread uniformly
across its [low, high] range (M1 fidelity spot-check is a separate step;
FTMO M1 depth is ~7 weeks, too thin to train on).

Levels per recompute: POC (max-mass bin), HVNs (local maxima), value-area
edges (70% mass around POC). Strength in [0,1] = relative bin mass, with the
POC anchored at 1.0.
"""
import numpy as np

N_BINS = 200


N_SAMPLES = 16   # points per bar approximating uniform volume spread


def _histogram(lo_arr, hi_arr, vol_arr, grid_lo, grid_hi):
    """Mass per bin: each bar's volume spread across its range, approximated by
    N_SAMPLES equally spaced points per bar (single C-level histogram call)."""
    if grid_hi <= grid_lo:
        return np.zeros(N_BINS)
    frac = (np.arange(N_SAMPLES) + 0.5) / N_SAMPLES            # (S,)
    pts = lo_arr[:, None] + (hi_arr - lo_arr)[:, None] * frac  # (W, S)
    wts = np.repeat(vol_arr / N_SAMPLES, N_SAMPLES)
    mass, _ = np.histogram(pts.ravel(), bins=N_BINS,
                           range=(grid_lo, grid_hi), weights=wts)
    return mass


def _extract_levels(mass, grid_lo, width, top_k):
    """POC + HVN local maxima + value-area edges, with strength scores."""
    total = mass.sum()
    if total <= 0:
        return []
    poc = int(np.argmax(mass))
    # value area: expand around POC to 70% of mass
    lo_b = hi_b = poc
    acc = mass[poc]
    while acc < 0.70 * total and (lo_b > 0 or hi_b < len(mass) - 1):
        left = mass[lo_b - 1] if lo_b > 0 else -1.0
        right = mass[hi_b + 1] if hi_b < len(mass) - 1 else -1.0
        if left >= right:
            lo_b -= 1; acc += max(left, 0.0)
        else:
            hi_b += 1; acc += max(right, 0.0)
    med = np.median(mass[mass > 0])
    peak = mass[poc]
    levels = []

    def price_of(b):
        return grid_lo + (b + 0.5) * width

    levels.append((price_of(poc), 1.0, 'POC'))
    # HVN local maxima: above 1.2x median mass, >= 5 bins from an accepted level
    order = np.argsort(mass)[::-1]
    for b in order[:40]:
        if mass[b] < 1.2 * med or b == poc:
            continue
        if 0 < b < len(mass) - 1 and not (mass[b] >= mass[b - 1] and mass[b] >= mass[b + 1]):
            continue
        p = price_of(b)
        if any(abs(b - int((lp - grid_lo) / width - 0.5)) < 5 for lp, _, _ in levels):
            continue
        levels.append((p, float(mass[b] / peak), 'HVN'))
        if len(levels) >= top_k:
            break
    # value-area edges (structural shelf boundaries)
    for b, tag in ((lo_b, 'VAL'), (hi_b, 'VAH')):
        p = price_of(b)
        if not any(abs(p - lp) < 2 * width for lp, _, _ in levels):
            levels.append((p, float(max(mass[b], med) / peak) * 0.8, tag))
    return levels


def rolling_vp_levels(df, window=192, step=4, top_k=6):
    """Return dict bar_index -> list[(price, strength, tag)], recomputed every
    `step` bars from the trailing `window` bars (causal). window=192 M15 bars
    ~= 2 trading days on a ~23h index; step=4 = hourly refresh."""
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    v = df["volume"].to_numpy(float) if "volume" in df else np.ones(len(df))
    out = {}
    last = None
    for t in range(window, len(df), step):
        seg = slice(t - window, t)
        glo, ghi = l[seg].min(), h[seg].max()
        if ghi <= glo:
            out[t] = last or []
            continue
        mass = _histogram(l[seg], h[seg], v[seg], glo, ghi)
        width = (ghi - glo) / N_BINS
        last = _extract_levels(mass, glo, width, top_k)
        out[t] = last
    return out


def levels_at(vp_dict, t, step=4, window=192):
    """Causal lookup: most recent recompute at or before bar t."""
    key = t - ((t - window) % step) if t >= window else None
    if key is None:
        return []
    # walk back to the nearest computed key (handles the tail)
    while key >= window and key not in vp_dict:
        key -= step
    return vp_dict.get(key, [])
