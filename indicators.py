"""Ported ThinkScript watchlist columns, computed on daily OHLCV.

Conventions (see plan.md):
- VWAP proxy: Typical Price (TP) = OHLC / 4 per bar, over the full window
  (no per-day reset).
- All lookbacks standardized to 21 bars, except DMHL which uses the
  52-week (252-trading-day) high/low per the DeMark High Low intent.
- Each function returns a dict of {name: Series}; complex columns also
  expose every intermediate component so viewers can recompute the values
  from the documented logic (e.g. Normalized ATR (NATR) shows Typical Price
  (TP), True Range (TR), and Average True Range (ATR)). Final column names
  are human-readable professional labels, e.g. "Normalized ATR (NATR)".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from utils import ema, highest, lowest, median, ohlc4, true_range

LOOKBACK = 21
DMHL_LOOKBACK = 252  # 52-week high/low, per the DeMark High Low intent

_DMHL_NAN = 65.0  # dmhlNaN sentinel when the high-low range is zero

JRI_TIMEFRAMES = (
    (20, 0.15),  # 4 weeks
    (60, 0.20),  # 12 weeks
    (130, 0.25),  # 26 weeks
    (252, 0.40),  # 52 weeks
)
_JRI_PROXIMITY = 0.5  # max linear weight bonus when price hugs a boundary

_JVPO_FAST_WINDOW = 20
_JVPO_SLOW_WINDOW = 252
_JVPO_SHORT_FAST = 8  # fast window for tickers with < 252 bars (recent IPOs)
_JVPO_FAST_BINS = 40
_JVPO_SLOW_BINS = 70


def atrpct(df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_ATRPctVWAPWATCHLIST: ((vwap + ATR) / vwap) * 100.

    Chain: Typical Price (TP) -> True Range (TR) = TrueRange(H, TP, L)
                    -> Average True Range (ATR) = EMA21(True Range (TR))
                    -> Normalized ATR (NATR) = (TP + ATR) / TP * 100
    """
    tp = ohlc4(df)
    tr = true_range(df["High"], tp, df["Low"])
    atr = ema(tr, LOOKBACK)
    natr = np.where(tp > 0, ((tp + atr) / tp) * 100.0, 1.0)
    return {
        "Typical Price (TP)": tp,
        "True Range (TR)": tr,
        "Average True Range (ATR)": atr,
        "Normalized ATR (NATR)": pd.Series(natr, index=df.index),
    }


