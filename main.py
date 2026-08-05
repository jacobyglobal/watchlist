"""Entrypoint: fetch data, compute indicators, export the watchlist."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from columns import build_watchlist, write_column_guide
from data_fetcher import BENCHMARK, TICKERS

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "output" / "watchlist.csv"
DEFAULT_GUIDE_OUT = ROOT / "output" / "column_guide.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a daily OHLCV watchlist from yfinance (ThinkScript ports)."
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Re-download data, ignoring cache"
    )
    parser.add_argument(
        "--out", type=str, default=str(DEFAULT_OUT), help="Output CSV path"
    )
    parser.add_argument(
        "--guide-out", type=str, default=str(DEFAULT_GUIDE_OUT), help="Output column guide JSON path"
    )
    args = parser.parse_args()

    watch = build_watchlist(TICKERS, BENCHMARK, refresh=args.refresh)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    watch.to_csv(out_path, index=False)

    guide_path = write_column_guide(args.guide_out)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(watch.to_string(index=False))
    print(f"\nSaved: {out_path}")
    print(f"Saved: {guide_path}")


if __name__ == "__main__":
    main()
