# FTMO Momentum Pullback execution-history snapshot

This is a sanitized, immutable fixture for validating the live EA against broker history and its own telemetry. It is not a substitute for candle data.

- `deals.csv`: all broker deals whose magic is 770077 or 771025.
- `orders.csv`: all corresponding broker orders.
- `MomentumPullback_*.csv`: EA telemetry captured at export time.
- `METADATA.json`: venue, schema, count, and retrieval provenance without account credentials or login.
- `MANIFEST.sha256`: SHA256 hashes for every file above.

Ticket, order, and position identifiers are deterministic one-way snapshot identifiers; comments, external IDs, account number, terminal data path, and credentials are excluded.

Cursor setup: run `git lfs pull`, then `python backtest/verify_data.py` and `python backtest/export_ftmo_momentum_history_snapshot.py --verify`.
