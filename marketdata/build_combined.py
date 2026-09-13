"""Merge WatchList indicator rows + MarketHighs horizon/decile rows.

Reads the two projects' committed outputs and joins them into ONE wide table
(one row per ticker, in canonical universe order) plus the schema-v3 column
guide:

- `WatchList/output/watchlist.csv`            -> base OHLCV + 17 indicators
- `MarketHighs/output/detail.csv` / `leaderboard.csv` -> horizon/decile columns

Decile polarity is standardized to **strength** (10 = strongest): the MarketHighs
raw `off_low_decile` is a weakness measure (10 = nearest the low), so the merged
table stores `11 - off_low_decile` (see marketdata/contract.py).

Outputs: `output/combined_watchlist.csv` + `output/combined_column_guide.json`
(one row per ticker; the contract for TheChasIX `/api/watchlist` from phase 2).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from columns import COLUMN_GUIDE
from marketdata import config as md_config
from marketdata import contract

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
MH_OUT = ROOT.parent / "MarketHighs" / "output"

_BASE_COLS = ["Ticker", "Type", "Sector", "Date", "Open", "High", "Low", "Close", "Volume (Vol)"]


def _lb_by_ticker(leaderboard: pd.DataFrame) -> dict[str, pd.Series]:
    return {str(r["ticker"]): r for _, r in leaderboard.iterrows()}


def _detail_by_ticker_duration(detail: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    out: dict[tuple[str, str], pd.Series] = {}
    for _, r in detail.iterrows():
        out[(str(r["ticker"]), str(r["duration"]))] = r
    return out


def build_combined(
    watchlist_csv: Path,
    detail_csv: Path,
    leaderboard_csv: Path,
    tickers: list[str],
    sector_map: dict[str, str],
) -> pd.DataFrame:
    """Join indicator + horizon/decile rows into the merged wide table."""
    wl = pd.read_csv(watchlist_csv)
    wl_by_ticker = {str(r["Ticker"]): r for _, r in wl.iterrows()}
    detail = pd.read_csv(detail_csv)
    leaderboard = pd.read_csv(leaderboard_csv)
    lb_by_ticker = _lb_by_ticker(leaderboard)
    detail_by = _detail_by_ticker_duration(detail)

    rows: list[dict] = []
    for ticker in tickers:
        w = wl_by_ticker.get(ticker)
        lb = lb_by_ticker.get(ticker)
        row: dict = {
            col: (w[col] if w is not None else pd.NA)
            for col in _BASE_COLS
            if col not in ("Sector",)
        }
        row["Sector"] = sector_map.get(ticker, ticker)
        for col in contract.WATCHLIST_COMPUTED:
            row[col] = w[col] if w is not None else pd.NA
        for dur in contract.DURATIONS:
            if lb is not None:
                row[f"off_high_pct_{dur}"] = lb[f"off_high_pct_{dur}"]
                row[f"off_low_pct_{dur}"] = lb[f"off_low_pct_{dur}"]
                row[f"high_decile_{dur}"] = lb[f"high_decile_{dur}"]
            else:
                row[f"off_high_pct_{dur}"] = pd.NA
                row[f"off_low_pct_{dur}"] = pd.NA
                row[f"high_decile_{dur}"] = pd.NA
            d = detail_by.get((ticker, dur))
            raw_low = d["off_low_decile"] if d is not None else pd.NA
            row[f"low_decile_{dur}"] = (
                11 - raw_low if pd.notna(raw_low) else pd.NA
            )
        row["composite_score"] = lb["composite_score"] if lb is not None else pd.NA
        row["rank"] = lb["rank"] if lb is not None else pd.NA
        rows.append(row)

    return pd.DataFrame(rows)[contract.merged_column_order()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--watchlist", type=Path, default=OUT / "watchlist.csv")
    parser.add_argument("--detail", type=Path, default=MH_OUT / "detail.csv")
    parser.add_argument("--leaderboard", type=Path, default=MH_OUT / "leaderboard.csv")
    parser.add_argument("--out", type=Path, default=OUT / "combined_watchlist.csv")
    parser.add_argument("--guide-out", type=Path, default=OUT / "combined_column_guide.json")
    args = parser.parse_args()

    universe = md_config.load_universe()
    combined = build_combined(
        args.watchlist,
        args.detail,
        args.leaderboard,
        universe.tickers,
        universe.sector_map,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.out, index=False)

    guide = contract.build_combined_guide(COLUMN_GUIDE)
    contract.write_combined_guide(args.guide_out, COLUMN_GUIDE)

    print(f"wrote combined_watchlist_csv: {args.out} ({len(combined)} rows x {len(combined.columns)} cols)")
    print(f"wrote combined_column_guide_json: {args.guide_out} ({guide['_meta']['column_count']} cols, schema v{guide['_meta']['version']})")


if __name__ == "__main__":
    main()