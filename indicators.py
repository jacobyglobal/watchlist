"""Ported ThinkScript watchlist columns, computed on daily OHLCV.

Conventions (see plan.md):
- VWAP proxy: OHLC / 4 per bar, over the full window (no per-day reset).
- All lookbacks standardized to 21 bars, except DMHL which uses the
  52-week (252-trading-day) high/low per the DeMark High Low intent.
- Each function returns a dict of {name: Series}; complex columns also
  expose every intermediate component so viewers can recompute the values
  from the documented logic (e.g. ATR as % Price shows OHLC / 4, True Range,
  and Average True Range (ATR)). Final column names are human-readable:
  spaces only (no underscores or mixed case), e.g. "ATR as % Price".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from utils import ema, highest, lowest, median, ohlc4, true_range

LOOKBACK = 21
DMHL_LOOKBACK = 252  # 52-week high/low, per the DeMark High Low intent

_DMHL_NAN = 65.0  # dmhlNaN sentinel when the high-low range is zero


def atrpct(df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_ATRPctVWAPWATCHLIST: ((vwap + ATR) / vwap) * 100.

    Chain: OHLC / 4 -> True Range = TrueRange(H, OHLC / 4, L)
                     -> Average True Range (ATR) = EMA21(True Range)
                     -> ATR as % Price = (OHLC / 4 + ATR) / OHLC / 4 * 100
    """
    ohlc4_price = ohlc4(df)
    tr = true_range(df["High"], ohlc4_price, df["Low"])
    atr = ema(tr, LOOKBACK)
    atrpct = np.where(ohlc4_price > 0, ((ohlc4_price + atr) / ohlc4_price) * 100.0, 1.0)
    return {
        "OHLC / 4": ohlc4_price,
        "True Range": tr,
        "Average True Range (ATR)": atr,
        "ATR as % Price": pd.Series(atrpct, index=df.index),
    }


def dmhl(df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_DMHLWATCHLIST: (vwap - lowest) / (highest - lowest) * 100 - 50.

    DeMark High Low measures the current price against the 52-week
    (252-trading-day) high/low, per the original script's lookbackLength.

    Chain: 52-Wk High / 52-Wk Low -> 52-Wk Range
           = 52-Wk High - 52-Wk Low
           -> DeMark High Low Rank = (OHLC / 4 - 52-Wk Low) / 52-Wk Range * 100 - 50
    """
    ohlc4_price = ohlc4(df)
    hi = highest(df["High"], DMHL_LOOKBACK)
    lo = lowest(df["Low"], DMHL_LOOKBACK)
    rng = hi - lo
    dmhl = np.where(rng == 0, _DMHL_NAN, ((ohlc4_price - lo) / rng) * 100.0 - 50.0)
    return {
        "OHLC / 4": ohlc4_price,
        "52-Wk High": hi,
        "52-Wk Low": lo,
        "52-Wk Range": rng,
        "DeMark High Low Rank": pd.Series(np.round(dmhl, 1), index=df.index),
    }


def chg_open_pct(df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_PctChOpWATCHLIST: log(close / open) * 100."""
    return {"Close vs Open %": np.log(df["Close"] / df["Open"]) * 100.0}


def vol_avg_pct(df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_VolAvgPlusWATCHLIST: Volume / EMA21(Volume) * 100.

    Chain: Volume -> Vol EMA 21 = EMA21(Volume)
                 -> Vol % of Vol EMA 21 = Volume / Vol EMA 21 * 100
    """
    vol_ema = ema(df["Volume"], LOOKBACK)
    ratio = np.where(vol_ema > 0, df["Volume"] / vol_ema * 100.0, 100.0)
    return {
        "Vol EMA 21": vol_ema,
        "Vol % of Vol EMA 21": pd.Series(np.round(ratio, 1), index=df.index),
    }


def rel_vol_plus(df: pd.DataFrame, qqq_df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_VolQQQPlusWATCHLIST: log(volPct / qqqVolPct) * 100.

    Chain (both sides median-21):
      Vol Median 21 = Median21(Volume)
      Vol % of Vol Median 21 = Volume / Vol Median 21 * 100
      qqqVolPct    = QQQ volume / Median21(QQQ volume) * 100 (benchmark side,
                     computed internally; QQQ is a watchlist row, so its own
                     Vol % of Vol Median 21 column is the exposed equivalent)
      Relative Vol vs QQQ Market = log(Vol % of Vol Median 21 / qqqVolPct) * 100
    """
    qqq_vol = qqq_df["Volume"].copy()
    qqq_vol.index = pd.to_datetime(qqq_vol.index, utc=True).tz_localize(None)
    qqq_vol = qqq_vol.reindex(df.index)
    vol_med = median(df["Volume"], LOOKBACK)
    vol_pct = df["Volume"] / vol_med * 100.0
    qqq_vol_pct = qqq_vol / median(qqq_vol, LOOKBACK) * 100.0
    return {
        "Vol Median 21": vol_med,
        "Vol % of Vol Median 21": vol_pct,
        "Relative Vol vs QQQ Market": np.log(vol_pct / qqq_vol_pct) * 100.0,
    }


def vwap_dollar_vol(df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_vwapXVolWATCHLIST: volume * vwap / 1_000_000 (rounded)."""
    return {"Notional Value $M": np.round(df["Volume"] * ohlc4(df) / 1_000_000.0)}
