"""Freeze read-only FTMO symbol metadata for the H1 universe study."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import MetaTrader5 as mt5


TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "h1_universe_broker_meta.json"

SOURCE_TO_FTMO = {
    "Wall_Street_30": "US30.cash",
    "US_Tech_100": "US100.cash",
    "Japan_225": "JP225.cash",
    "US_SP_500": "US500.cash",
    "US_Small_Cap_2000": "US2000.cash",
    "Germany_40": "GER40.cash",
    "France_40": "FRA40.cash",
    "UK_100": "UK100.cash",
    "Australia_200": "AUS200.cash",
    "Hong_Kong_50": "HK50.cash",
    "NGAS": "NATGAS.cash",
    "UK_Brent_Oil": "UKOIL.cash",
    "US_Oil": "USOIL.cash",
    "AUDJPY": "AUDJPY",
    "EURGBP": "EURGBP",
    "EURJPY": "EURJPY",
    "EURUSD": "EURUSD",
    "GBPJPY": "GBPJPY",
    "GBPUSD": "GBPUSD",
    "NZDUSD": "NZDUSD",
    "USDCAD": "USDCAD",
    "USDCHF": "USDCHF",
    "USDJPY": "USDJPY",
    "XAUUSD": "XAUUSD",
    "XAGUSD": "XAGUSD",
    "XCUUSD": "XCUUSD",
    "XPTUSD": "XPTUSD",
    "BTCUSD": "BTCUSD",
    "ETHUSD": "ETHUSD",
    "SOLUSD": "SOLUSD",
    "XRPUSD": "XRPUSD",
    "BCHUSD": "BCHUSD",
    "LTCUSD": "LTCUSD",
}


def commission_rule(symbol: str) -> dict[str, float | str]:
    if symbol.endswith(".cash") and symbol not in {"NATGAS.cash", "UKOIL.cash", "USOIL.cash"}:
        return {"kind": "zero", "per_side_usd_per_lot": 0.0}
    if symbol.endswith("USD") and symbol[:-3] in {"BTC", "ETH", "SOL", "XRP", "BCH", "LTC"}:
        return {"kind": "notional_fraction", "per_side_fraction": 0.000325}
    return {"kind": "usd_per_lot", "per_side_usd_per_lot": 2.5}


def main() -> None:
    if not mt5.initialize(path=TERMINAL):
        raise RuntimeError(f"MetaTrader5 initialize failed: {mt5.last_error()}")
    try:
        account = mt5.account_info()
        terminal = mt5.terminal_info()
        if account is None or terminal is None:
            raise RuntimeError(f"FTMO account/terminal unavailable: {mt5.last_error()}")
        catalogue = {item.name: item for item in mt5.symbols_get()}
        symbols = {}
        for source, name in SOURCE_TO_FTMO.items():
            info = catalogue.get(name)
            tick = mt5.symbol_info_tick(name)
            if info is None:
                raise RuntimeError(f"FTMO symbol unavailable: {source} -> {name}")
            symbols[source] = {
                "ftmo_symbol": name,
                "path": info.path,
                "digits": int(info.digits),
                "point": float(info.point),
                "spread_points": int(info.spread),
                "bid": float(tick.bid if tick is not None else info.bid),
                "ask": float(tick.ask if tick is not None else info.ask),
                "trade_contract_size": float(info.trade_contract_size),
                "trade_tick_size": float(info.trade_tick_size),
                "trade_tick_value_loss": float(info.trade_tick_value_loss),
                "trade_tick_value_profit": float(info.trade_tick_value_profit),
                "volume_min": float(info.volume_min),
                "volume_step": float(info.volume_step),
                "volume_max": float(info.volume_max),
                "trade_mode": int(info.trade_mode),
                "filling_mode": int(info.filling_mode),
                "commission": commission_rule(name),
            }
        payload = {
            "captured_utc": datetime.now(timezone.utc).isoformat(),
            "terminal_build": int(terminal.build),
            "account_login": int(account.login),
            "server": account.server,
            "symbols": symbols,
        }
        OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {OUTPUT}")
        print(f"symbols {len(symbols)}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
