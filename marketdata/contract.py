"""Merged wide-table schema and schema-v3 column guide.

Defines the *combined* watchlist contract that phase 1's ``build_combined.py``
will emit: base + metadata columns, WatchList indicators, MarketHighs
horizon/decile columns (multiple durations), and MarketHighs summary columns -
all as ONE row per ticker.

The column guide is **schema v3**: every column is tagged with a ``view``
(Base / Volatility / Volume / Horizon & Deciles / Jacoby / Custom) so phase-2+
view presets become declarative config rather than per-view code. Decile
polarity is standardized to **strength** (10 = strongest, nearest the window
high) by inverting the stored ``off_low_decile`` (``11 - off_low_decile``).

This module is pure spec/meta data - it does not import the analysis pipeline,
so `MarketHighs` can import the shared package without dragging in
``data_fetcher``.
"""

from __future__ import annotations

import json
from pathlib import Path

DURATIONS = ["4w", "12w", "26w", "52w"]

HORIZON_FIELDS = ["off_high_pct", "off_low_pct", "high_decile", "low_decile"]

# One view tag per logical grouping; free-form keys are allowed beyond these.
VIEWS: dict[str, str] = {
    "base": "Identity, latest-bar price, and sector - the table anchor.",
    "volatility": "Volatility measures derived from the bar's price action.",
    "volume": "Volume and liquidity measures.",
    "horizon": "Multi-horizon distance-from-high/low stats and deciles.",
    "jacoby": "Jacoby indicators and their supporting series.",
}

# order of columns in the combined table. Base = the existing watchlist base
# plus a `Sector` column (Type, Sector come from config/watchlist.yaml).
BASE_COLS = [
    "Ticker",
    "Type",
    "Sector",
    "Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume (Vol)",
]

WATCHLIST_COMPUTED = [
    "Typical Price (TP)",
    "True Range (TR)",
    "Average True Range (ATR)",
    "Normalized ATR (NATR)",
    "52-Week High",
    "52-Week Low",
    "52-Week Range Position",
    "TD Range Rank",
    "Session Return %",
    "21-Period EMA Volume",
    "Relative Volume (RVOL EMA)",
    "21-Period Median Volume",
    "Relative Volume (RVOL Median)",
    "Idiosyncratic RVOL",
    "Notional Turnover ($M)",
    "Jacoby Range Index",
    "Jacoby Volume Profile Oscillator",
]

MH_SUMMARY = ["composite_score", "rank"]


def horizon_columns() -> list[str]:
    """All MarketHighs horizon/decile column names, per duration."""
    return [
        f"{field}_{dur}" for dur in DURATIONS for field in HORIZON_FIELDS
    ]


def merged_column_order() -> list[str]:
    """Full combined table column order (one row per ticker)."""
    return BASE_COLS + WATCHLIST_COMPUTED + horizon_columns() + MH_SUMMARY


# Column name -> view tag for the WatchList side of the guide.
_VIEW_TAGS: dict[str, str] = {
    "Ticker": "base",
    "Type": "base",
    "Sector": "base",
    "Date": "base",
    "Open": "base",
    "High": "base",
    "Low": "base",
    "Close": "base",
    "Volume (Vol)": "volume",
    "Typical Price (TP)": "jacoby",
    "True Range (TR)": "volatility",
    "Average True Range (ATR)": "volatility",
    "Normalized ATR (NATR)": "volatility",
    "52-Week High": "horizon",
    "52-Week Low": "horizon",
    "52-Week Range Position": "horizon",
    "TD Range Rank": "horizon",
    "Session Return %": "volatility",
    "21-Period EMA Volume": "volume",
    "Relative Volume (RVOL EMA)": "volume",
    "21-Period Median Volume": "volume",
    "Relative Volume (RVOL Median)": "volume",
    "Idiosyncratic RVOL": "volume",
    "Notional Turnover ($M)": "volume",
    "Jacoby Range Index": "jacoby",
    "Jacoby Volume Profile Oscillator": "jacoby",
}

