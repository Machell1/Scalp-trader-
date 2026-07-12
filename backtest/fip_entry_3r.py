"""Frozen smooth-impulse predicate for the FIP 3R study."""
from types import SimpleNamespace

import numpy as np


def fip4of5(s, i):
    """True when at least four of the five formation returns align with side."""
    if i < 5 or int(s.side[i]) == 0:
        return False
    changes = np.diff(np.asarray(s.c[i - 5:i + 1], dtype=float))
    return int(np.sum(int(s.side[i]) * changes > 0.0)) >= 4


def self_test():
    passed = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        passed.append(name)

    def fixture(closes, side):
        sides = np.zeros(len(closes), dtype=np.int8)
        sides[-1] = side
        return SimpleNamespace(c=np.asarray(closes, dtype=float), side=sides)

    check("long_four_of_five_pass", fip4of5(fixture([0, 1, 2, 1, 2, 3], 1), 5))
    check("long_three_of_five_fail", not fip4of5(fixture([0, 1, 0, 1, 0, 1], 1), 5))
    check("short_four_of_five_pass", fip4of5(fixture([5, 4, 3, 4, 3, 2], -1), 5))
    check("short_three_of_five_fail", not fip4of5(fixture([5, 4, 5, 4, 5, 4], -1), 5))
    check("zero_return_not_aligned", not fip4of5(fixture([0, 1, 2, 2, 2, 3], 1), 5))
    longer = fixture([99, 0, 1, 2, 1, 2, 3], 1)
    longer.side[-1] = 1
    check("causal_window_ignores_older_bar", fip4of5(longer, 6))
    print(f"FIP entry synthetic checks: {len(passed)} passed")
    for name in passed:
        print(f"PASS {name}")
    return tuple(passed)


if __name__ == "__main__":
    self_test()
