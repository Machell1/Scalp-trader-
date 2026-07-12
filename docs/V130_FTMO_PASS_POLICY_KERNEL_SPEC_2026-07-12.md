# v1.30 FTMO pass-policy reference-kernel execution repair — pre-registration

The worker-initializer protocol passed its direct-versus-worker invariant but
the reference account replay remains impractical at roughly tens of seconds per
path. This execution-only repair retains the same tape, policies, bootstrap
seed, path IDs, account rules, gates, and ledger. It permits only:

* versioned caching of marked/conservative equity between unchanged account
  states;
* a flat-account rail fast path;
* cached normalized event-kind dispatch;
* cached eligible flat-block enumeration; and
* reuse of immutable replay rows across C0/C1/P1 within one path.

The pre-event rail check is skipped only when the immediately preceding event
already checked rails and the EA server-day token is unchanged; timestamp
advance and target-pending cancellation cannot change equity. A direct
one-path comparison for C0, C1, and P1 must be byte/equality identical before
the full registered run. Synthetic checks must remain green. No policy, risk,
entry, cost, data, random stream, or gate change is permitted. Hypothesis
charge: zero; no blind frame or terminal access.

Registered command: `python -u backtest/run_v130_pass_policy.py --development`.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `841ed68e0424d41881a187e54ad4d57858a2aa175d8d0abc52c18622c7db4029`
