"""Assemble the final watchlist table from per-ticker indicator results."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from data_fetcher import download
from indicators import atrpct, chg_open_pct, dmhl, rel_vol_plus, vol_avg_pct, vwap_dollar_vol

_BASE_COLS = ["Ticker", "Date", "Open", "High", "Low", "Close", "Volume (Vol)"]

_COMPUTED_ORDER = [
    "OHLC / 4",
    "True Range", "Average True Range (ATR)", "ATR as % Price",
    "52-Wk High", "52-Wk Low", "52-Wk Range", "DeMark High Low Rank",
    "Close vs Open %",
    "Vol EMA 21", "Vol % of Vol EMA 21", "Vol Median 21", "Vol % of Vol Median 21",
    "Relative Vol vs QQQ Market",
    "Notional Value $M",
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
        "name": "OHLC / 4",
        "kind": "intermediate",
        "formula": "(Open + High + Low + Close) / 4",
        "meaning": "A per-bar typical-price proxy standing in for intraday VWAP throughout the watchlist (used by ATR as % Price, DeMark High Low Rank, and Notional Value $M).",
        "recompute": "",
    },
    {
        "name": "True Range",
        "kind": "intermediate",
        "formula": "Max(High - Low, |High - OHLC / 4|, |OHLC / 4 - Low|)",
        "meaning": "The daily true range of the bar, measured from the OHLC / 4 proxy price instead of the close. It is the input series to Average True Range (ATR).",
        "recompute": "",
    },
    {
        "name": "Average True Range (ATR)",
        "kind": "intermediate",
        "formula": "EMA21(True Range)",
        "meaning": "The 21-day average true range anchored at the OHLC / 4 proxy price - a volatility measure in dollar terms.",
        "recompute": "",
    },
    {
        "name": "ATR as % Price",
        "kind": "computed",
        "formula": "((OHLC / 4 + Average True Range (ATR)) / OHLC / 4) * 100",
        "meaning": "Average True Range (ATR) expressed as a percentage of price. ATR as % Price - 100 is the ATR as a % of price; values well above 100 indicate an expanded daily range relative to price.",
        "recompute": "(OHLC / 4 + Average True Range (ATR)) / OHLC / 4 * 100",
    },
    {
        "name": "52-Wk High",
        "kind": "intermediate",
        "formula": "Highest(High, 252)",
        "meaning": "The 52-week trading range boundary - the upper DeMark High/Low reference level.",
        "recompute": "",
    },
    {
        "name": "52-Wk Low",
        "kind": "intermediate",
        "formula": "Lowest(Low, 252)",
        "meaning": "The 52-week trading range boundary - the lower DeMark High/Low reference level.",
        "recompute": "",
    },
    {
        "name": "52-Wk Range",
        "kind": "intermediate",
        "formula": "52-Wk High - 52-Wk Low",
        "meaning": "The width of the 52-week high-low range, in dollars.",
        "recompute": "",
    },
    {
        "name": "DeMark High Low Rank",
        "kind": "computed",
        "formula": "((OHLC / 4 - 52-Wk Low) / 52-Wk Range) * 100 - 50   (rounded to 1 decimal)",
        "meaning": "Where the OHLC / 4 price sits inside the 52-week high-low range, on a 0-centered scale of [-50, +50]. Above zero = upper half of the yearly range; below zero = lower half. The sentinel 65.0 is used when the range is zero (rare).",
        "recompute": "(OHLC / 4 - 52-Wk Low) / 52-Wk Range * 100 - 50",
    },
    {
        "name": "Close vs Open %",
        "kind": "computed",
        "formula": "log(Close / Open) * 100",
        "meaning": "Continuously-compounded percent change from the open to the close. Positive = closed above the open; negative = closed below.",
        "recompute": "",
    },
    {
        "name": "Vol EMA 21",
        "kind": "intermediate",
        "formula": "EMA21(Volume)",
        "meaning": "The 21-day exponential moving average of volume (Vol). The baseline for Vol % of Vol EMA 21.",
        "recompute": "",
    },
    {
        "name": "Vol % of Vol EMA 21",
        "kind": "computed",
        "formula": "Volume / Vol EMA 21 * 100   (rounded to 1 decimal)",
        "meaning": "Current volume relative to its 21-day exponential average. 100 = average activity; >130 = heavy volume; <80 = light volume.",
        "recompute": "Volume / Vol EMA 21 * 100",
    },
    {
        "name": "Vol Median 21",
        "kind": "intermediate",
        "formula": "Median(Volume, 21)",
        "meaning": "The 21-day median volume (Vol) - the baseline for the ticker side of Relative Vol vs QQQ Market.",
        "recompute": "",
    },
    {
        "name": "Vol % of Vol Median 21",
        "kind": "computed",
        "formula": "Volume / Vol Median 21 * 100",
        "meaning": "The ticker's volume (Vol) as a percentage of its own 21-day median volume. 100 = median activity.",
        "recompute": "Volume / Vol Median 21 * 100",
    },
    {
        "name": "Relative Vol vs QQQ Market",
        "kind": "computed",
        "formula": "log(Vol % of Vol Median 21 / qqqVolPct) * 100   where qqqVolPct = QQQ row's Vol % of Vol Median 21",
        "meaning": "The ticker's volume (Vol) normalized against the market's (QQQ's) relative volume, log-scaled. 0 = the stock's volume activity matches the market's; positive = trading on relatively higher volume than the market; negative = lighter.",
        "recompute": "log(Vol % of Vol Median 21 / QQQ's Vol % of Vol Median 21) * 100, using the QQQ row for the denominator",
    },
    {
        "name": "Notional Value $M",
        "kind": "computed",
        "formula": "round(Volume * OHLC / 4 / 1_000_000)",
        "meaning": "Dollar value traded for the day in millions (volume weighted at the OHLC / 4 proxy price). A liquidity/participation measure: large, liquid names show high values. Holds the raw numeric value for easy sorting.",
        "recompute": "Volume * OHLC / 4 / 1_000_000, rounded",
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
            "version": 1,
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

        for func in (atrpct, dmhl, chg_open_pct, vol_avg_pct, vwap_dollar_vol):
            for name, series in func(df).items():
                row[name] = series.iloc[-1] if isinstance(series, pd.Series) else series
        for name, series in rel_vol_plus(df, qqq_df).items():
            row[name] = series.iloc[-1] if isinstance(series, pd.Series) else series

        rows.append(row)

    return pd.DataFrame(rows)[_BASE_COLS + _COMPUTED_ORDER]
