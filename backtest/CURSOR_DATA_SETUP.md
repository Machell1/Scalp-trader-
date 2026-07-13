# Cursor data setup

This repository keeps its backtest candles in Git LFS so a fresh clone stays
small while Cursor can still reproduce research locally.

```powershell
git lfs pull
python backtest/verify_data.py
python backtest/freeze_ftmo_v130_blind.py --verify
python backtest/export_ftmo_momentum_history_snapshot.py --verify
```

The LFS-managed `backtest/data/derivM15*` directories contain the 46 canonical
M15 CSVs used by the historical harness. `backtest/data/ftmoM15_blind_20260711`
contains the frozen FTMO M15 bars for US30, US100, and JP225. The current H1 EA
can be evaluated by resampling M15 data; USDJPY is available in
`derivM15_diverse/USDJPY.csv`.

`backtest/fixtures/ftmo_momentum_pullback_history_20260713/` is a sanitized,
hash-verified forward-execution snapshot: broker deals/orders plus EA trade,
decision, and partial-close telemetry. Use it to compare simulator behavior
with live execution; it is not a substitute for historical candle data.
