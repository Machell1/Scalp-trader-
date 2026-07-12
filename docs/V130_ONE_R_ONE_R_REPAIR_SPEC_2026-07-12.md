# v1.30 1R:1R screen implementation repair — pre-registration

This repair inherits every frozen cell, dataset, output, gate, disposition,
and ledger term from protocol
`16fc8f12a78db09424b6b6b7f30984a40e99894018f012289c8f1a669bd1f4d5`.
The first execution stopped before enumeration because `times` is a pandas
Series. The sole authorized change is `times.tz_convert(None)` to
`times.dt.tz_convert(None)`. No new hypothesis is charged and no other code or
parameter changes are allowed. The registered command remains
`python backtest/run_v130_one_r_one_r.py`.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `PENDING`

