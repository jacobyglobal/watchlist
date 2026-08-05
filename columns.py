"""Assemble the final watchlist table from per-ticker indicator results."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from data_fetcher import download
from indicators import (
    atrpct,
    chg_open_pct,
    dmhl,
    jacoby_range_index,
    jacoby_volume_profile_oscillator,
    rel_vol_plus,
    vol_avg_pct,
    vwap_dollar_vol,
)

_BASE_COLS = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume (Vol)"]

_COMPUTED_ORDER = [
    "Typical Price (TP)",
    "True Range (TR)", "Average True Range (ATR)", "Normalized ATR (NATR)",
    "52-Week High", "52-Week Low", "52-Week Range Position", "TD Range Rank",
    "Session Return %",
    "21-Period EMA Volume", "Relative Volume (RVOL EMA)",
    "21-Period Median Volume", "Relative Volume (RVOL Median)",
    "Idiosyncratic RVOL",
    "Notional Turnover ($M)",
    "Jacoby Range Index",
    "Jacoby Volume Profile Oscillator",
]

# Human + machine readable guide for every output column, kept in lockstep
# with _COMPUTED_ORDER above. Emitted to output/column_guide.json alongside
# the CSV. `kind` is one of base / intermediate / computed (per plan.md).
_BASE_GUIDE = [
    {"name": "Ticker", "kind": "base", "formula": "", "meaning": "Symbol from the watchlist.", "recompute": ""},
    {"name": "Date", "kind": "base", "formula": "", "meaning": "Trading date of the latest bar used for the row.", "recompute": ""},
    {"name": "Open", "kind": "base", "formula": "", "meaning": "Raw daily open from yfinance.", "recompute": ""},
    {"name": "High", "kind": "base", "formula": "", "meaning": "Raw daily high from yfinance.", "recompute": ""},
    {"name": "Low", "kind": "base", "formula": "", "meaning": "Raw daily low from yfinance.", "recompute": ""},
    {"name": "Close", "kind": "base", "formula": "", "meaning": "Raw daily close from yfinance.", "recompute": ""},
    {
        "name": "Volume (Vol)",
        "kind": "base",
        "formula": "",
        "meaning": "Raw daily share volume (Vol = Volume); basis for all Vol ... columns.",
        "recompute": "",
    },
]

_COMPUTED_GUIDE = [
    {
        "name": "Typical Price (TP)",
        "kind": "intermediate",
        "formula": "(Open + High + Low + Close) / 4",
        "meaning": "A per-bar typical-price proxy standing in for intraday VWAP throughout the watchlist (used by Normalized ATR (NATR), TD Range Rank, Notional Turnover ($M), and the Jacoby indicators).",
        "recompute": "",
    },
    {
        "name": "True Range (TR)",
        "kind": "intermediate",
        "formula": "Max(High - Low, |High - Typical Price (TP)|, |Typical Price (TP) - Low|)",
        "meaning": "The daily true range of the bar, measured from the Typical Price (TP) proxy price instead of the close. It is the input series to Average True Range (ATR).",
        "recompute": "",
    },
    {
        "name": "Average True Range (ATR)",
        "kind": "intermediate",
        "formula": "EMA21(True Range (TR))",
        "meaning": "The 21-day average true range anchored at the Typical Price (TP) proxy price - a volatility measure in dollar terms.",
        "recompute": "",
    },
    {
        "name": "Normalized ATR (NATR)",
        "kind": "computed",
        "formula": "((Typical Price (TP) + Average True Range (ATR)) / Typical Price (TP)) * 100",
        "meaning": "Average True Range (ATR) expressed as a percentage of price. Normalized ATR (NATR) - 100 is the ATR as a % of price; values well above 100 indicate an expanded daily range relative to price.",
        "recompute": "(Typical Price (TP) + Average True Range (ATR)) / Typical Price (TP) * 100",
    },
    {
        "name": "52-Week High",
        "kind": "intermediate",
        "formula": "Highest(High, 252)",
        "meaning": "The 52-week trading range boundary - the upper DeMark High/Low reference level.",
        "recompute": "",
    },
    {
        "name": "52-Week Low",
        "kind": "intermediate",
        "formula": "Lowest(Low, 252)",
        "meaning": "The 52-week trading range boundary - the lower DeMark High/Low reference level.",
        "recompute": "",
    },
    {
        "name": "52-Week Range Position",
        "kind": "intermediate",
        "formula": "52-Week High - 52-Week Low",
        "meaning": "The width of the 52-week high-low range, in dollars. The band against which TD Range Rank places the current price.",
        "recompute": "",
    },
    {
        "name": "TD Range Rank",
        "kind": "computed",
        "formula": "((Typical Price (TP) - 52-Week Low) / 52-Week Range Position) * 100 - 50   (rounded to 1 decimal)",
        "meaning": "Where the Typical Price (TP) price sits inside the 52-week high-low range, on a 0-centered scale of [-50, +50]. Above zero = upper half of the yearly range; below zero = lower half. The sentinel 65.0 is used when the range is zero (rare).",
        "recompute": "(Typical Price (TP) - 52-Week Low) / 52-Week Range Position * 100 - 50",
    },
    {
        "name": "Session Return %",
        "kind": "computed",
        "formula": "log(Close / Open) * 100",
        "meaning": "Continuously-compounded percent change from the open to the close. Positive = closed above the open; negative = closed below.",
        "recompute": "",
    },
    {
        "name": "21-Period EMA Volume",
        "kind": "intermediate",
        "formula": "EMA21(Volume)",
        "meaning": "The 21-day exponential moving average of volume (Vol). The baseline for Relative Volume (RVOL EMA).",
        "recompute": "",
    },
    {
        "name": "Relative Volume (RVOL EMA)",
        "kind": "computed",
        "formula": "Volume / 21-Period EMA Volume * 100   (rounded to 1 decimal)",
        "meaning": "Current volume relative to its 21-day exponential average. 100 = average activity; >130 = heavy volume; <80 = light volume.",
        "recompute": "Volume / 21-Period EMA Volume * 100",
    },
    {
        "name": "21-Period Median Volume",
        "kind": "intermediate",
        "formula": "Median(Volume, 21)",
        "meaning": "The 21-day median volume (Vol) - the baseline for the ticker side of Idiosyncratic RVOL.",
        "recompute": "",
    },
    {
        "name": "Relative Volume (RVOL Median)",
        "kind": "computed",
        "formula": "Volume / 21-Period Median Volume * 100",
        "meaning": "The ticker's volume (Vol) as a percentage of its own 21-day median volume. 100 = median activity.",
        "recompute": "Volume / 21-Period Median Volume * 100",
    },
    {
        "name": "Idiosyncratic RVOL",
        "kind": "computed",
        "formula": "log(Relative Volume (RVOL Median) / qqqVolPct) * 100   where qqqVolPct = QQQ row's Relative Volume (RVOL Median)",
        "meaning": "The ticker's volume (Vol) normalized against the market's (QQQ's) relative volume, log-scaled. 0 = the stock's volume activity matches the market's; positive = trading on relatively higher volume than the market; negative = lighter. The name reflects the market-normalized, asset-specific (idiosyncratic) component of volume.",
        "recompute": "log(Relative Volume (RVOL Median) / QQQ's Relative Volume (RVOL Median)) * 100, using the QQQ row for the denominator",
    },
    {
        "name": "Notional Turnover ($M)",
        "kind": "computed",
        "formula": "round(Volume * Typical Price (TP) / 1_000_000)",
        "meaning": "Dollar value traded for the day in millions (volume weighted at the Typical Price (TP) proxy price). A liquidity/participation measure: large, liquid names show high values. Holds the raw numeric value for easy sorting.",
        "recompute": "Volume * Typical Price (TP) / 1_000_000, rounded",
    },
    {
        "name": "Jacoby Range Index",
        "kind": "computed",
        "formula": "Weighted average of RangePos_i across the 4/12/26/52-week boundaries, weight_i = base_weight_i * (1 + 0.5 * |RangePos_i| / 50); RangePos_i = (Typical Price (TP) - Low_i) / (High_i - Low_i) * 100 - 50; base weights 0.15 / 0.20 / 0.25 / 0.40   (rounded to 1 decimal)",
        "meaning": "A multi-timeframe DeMark position score on the same [-50, +50] scale as TD Range Rank. The 52-week (0.40), 26-week (0.25), 12-week (0.20), and 4-week (0.15) range positions are blended with a linear proximity bonus: a timeframe whose boundary price is actively hugging earns up to a 50% weight boost, while mid-range timeframes keep their base weight. The heavier macro base weights keep the score anchored to the annual structure, so short-term boundary pressure modulates rather than overwhelms the 52-week trend. Above zero = upper half of the structural range.",
        "recompute": "",
    },
    {
        "name": "Jacoby Volume Profile Oscillator",
        "kind": "computed",
        "formula": "ln(Fast VPOC / Slow VPOC) * 100, rounded to 2 decimals. Fast VPOC = synthetic volume point of control over the last 20 bars (40 bins); Slow VPOC = over the last 252 bars (70 bins).",
        "meaning": "Short-term institutional volume migration vs the annual baseline. Log scaling preserves the 1-year macro anchor while compressing the +500% outliers of multi-bagger re-ratings (max near +200%); for moderate values it tracks the linear percentage closely. Positive = the fast 20-bar VPOC sits above the 252-bar annual VPOC (upward structural migration); negative = compressed below it. Tickers with fewer than 252 bars of history (recent IPOs such as SPCX, ~36 bars) use the full available history for the slow baseline and an 8-bar fast window, since the 252-bar annual baseline is unavailable.",
        "recompute": "",
    },
]

COLUMN_GUIDE = _BASE_GUIDE + _COMPUTED_GUIDE


def write_column_guide(path: str | Path) -> Path:
    """Emit the pretty-printed column guide JSON alongside the CSV."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "schema": "watchlist-column-guide",
            "version": 2,
            "column_count": len(COLUMN_GUIDE),
        },
        "columns": COLUMN_GUIDE,
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out_path


