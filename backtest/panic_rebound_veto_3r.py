"""Frozen panic-rebound veto predicate for the 3R entry study."""
from types import SimpleNamespace

import numpy as np


def components(s, i):
    if i < 96 or i < 37 or int(s.side[i]) == 0:
        return None
    history = np.asarray(s.atr[i - 96:i], dtype=float)
    finite = history[np.isfinite(history)]
    if len(finite) != 96 or not np.isfinite(s.atr[i]) or s.atr[i] <= 0:
        return None
    threshold = float(np.percentile(finite, 80.0))
    prior_signed_atr = (
        int(s.side[i]) * (float(s.c[i - 5]) - float(s.c[i - 37])) / float(s.atr[i])
    )
    return prior_signed_atr, threshold


def admit_unless_panic_rebound(s, i):
    state = components(s, i)
    if state is None:
        return True
    prior_signed_atr, threshold = state
    veto = prior_signed_atr <= -2.0 and float(s.atr[i]) >= threshold
    return not veto


def self_test():
    passed = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        passed.append(name)

    def fixture(side, prior_start, prior_end, signal_atr=2.0, history_atr=1.0):
        n, i = 110, 100
        c = np.full(n, prior_end, dtype=float)
        c[i - 37] = prior_start
        c[i - 5] = prior_end
        atr = np.full(n, history_atr, dtype=float)
        atr[i] = signal_atr
        sides = np.zeros(n, dtype=np.int8)
        sides[i] = side
        return SimpleNamespace(c=c, atr=atr, side=sides), i

    s, i = fixture(1, 100.0, 95.0)
    check("long_panic_rebound_veto", not admit_unless_panic_rebound(s, i))
    s, i = fixture(-1, 100.0, 105.0)
    check("short_panic_rebound_veto", not admit_unless_panic_rebound(s, i))
    s, i = fixture(1, 100.0, 105.0)
    check("long_prior_alignment_admitted", admit_unless_panic_rebound(s, i))
    s, i = fixture(-1, 100.0, 95.0)
    check("short_prior_alignment_admitted", admit_unless_panic_rebound(s, i))
    s, i = fixture(1, 100.0, 96.0, signal_atr=2.0, history_atr=2.0)
    check("exact_thresholds_veto", not admit_unless_panic_rebound(s, i))
    state = components(s, i)
    check("signal_atr_excluded_from_percentile", state is not None and state[1] == 2.0)
    check("incomplete_history_admitted", admit_unless_panic_rebound(s, 20))
    print(f"panic-veto synthetic checks: {len(passed)} passed")
    for name in passed:
        print(f"PASS {name}")
    return tuple(passed)


if __name__ == "__main__":
    self_test()
