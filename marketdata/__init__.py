"""Shared market data module for the WatchList/MarketHighs pipeline.

Single source of truth for the ticker universe (WatchList/config/watchlist.yaml)
and raw daily OHLCV price history (parquet cache in MarketHighs/data, a
regenerable cache - never committed). Consumed by WatchList (daily indicators),
MarketHighs (horizon/decile analysis) and, via synced outputs, TheChasIX.com.
See WatchList/unifyData_plan.md.
"""

from . import config, contract, store

__all__ = ["config", "contract", "store"]