def build_watchlist(
    tickers: list[str], benchmark: str, refresh: bool = False
) -> pd.DataFrame:
    """One row per ticker with the latest bar's base + computed values."""
    symbols = list(dict.fromkeys(tickers + [benchmark]))
    data = download(symbols, refresh=refresh)

    qqq_df = data.get(benchmark)
    if qqq_df is None or qqq_df.empty:
        raise RuntimeError(f"Failed to fetch benchmark data for {benchmark}")

    rows: list[dict] = []
    for ticker in tickers:
        df = data.get(ticker)
        row: dict = {"Ticker": ticker, "Date": None}
        if df is None or df.empty:
            rows.append(row)
            continue

        last = df.iloc[-1]
        row["Date"] = df.index[-1]
        # Raw OHLCV columns come from the yfinance price frame (keyed Volume);
        # the output label is renamed "Volume (Vol)" so the derived Vol* columns
        # are self-documenting.
        row.update(
            {col: last[col] for col in ["Open", "High", "Low", "Close", "Volume"]}
        )
        row["Volume (Vol)"] = row.pop("Volume")

        for func in (
            atrpct,
            dmhl,
            chg_open_pct,
            vol_avg_pct,
            vwap_dollar_vol,
            jacoby_range_index,
            jacoby_volume_profile_oscillator,
        ):
            for name, series in func(df).items():
                row[name] = series.iloc[-1] if isinstance(series, pd.Series) else series
        for name, series in rel_vol_plus(df, qqq_df).items():
            row[name] = series.iloc[-1] if isinstance(series, pd.Series) else series

        rows.append(row)

    return pd.DataFrame(rows)[_BASE_COLS + _COMPUTED_ORDER]
