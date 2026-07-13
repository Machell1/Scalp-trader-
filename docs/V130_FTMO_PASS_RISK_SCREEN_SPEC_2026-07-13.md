# v1.30 FTMO pass-probability risk-allocation screen — pre-registration

The registered C0/C1/P1 policies fail the 88% two-phase target, especially in
E2 stress. This screen tests three account-risk allocations with the frozen
v1.30 entry/cost tape, same 20-day moving-block bootstrap, seed
13020260711, common-random-number path IDs 0..9,999, and the same FTMO/EA rules:

* R4: JP225/US100 0.40% phase 1 and 0.20% phase 2; US30 0.01%/0.005%.
* R3: JP225/US100 0.30%/0.15%; US30 0.01%/0.005%.
* R5: JP225/US100 0.50%/0.25%; US30 0.01%/0.005%.

The screen is exploratory and is not a promotion result. It uses E1 measured
and E2 stress modes, 10,000 paths per mode, and reports the same point and
Wilson statistics. A candidate is only eligible for a full 100,000-path
confirmatory cell if its screen point estimate is at least 0.88, its stress
hard-halt rate is below 0.10, and its stress timeout rate is below 0.02. A
screen failure kills that candidate; cells are not combined or tuned after the
fact. C0/C1/P1 results remain the frozen controls.

Ledger charge proposed: three exploratory risk-allocation cells (R4/R3/R5),
with no entry-strategy hypothesis. No terminal access or data refresh is
allowed.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `b9f9ba6b11129a7b6c38b7a15c31bc3d1e679647f3712cf2ec0ac7c090ffc246`
