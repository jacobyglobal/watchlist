"""Canonical ticker universe - the single source of truth.

Reads WatchList/config/watchlist.yaml, the only universe file. Exposes:

- MarketHighs-flavored metadata: ``entries`` (benchmark first, labelled
  "Benchmark"), ``tickers`` (deduped, declaration order), ``sector_map``
  (first occurrence wins).
- WatchList-flavored metadata: ``watchlist_tickers``, ``watchlist_sector_map``
  and ``type_map`` (symbol -> Stock|ETF) read from the ``tickers`` list only,
  so QQQ keeps its ETF type and sector in the watchlist table.

Both downstream projects should gate their symbol lists off this module
(or MarketHighs off ``store``/``parse_watchlist``) instead of re-reading YAML.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
CONFIG_PATH = REPO_ROOT / "config" / "watchlist.yaml"

BENCHMARK_SECTOR = "Benchmark"
DEFAULT_TYPE = "Stock"


@dataclass(frozen=True)
class Universe:
    """Parsed universe for one watchlist yaml."""

    benchmark: str | None
    # (symbol, sector) pairs in declaration order; benchmark first when set.
    entries: tuple[tuple[str, str], ...]
    # Ticker-list entries only (WatchList labels - no forced "Benchmark" sector).
    watchlist_entries: tuple[tuple[str, str], ...]
    # symbol -> Stock | ETF, from the tickers list only.
    type_map: dict[str, str]
    source: Path

    @property
    def tickers(self) -> list[str]:
        """All symbols (benchmark + tickers), deduped, declaration order."""
        seen: set[str] = set()
        ordered: list[str] = []
        for symbol, _ in self.entries:
            if symbol not in seen:
                seen.add(symbol)
                ordered.append(symbol)
        return ordered

    @property
    def sector_map(self) -> dict[str, str]:
        """symbol -> sector, first occurrence wins (MarketHighs semantics)."""
        mapping: dict[str, str] = {}
        for symbol, sector in self.entries:
            mapping.setdefault(symbol, sector)
        return mapping

    @property
    def watchlist_tickers(self) -> list[str]:
        """Enabled ticker symbols from the tickers list (WatchList semantics)."""
        seen: set[str] = set()
        ordered: list[str] = []
        for symbol, _ in self.watchlist_entries:
            if symbol not in seen:
                seen.add(symbol)
                ordered.append(symbol)
        return ordered

    @property
    def watchlist_sector_map(self) -> dict[str, str]:
        """symbol -> sector from the tickers list only."""
        mapping: dict[str, str] = {}
        for symbol, sector in self.watchlist_entries:
            mapping.setdefault(symbol, sector)
        return mapping


def parse_watchlist(path: Path | str) -> Universe:
    """Parse one watchlist yaml into a Universe (used by both projects).

    Semantics mirror the historic MarketHighs parser: benchmark first with
    sector "Benchmark"; disabled / empty / non-dict entries skipped; symbols
    upper-cased; missing sector falls back to the symbol.
    """
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    benchmark_raw = str(raw.get("benchmark") or "").strip().upper()
    benchmark: str | None = benchmark_raw or None

    entries: list[tuple[str, str]] = []
    if benchmark:
        entries.append((benchmark, BENCHMARK_SECTOR))

    watchlist_entries: list[tuple[str, str]] = []
    type_map: dict[str, str] = {}
    for item in raw.get("tickers") or []:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        if not bool(item.get("enabled", True)):
            continue
        sector = str(item.get("sector") or "").strip() or symbol
        entries.append((symbol, sector))
        watchlist_entries.append((symbol, sector))
        type_map.setdefault(
            symbol, str(item.get("type") or DEFAULT_TYPE).strip() or DEFAULT_TYPE
        )

    return Universe(
        benchmark=benchmark,
        entries=tuple(entries),
        watchlist_entries=tuple(watchlist_entries),
        type_map=type_map,
        source=path,
    )


def load_universe(path: Path | str | None = None) -> Universe:
    """Load the canonical universe (default: WatchList/config/watchlist.yaml)."""
    return parse_watchlist(path or CONFIG_PATH)