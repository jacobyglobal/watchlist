"""10-year OHLCV price store shared by WatchList and MarketHighs.

One parquet per ticker: ``date`` index (naive daily) + ``Open, High, Low,
Close, Volume`` from raw / unadjusted bars (matches thinkorswim intent, and
now the basis for ALL close-based metrics in both projects).

Cache policy mirrors MarketHighs' historic loader: the cache exists for
offline resilience and to avoid re-hitting Yahoo on back-to-back runs - never
as an incremental store. Adjusted prices are retroactively restated by
splits/dividends, so caches are only reused whole (within
``cache_max_age_days``) or replaced wholesale by a fresh download; rows are
never appended. If the download fails, the (possibly stale) cache is used as a
fallback.

Note: the cache does not record which ``years`` span produced it - if you
change the span, delete the cache dir or wait out the TTL.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
CACHE_DIR = REPO_ROOT / "output" / "prices"

FIELDS = ["Open", "High", "Low", "Close", "Volume"]

DEFAULT_YEARS = 10
# Reuse cached parquets only if every file was written within this many days
# (0 disables reuse; the cache is then used solely as a download fallback).
DEFAULT_CACHE_MAX_AGE_DAYS: float = 1.0

# WatchList indicators only need ~18 months; keep the exact window they used.
WATCHLIST_MONTHS = 18


class DataLoadError(RuntimeError):
    """Raised when historical price data cannot be obtained."""


def _cache_paths(cache_dir: Path, tickers: list[str]) -> dict[str, Path]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return {t: cache_dir / f"{t}.parquet" for t in tickers}


def _normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    """Convert tz-aware yfinance timestamps to naive daily dates.

    Avoids mixed-UTC-offset parsing issues on re-read and makes cross-ticker
    reindexing exact.
    """
    idx = pd.to_datetime(df.index, utc=True).tz_localize(None)
    return df.set_axis(pd.DatetimeIndex(idx.date), axis=0)


def _read_cached_frame(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        return df.sort_index()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed reading cache at %s: %s", path, exc)
        return None


def _cache_is_fresh(paths: dict[str, Path], max_age_days: float) -> bool:
    """True when every ticker's parquet exists and was written within the TTL."""
    if max_age_days <= 0:
        return False
    cutoff = datetime.now().timestamp() - max_age_days * 86400.0
    for path in paths.values():
        try:
            if not path.exists() or path.stat().st_mtime < cutoff:
                return False
        except OSError as exc:
            logger.warning("Cache freshness check failed for %s: %s", path, exc)
            return False
    return True


def _load_cached(tickers: list[str], paths: dict[str, Path]) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for t in tickers:
        df = _read_cached_frame(paths[t])
        if df is None or "Close" not in df.columns or df["Close"].isna().all():
            continue
        frames[t] = df
    return frames


def _extract_fields(raw: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Split a yfinance OHLC result into {field: DataFrame(ticker columns)}."""
    cols = raw.columns
    frames: dict[str, pd.DataFrame] = {}
    if isinstance(cols, pd.MultiIndex):
        present = set(cols.get_level_values(0))
        for field in FIELDS:
            if field in present:
                sub = raw[field].copy()
                sub.columns = [c[-1] if isinstance(c, tuple) else c for c in sub.columns]
                frames[field] = sub[[t for t in tickers if t in sub.columns]]
    else:
        # Single-ticker result: columns are the price fields themselves.
        ticker = tickers[0]
        for field in FIELDS:
            if field in cols:
                frames[field] = pd.DataFrame({ticker: raw[field]})
    return frames


def _save_cache(
    paths: dict[str, Path],
    ticker_frames: dict[str, pd.DataFrame],
) -> None:
    for t, df in ticker_frames.items():
        try:
            df.to_parquet(paths[t])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed caching %s: %s", t, exc)


def load_ohlcv(
    tickers: list[str],
    cache_dir: Path | None = None,
    years: int = DEFAULT_YEARS,
    period: str | None = None,
    cache_max_age_days: float = DEFAULT_CACHE_MAX_AGE_DAYS,
) -> dict[str, pd.DataFrame]:
    """Return a {ticker: DataFrame(Open, High, Low, Close, Volume)} cache.

    The cache is reused only when it covers exactly the requested tickers AND
    every parquet is younger than ``cache_max_age_days``; otherwise a fresh
    full download replaces it. If the download fails, the (possibly stale)
    cache is used as a fallback.
    """
    cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    paths = _cache_paths(cache_dir, tickers)

    cached = _load_cached(tickers, paths)
    if (
        len(cached) == len(tickers)
        and _cache_is_fresh(paths, cache_max_age_days)
    ):
        logger.info("Loaded fresh prices from cache: %d tickers", len(cached))
        return cached

    span = period or f"{max(1, years)}y"
    try:
        raw = yf.download(
            tickers,
            period=span,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception as exc:  # noqa: BLE001
        if not cached:
            raise DataLoadError(
                f"yfinance download failed ({exc}) and no cache available"
            ) from exc
        logger.warning("Download failed, falling back to cache: %s", exc)
        return cached

    fields = _extract_fields(raw, tickers)
    if "Close" not in fields or fields["Close"].empty:
        if not cached:
            raise DataLoadError("Downloaded data missing Close and no cache exists")
        logger.warning("Downloaded data empty, falling back to cache")
        return cached

    ticker_frames: dict[str, pd.DataFrame] = {}
    for t in tickers:
        parts: dict[str, pd.Series] = {
            f: fields[f][t] for f in FIELDS if t in fields.get(f, pd.DataFrame()).columns
        }
        if "Close" not in parts:
            continue
        df = _normalize_index(pd.DataFrame(parts).sort_index())
        if df["Close"].isna().all() or df.empty:
            continue
        df = df.dropna(subset=["Close"])
        ticker_frames[t] = df

    if not ticker_frames:
        if not cached:
            raise DataLoadError("Downloaded data empty and no cache exists")
        logger.warning("Downloaded data produced no frames, falling back to cache")
        return cached

    _save_cache(paths, ticker_frames)
    merged = {t: cached[t] for t in tickers if t in cached}
    merged.update(ticker_frames)
    logger.info(
        "Downloaded and cached %d prices for %d tickers", len(ticker_frames), len(tickers)
    )
    return {t: merged[t] for t in tickers if t in merged}