def dmhl(df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_DMHLWATCHLIST: (vwap - lowest) / (highest - lowest) * 100 - 50.

    DeMark High Low measures the current price against the 52-week
    (252-trading-day) high/low, per the original script's lookbackLength.

    Chain: 52-Week High / 52-Week Low -> 52-Week Range Position
           = 52-Week High - 52-Week Low
           -> TD Range Rank = (Typical Price (TP) - 52-Week Low)
                              / 52-Week Range Position * 100 - 50
    """
    tp = ohlc4(df)
    hi = highest(df["High"], DMHL_LOOKBACK)
    lo = lowest(df["Low"], DMHL_LOOKBACK)
    rng = hi - lo
    rank = np.where(rng == 0, _DMHL_NAN, ((tp - lo) / rng) * 100.0 - 50.0)
    return {
        "Typical Price (TP)": tp,
        "52-Week High": hi,
        "52-Week Low": lo,
        "52-Week Range Position": rng,
        "TD Range Rank": pd.Series(np.round(rank, 1), index=df.index),
    }


def jacoby_range_index(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Jacoby Range Index: multi-timeframe DeMark position, linear distance weighting.

    Chain: Typical Price (TP) + rolling 20/60/130/252-bar High/Low boundaries
           -> per-timeframe RangePos = (TP - Low) / (High - Low) * 100 - 50
           -> weight = base_weight * (1 + proximity * |RangePos| / 50),
              base_weight 0.15 / 0.20 / 0.25 / 0.40, proximity = 0.5
           -> weighted-average composite score, rounded to 1 decimal.
    The 52-week timeframe carries the highest base weight, so the score stays
    anchored to the annual range while shorter timeframes modulate it when
    price actively presses on their boundaries.
    """
    tp = ohlc4(df).to_numpy(dtype=float)
    bounds = [
        (
            highest(df["High"], lb).to_numpy(dtype=float),
            lowest(df["Low"], lb).to_numpy(dtype=float),
        )
        for lb, _ in JRI_TIMEFRAMES
    ]
    scores = np.full(len(df), np.nan)
    for i in range(len(df)):
        tp_i = tp[i]
        positions = np.empty(len(JRI_TIMEFRAMES))
        weights = np.empty(len(JRI_TIMEFRAMES))
        for j, ((_, base_w), (highs, lows)) in enumerate(
            zip(JRI_TIMEFRAMES, bounds)
        ):
            rng = highs[i] - lows[i]
            pos = 0.0 if rng == 0 else (tp_i - lows[i]) / rng * 100.0 - 50.0
            positions[j] = pos
            weights[j] = base_w * (1.0 + _JRI_PROXIMITY * abs(pos) / 50.0)
        total_w = weights.sum()
        scores[i] = (
            positions.mean()
            if total_w == 0
            else (positions * weights).sum() / total_w
        )
    return {"Jacoby Range Index": pd.Series(np.round(scores, 1), index=df.index)}


def chg_open_pct(df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_PctChOpWATCHLIST: log(close / open) * 100."""
    return {"Session Return %": np.log(df["Close"] / df["Open"]) * 100.0}


def vol_avg_pct(df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_VolAvgPlusWATCHLIST: Volume / EMA21(Volume) * 100.

    Chain: Volume -> 21-Period EMA Volume = EMA21(Volume)
                 -> Relative Volume (RVOL EMA) = Volume / 21-Period EMA Volume * 100
    """
    vol_ema = ema(df["Volume"], LOOKBACK)
    ratio = np.where(vol_ema > 0, df["Volume"] / vol_ema * 100.0, 100.0)
    return {
        "21-Period EMA Volume": vol_ema,
        "Relative Volume (RVOL EMA)": pd.Series(np.round(ratio, 1), index=df.index),
    }


def rel_vol_plus(df: pd.DataFrame, qqq_df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_VolQQQPlusWATCHLIST: log(volPct / qqqVolPct) * 100.

    Chain (both sides median-21):
      21-Period Median Volume = Median21(Volume)
      Relative Volume (RVOL Median) = Volume / 21-Period Median Volume * 100
      qqqVolPct    = QQQ volume / Median21(QQQ volume) * 100 (benchmark side,
                     computed internally; QQQ is a watchlist row, so its own
                     Relative Volume (RVOL Median) column is the exposed
                     equivalent)
      Idiosyncratic RVOL = log(Relative Volume (RVOL Median) / qqqVolPct) * 100
    """
    qqq_vol = qqq_df["Volume"].copy()
    qqq_vol.index = pd.to_datetime(qqq_vol.index, utc=True).tz_localize(None)
    qqq_vol = qqq_vol.reindex(df.index)
    vol_med = median(df["Volume"], LOOKBACK)
    vol_pct = df["Volume"] / vol_med * 100.0
    qqq_vol_pct = qqq_vol / median(qqq_vol, LOOKBACK) * 100.0
    return {
        "21-Period Median Volume": vol_med,
        "Relative Volume (RVOL Median)": vol_pct,
        "Idiosyncratic RVOL": np.log(vol_pct / qqq_vol_pct) * 100.0,
    }


def vwap_dollar_vol(df: pd.DataFrame) -> dict[str, pd.Series]:
    """CJ_vwapXVolWATCHLIST: volume * vwap / 1_000_000 (rounded)."""
    return {"Notional Turnover ($M)": np.round(df["Volume"] * ohlc4(df) / 1_000_000.0)}


def _synthetic_vpoc_last(df: pd.DataFrame, window: int, num_bins: int) -> float:
    """Synthetic Volume Point of Control for the trailing `window` bars.

    Each bar's volume is allocated proportionally across the price bins its
    High-Low range touches; the estimated VPOC is the midpoint of the bin with
    the most accumulated volume. Only the final window is needed for the
    watchlist's latest-bar column.
    """
    wdf = df.iloc[-window:]
    min_p = float(wdf["Low"].min())
    max_p = float(wdf["High"].max())
    if min_p == max_p or np.isnan(min_p):
        return float(wdf["Close"].iloc[-1])
    bins = np.linspace(min_p, max_p, num_bins + 1)
    bin_volumes = np.zeros(num_bins)
    highs = wdf["High"].to_numpy(dtype=float)
    lows = wdf["Low"].to_numpy(dtype=float)
    vols = wdf["Volume"].to_numpy(dtype=float)
    for h, l, v in zip(highs, lows, vols):
        if h == l or v == 0 or np.isnan(v):
            continue
        overlap = np.maximum(0.0, np.minimum(bins[1:], h) - np.maximum(bins[:-1], l))
        bin_volumes += v * overlap / (h - l)
    idx = int(np.argmax(bin_volumes))
    return float((bins[idx] + bins[idx + 1]) / 2.0)


def _jvpo_windows(n: int) -> tuple[int, int]:
    """(fast, slow) VPOC windows for a ticker with `n` bars.

    Tickers with fewer than 252 bars (recent IPOs such as SPCX, ~36 bars)
    use the full available history for the slow annual baseline and an 8-bar
    fast window, since the 252-bar baseline is unavailable.
    """
    if n >= _JVPO_SLOW_WINDOW:
        return _JVPO_FAST_WINDOW, _JVPO_SLOW_WINDOW
    return _JVPO_SHORT_FAST, n


def jacoby_volume_profile_oscillator(df: pd.DataFrame) -> dict[str, float]:
    """Jacoby Volume Profile Oscillator: ln(Fast VPOC / Slow VPOC) * 100.

    Fast VPOC = synthetic VPOC over the last 20 bars (40 bins); Slow VPOC =
    synthetic VPOC over the last 252 bars (70 bins) - the annual baseline.
    Log scaling preserves the 1-year macro anchor while compressing the +500%
    outliers of multi-bagger re-ratings; for moderate values it tracks the
    linear percentage closely. Positive = short-term volume migrating above
    the annual macro fair value; negative = compressed below it. See
    _jvpo_windows for short-history tickers.
    """
    fast_window, slow_window = _jvpo_windows(len(df))
    fast_vpoc = _synthetic_vpoc_last(df, fast_window, _JVPO_FAST_BINS)
    slow_vpoc = _synthetic_vpoc_last(df, slow_window, _JVPO_SLOW_BINS)
    if np.isnan(fast_vpoc) or np.isnan(slow_vpoc) or slow_vpoc <= 0:
        score = 0.0
    else:
        score = np.log(fast_vpoc / slow_vpoc) * 100.0
    return {"Jacoby Volume Profile Oscillator": round(float(score), 2)}
