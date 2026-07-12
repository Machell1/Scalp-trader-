"""Pure synthetic checks for the immediate reclaim entry mode."""
from types import SimpleNamespace

import numpy as np

from parity_engine import START
from retest_fillrealism import run


def fixture(side, reclaim_close, next_open, stop_first=False):
    n = START + 12
    o = np.full(n, 100.0)
    h = np.full(n, 100.0)
    l = np.full(n, 100.0)
    c = np.full(n, 100.0)
    atr = np.full(n, 10.0)
    watr = np.full(n, np.nan)
    sides = np.zeros(n, dtype=int)
    ep = np.arange(n, dtype=np.int64) * 900
    sides[START] = side
    watr[START] = 0.30
    c[START] = 100.0
    touch = START + 1
    entry_bar = START + 2
    if side > 0:
        l[touch], h[touch], c[touch] = 93.0, 98.0, reclaim_close
        o[entry_bar] = next_open
        l[entry_bar] = next_open - (11.0 if stop_first else 1.0)
        h[entry_bar] = next_open + 30.2
    else:
        h[touch], l[touch], c[touch] = 107.0, 102.0, reclaim_close
        o[entry_bar] = next_open
        h[entry_bar] = next_open + (11.0 if stop_first else 1.0)
        l[entry_bar] = next_open - 30.2
    return SimpleNamespace(o=o, h=h, l=l, c=c, atr=atr, watr=watr,
                           side=sides, ep=ep, cost=0.0)


def main():
    passed = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        passed.append(name)

    long_rows, long_diag = run(
        fixture(1, 95.0, 96.0), 3.0, 0.0, 0.0, 0.02,
        entry_mode="reclaim", return_diag=True,
    )
    check("long_reclaim_next_open_and_3r_trade_through",
          len(long_rows) == 1 and abs(long_rows[0][1] - 3.0) < 1e-12
          and long_diag["reclaim_pass"] == 1)

    short_rows, short_diag = run(
        fixture(-1, 105.0, 104.0), 3.0, 0.0, 0.0, 0.02,
        entry_mode="reclaim", return_diag=True,
    )
    check("short_reclaim_next_open_and_3r_trade_through",
          len(short_rows) == 1 and abs(short_rows[0][1] - 3.0) < 1e-12
          and short_diag["reclaim_pass"] == 1)

    long_reject, long_reject_diag = run(
        fixture(1, 93.5, 96.0), 3.0, 0.0, 0.0, 0.02,
        entry_mode="reclaim", return_diag=True,
    )
    check("long_nonreclaim_rejected",
          len(long_reject) == 0 and long_reject_diag["reclaim_reject"] == 1)

    short_reject, short_reject_diag = run(
        fixture(-1, 106.5, 104.0), 3.0, 0.0, 0.0, 0.02,
        entry_mode="reclaim", return_diag=True,
    )
    check("short_nonreclaim_rejected",
          len(short_reject) == 0 and short_reject_diag["reclaim_reject"] == 1)

    stop_rows, _ = run(
        fixture(1, 95.0, 96.0, stop_first=True), 3.0, 0.0, 0.0, 0.02,
        entry_mode="reclaim", return_diag=True,
    )
    check("stop_first_on_entry_bar", len(stop_rows) == 1 and stop_rows[0][1] == -1.0)

    rearm = fixture(1, 93.5, 96.0)
    second = START + 2
    rearm.side[second] = 1
    rearm.watr[second] = 0.30
    rearm.c[second] = 100.0
    rearm.l[second + 1], rearm.h[second + 1], rearm.c[second + 1] = 93.0, 98.0, 95.0
    rearm.o[second + 2] = 96.0
    rearm.l[second + 2], rearm.h[second + 2] = 95.0, 126.2
    rearm_rows, rearm_diag = run(
        rearm, 3.0, 0.0, 0.0, 0.02,
        entry_mode="reclaim", return_diag=True,
    )
    check("reject_cancels_and_resignals_next_bar",
          len(rearm_rows) == 1 and rearm_diag["signals"] == 2
          and rearm_diag["reclaim_reject"] == 1 and rearm_diag["reclaim_pass"] == 1)

    print(f"reclaim-entry synthetic checks: {len(passed)} passed")
    for name in passed:
        print(f"PASS {name}")


if __name__ == "__main__":
    main()
