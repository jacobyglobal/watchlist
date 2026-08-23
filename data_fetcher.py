"""Download and cache daily OHLCV data from yfinance.

Raw (unadjusted) daily bars are used to match ThinkOrSwim price series.
Each ticker's history is cached to output/raw/{ticker}.csv and reused on
subsequent runs unless `refresh=True`.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import yaml
import yfinance as yf

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "watchlist.yaml"


def _load_config() -> dict:
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f)


_config = _load_config()
BENCHMARK = _config["benchmark"]
TICKERS = [t["symbol"] for t in _config["tickers"] if t.get("enabled", True)]

PERIOD = "18mo"
INTERVAL = "1d"
_OHLCV_COLS = ["Open", "High", "Low", "Close", "Volume"]

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "output" / "raw"


def _normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    """Convert the index to naive daily dates (drop tz / time-of-day).

    yfinance returns tz-aware timestamps that round-trip through CSV with
    mixed UTC offsets (DST), which pandas 3.x refuses to parse. Normalizing
    to naive dates avoids the issue and makes cross-ticker reindexing exact.
    """
    idx = pd.to_datetime(df.index, utc=True).tz_localize(None)
    return df.set_axis(pd.DatetimeIndex(idx.date), axis=0)


def _fetch_one(ticker: str, refresh: bool = False) -> tuple[str, pd.DataFrame | None]:
    cache_path = RAW_DIR / f"{ticker}.csv"
    if not refresh and cache_path.exists():
        try:
            cached = _normalize_index(
                pd.read_csv(cache_path, index_col=0, parse_dates=True)
            )
            if not cached.empty:
                return ticker, cached
        except Exception:
            pass

    hist = yf.Ticker(ticker).history(
        period=PERIOD, interval=INTERVAL, auto_adjust=False
    )
    if hist is None or hist.empty:
        return ticker, None

    df = _normalize_index(hist[_OHLCV_COLS].dropna())
    if df.empty:
        return ticker, None

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path)
    return ticker, df


def download(tickers: list[str], refresh: bool = False) -> dict[str, pd.DataFrame | None]:
    """Fetch histories for all tickers in parallel, returning {ticker: df|None}."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    data: dict[str, pd.DataFrame | None] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for ticker, df in pool.map(
            lambda t: _fetch_one(t, refresh), tickers
        ):
            data[ticker] = df
    return data
