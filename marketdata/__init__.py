"""Shared market data module for the WatchList/MarketHighs pipeline.

Single source of truth for the ticker universe (WatchList/config/watchlist.yaml)
and raw daily OHLCV price history (parquet cache in output/prices, a
regenerable cache - never committed). Consumed by WatchList (daily indicators),
MarketHighs (horizon/decile analysis) and, via synced outputs, TheChasIX.com.

- config: universe parsing -> entries/sector_map/type_map/benchmark
- store: 10y OHLCV fetch + TTL-wholesale parquet cache
- contract: merged wide-table schema + schema-v3 column guide
- build_combined: merge indicator + horizon/decile rows
- sync_to_chasix: copy combined artifacts into TheChasIX.com/data/watchlist/

See WatchList/unifyData_plan.md.
"""

from . import config, contract, store

__all__ = ["config", "contract", "store"]