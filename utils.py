"""Shared helpers for indicator calculation.

All lookbacks are standardized to a single length (default 21 bars).
The VWAP proxy used throughout is OHLC/4, computed per bar over the full
window (daily data has no per-day VWAP reset).
"""
from __future__ import annotations

import pandas as pd


def ohlc4(df: pd.DataFrame) -> pd.Series:
    """Per-bar price proxy: (Open + High + Low + Close) / 4.

    This is the VWAP proxy used throughout the watchlist (the Typical Price (TP)
    column); daily data has no per-day VWAP reset, so OHLC / 4 is the standard
    daily substitute for intraday VWAP.
    """
    return (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4.0


def ema(series: pd.Series, length: int = 21) -> pd.Series:
    """Exponential moving average (ThinkOrSwim ExpAverage smoothing)."""
    return series.ewm(span=length, adjust=False).mean()


def median(series: pd.Series, length: int = 21) -> pd.Series:
    """Rolling median with a minimum of one observation."""
    return series.rolling(length, min_periods=1).median()


def highest(series: pd.Series, length: int = 21) -> pd.Series:
    """Rolling highest high."""
    return series.rolling(length, min_periods=1).max()


def lowest(series: pd.Series, length: int = 21) -> pd.Series:
    """Rolling lowest low."""
    return series.rolling(length, min_periods=1).min()


def true_range(high: pd.Series, price: pd.Series, low: pd.Series) -> pd.Series:
    """ThinkScript TrueRange(high, price, low).

    TrueRange(H, P, L) = Max(H - L, |H - P|, |P - L|).
    Here `price` is the VWAP proxy (Typical Price (TP)), matching the Average
    True Range (ATR) input used in Normalized ATR (NATR).
    """
    return pd.concat(
        [high - low, (high - price).abs(), (price - low).abs()], axis=1
    ).max(axis=1)
