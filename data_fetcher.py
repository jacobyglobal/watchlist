"""Thin client over the shared ``marketdata`` package.

The heavy lifting lives in ``marketdata/config.py`` (canonical universe from
config/watchlist.yaml) and ``marketdata/store.py`` (10-year OHLCV parquet
cache, TTL-wholesale). This module keeps the historic WatchList interface so
downstream code (columns.py, main.py) is unchanged:

- ``BENCHMARK`` / ``TICKERS`` / ``TICKER_TYPES`` from the canonical universe.
- ``download(tickers)`` -> {ticker: DataFrame} over the 18-month indicator
  window, sliced from the 10-year store.
"""

from __future__ import annotations

import pandas as pd

from marketdata import config as md_config
from marketdata import store as md_store

_universe = md_config.load_universe()

BENCHMARK = _universe.benchmark
TICKERS = _universe.watchlist_tickers
TICKER_TYPES = _universe.type_map

WATCHLIST_MONTHS = md_store.WATCHLIST_MONTHS


def _slice_18mo(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the trailing ~18 months (the WatchList indicator window)."""
    cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(months=WATCHLIST_MONTHS)
    return df[df.index >= cutoff]


def download(tickers: list[str], refresh: bool = False) -> dict[str, pd.DataFrame | None]:
    """Fetch the 18-month OHLCV window for `tickers` from the shared store.

    ``refresh=True`` forces a fresh download (TTL reuse disabled); on download
    failure the store falls back to its cached parquets.
    """
    max_age = 0.0 if refresh else md_store.DEFAULT_CACHE_MAX_AGE_DAYS
    frames = md_store.load_ohlcv(list(tickers), cache_max_age_days=max_age)
    data: dict[str, pd.DataFrame | None] = {}
    for ticker, df in frames.items():
        window = _slice_18mo(df)
        data[ticker] = window if not window.empty else None
    return data