_SECTOR_GUIDE = {
    "name": "Sector",
    "kind": "base",
    "formula": "",
    "meaning": "Sector/label for the ticker from config/watchlist.yaml (MarketHighs groups by this). The benchmark renders as 'Benchmark'.",
    "recompute": "",
    "view": "base",
}

_MH_GUIDE_TEMPLATE = {
    "off_high_pct": {
        "kind": "computed",
        "formula": "(Close / HIGHEST(High, N) - 1) * 100   (<= 0)",
        "meaning": "How far the latest close sits below the highest High over the N-day window. 0 = close equals the window peak high; negative = below it.",
    },
    "off_low_pct": {
        "kind": "computed",
        "formula": "(Close / LOWEST(Low, N) - 1) * 100   (>= 0)",
        "meaning": "How far the latest close sits above the lowest Low over the N-day window. 0 = close equals the window floor low; larger = further above it.",
    },
    "high_decile": {
        "kind": "computed",
        "formula": "Decile(1-10) of the latest off_high_pct within its own 10y history   (10 = strongest, nearest the window high)",
        "meaning": "Where today's distance-from-high ranks in the ticker's 10-year history. 10 = at/near the window high (strongest); 1 = deepest below it. Polarity is strength, shared with the low decile.",
    },
    "low_decile": {
        "kind": "computed",
        "formula": "11 - off_low_decile   (MarketHighs raw off_low_decile is a weakness measure, 10 = nearest the low)",
        "meaning": "Strength-scaled low decile: where today's distance-from-low ranks in the ticker's 10-year history, inverted so 10 = nearest the low AND therefore strongest. Shares polarity with the high decile.",
    },
}

_MH_SUMMARY_GUIDE = {
    "composite_score": {
        "kind": "computed",
        "formula": "Weighted average of high_decile_X across 4w/12w/26w/52w, weights 1/2/3/4   (rounded to 2 decimals)",
        "meaning": "The MarketHighs composite: how strong the ticker's position is across all durations on the strength scale (10 = consistently at/above its own multi-year extremes).",
    },
    "rank": {
        "kind": "computed",
        "formula": "1-based rank by composite_score, descending",
        "meaning": "Cross-sectional leaderboard rank of the ticker across the full universe.",
    },
}


def _entry(name: str, template: dict, dur: str | None) -> dict:
    entry = {"name": name, "view": "horizon", **template}
    if dur is not None:
        entry.update(
            formula=entry["formula"].replace("N", dur),
            meaning=entry["meaning"],
        )
    return entry


def _markethighs_guide() -> list[dict]:
    entries: list[dict] = []
    for dur in DURATIONS:
        for field in HORIZON_FIELDS:
            entries.append(_entry(f"{field}_{dur}", _MH_GUIDE_TEMPLATE[field], dur))
    for field in MH_SUMMARY:
        entries.append(
            {"name": field, "view": "horizon", **{**_MH_SUMMARY_GUIDE[field]}}
        )
    return entries


def build_combined_guide(base_guide: list[dict]) -> dict:
    """Lift a schema-v2 watchlist guide to v3 and merge the MarketHighs columns.

    `base_guide` is the existing per-column guide from ``columns.COLUMN_GUIDE``
    (list of dicts with name/kind/formula/meaning/recompute); each entry keeps
    its fields and gains a ``view`` tag. MarketHighs + Sector entries are
    appended so the result matches ``merged_column_order()`` exactly.
    """
    tagged = {
        entry["name"]: {**entry, "view": _VIEW_TAGS.get(entry["name"], "base")}
        for entry in base_guide
    }
    tagged["Sector"] = _SECTOR_GUIDE
    for entry in _markethighs_guide():
        tagged[entry["name"]] = entry
    v3 = [tagged[name] for name in merged_column_order()]

    return {
        "_meta": {
            "schema": "watchlist-column-guide",
            "version": 3,
            "column_count": len(v3),
            "views": VIEWS,
        },
        "columns": v3,
    }


def write_combined_guide(path: str | Path, base_guide: list[dict]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_combined_guide(base_guide), indent=2) + "\n", encoding="utf-8")
    return path