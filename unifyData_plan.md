# Plan: Unified Market Data Source & FanGraphs-Style Watchlist

## Objective

Consolidate `WatchList/` (daily indicators, stocks-focused) and `MarketHighs/`
(horizon/decile analysis, ETFs-focused) into **one source of truth** for
security metadata + price history + derived metrics, and upgrade
`TheChasIX.com` `/watchlist` into a single data table with an
**All / Stocks / ETFs** toggle (FanGraphs-style; named views are phase 2).

## Diagnosis (current duplication)

- Both projects fetch the same yfinance daily OHLCV for the same ~46-ticker
  universe but maintain **two independent caches**:
  - `WatchList/output/raw/*.csv` (18mo)
  - `MarketHighs/data/*.parquet` (10y)
- Two universes drift apart:
  - `WatchList/config/watchlist.yaml` (stocks + ETFs, each entry has
    `symbol`, `sector`, `type: Stock|ETF`, `enabled`, plus `benchmark: QQQ`)
  - `MarketHighs/etfs.yaml`, merged ad-hoc by `MarketHighs/config.yaml`
    via `watchlist_paths`
- Two output contracts get synced into `TheChasIX.com` separately:
  - `data/watchlist/` — 24-column indicator table
    (`output/watchlist.csv` + `output/column_guide.json`, manual copy)
  - `data/markethighs/` — decile leaderboard/detail/breadth/universe
    (via `scripts/sync_markethighs.py` from `MarketHighs/output/`)
- The website serves them as two disjoint tables with no asset-type filter:
  - `/api/watchlist` (indicator table) → `watchlist.html`
  - `/api/stocks` (decile/leaderboard) → `index.html`, `screener.html`

The two projects model the same securities with the same price data; the only
real difference is original focus (stocks vs ETFs). That distinction becomes a
**column**, not a **data store**.

## Decisions (confirmed)

1. **Keep the two repos separate.** The shared module and single source of
   truth live **inside the WatchList repo** (`jacobyglobal/watchlist`, already
   on GitHub), so the plan + shared code + store stay versioned and in sync.
2. **Source of truth = Parquet price cache + committed CSVs** (no DB server;
   matches the zero-build Netlify architecture).
3. **v1 scope = Stocks/ETFs/All toggle + one full table only**; the FanGraphs
   view selector ships in phase 2.
4. **All merged columns in one wide, horizontally-scrollable table** with a
   sticky `Ticker` column (current table pattern).
5. **Homepage and `screener.html` are NOT modified.** They read `/api/stocks`
   and `/api/metrics/*`, which stay backed by `data/markethighs/`. That
   artifact keeps its format; only the pipeline that produces it changes.
6. **MarketHighs stays a local, unversioned consumer** (not a git repo). It
   imports the shared module by absolute path and writes into WatchList's
   store/outputs.

## Target architecture

```
MarketHighs  ──(imports ../WatchList/marketdata)──┐
                                                 WatchList/   = single source of truth (git repo)
TheChasIX.com ◄── sync_to_chasix.py ──────────────┤
                                                 WatchList/
                                                 ├── unifyData_plan.md          this plan (tracked)
                                                 ├── config/watchlist.yaml      canonical universe (tracked)
                                                 ├── marketdata/                shared package (tracked)
                                                 │   ├── config.py              universe → entries/sector_map/type_map/benchmark
                                                 │   ├── store.py               10yr OHLCV fetch + parquet cache
                                                 │   ├── contract.py            merged wide-table schema + column-guide merge
                                                 │   ├── build_combined.py      merge indicator rows + MarketHighs rows
                                                 │   └── sync_to_chasix.py      copy outputs → TheChasIX.com/data/watchlist/
                                                 └── output/                    (gitignored, regenerated)
                                                     ├── prices/*.parquet       10yr price cache
                                                     ├── watchlist.csv          indicators (existing)
                                                     ├── combined_watchlist.csv wide table
                                                     └── combined_column_guide.json
```

Reconciliation:
- MarketHighs needs 10y (deciles), WatchList needs 18mo (indicators) → the
  shared store keeps **10y per ticker**, covering both.
- `output/` is already gitignored in WatchList, so the parquet cache and
  combined CSVs stay local/regenerable; the **committed** artifacts live in
  `TheChasIX.com/data/watchlist/` after sync (as today).
- The unified `data/watchlist/` artifact is consumed only by `/api/watchlist`
  → `watchlist.html`. The existing `data/markethighs/` artifact keeps serving
  the homepage, screener, stock detail, chart, and recommendation endpoints.

## Canonical universe

- `WatchList/config/watchlist.yaml` is already the full union (stocks + all
  ETFs with `type`/`sector`/`enabled`, `benchmark: QQQ`) — no new universe
  file is created. `MarketHighs/etfs.yaml` and the merge logic in
  `MarketHighs/config.yaml` are retired after `watchlist.yaml` is the sole
  universe (MarketHighs points at `../WatchList/config/watchlist.yaml`).
- `marketdata/config.py` exposes `entries` / `sector_map` / `type_map` /
  `benchmark`, replacing:
  - `MarketHighs/config.py` watchlist merge logic
  - `WatchList/data_fetcher.py` config load (`TICKERS`, `TICKER_TYPES`,
    `BENCHMARK`)

## Price store (`marketdata/store.py`)

- One parquet per ticker: `date` index + `Open, High, Low, Close, Volume`
  (raw / unadjusted, matching thinkorswim intent) at `output/prices/*.parquet`.
- TTL-wholesale refresh policy (never append rows — adjusted prices are
  retroactively restated; reuse only if whole cache is fresh, else replace).
- **Standardization decision:** base *all* close-based metrics (WatchList
  indicators **and** MarketHighs horizon/decile analysis) on the **raw close**
  from the shared store. MarketHighs previously used `Adj Close`; it is rerun
  against the shared store so both analyses are consistent.
- Delete `WatchList/output/raw/` and `MarketHighs/data/` legacy caches once
  both repos read the shared store.

## Merged wide table (one row per ticker)

Base + metadata:
`Ticker, Type, Sector, Date, Open, High, Low, Close, Volume (Vol)`

WatchList computed/intermediate (17 columns):
`Typical Price (TP)`, `True Range (TR)`, `Average True Range (ATR)`,
`Normalized ATR (NATR)`, `52-Week High`, `52-Week Low`,
`52-Week Range Position`, `TD Range Rank`, `Session Return %`,
`21-Period EMA Volume`, `Relative Volume (RVOL EMA)`,
`21-Period Median Volume`, `Relative Volume (RVOL Median)`,
`Idiosyncratic RVOL`, `Notional Turnover ($M)`,
`Jacoby Range Index`, `Jacoby Volume Profile Oscillator`

MarketHighs horizon/decile (4 durations × 4 columns = 16):
per `X` in {`4w`, `12w`, `26w`, `52w`}:
`off_high_pct_X`, `off_low_pct_X`, `high_decile_X`, `low_decile_X`

MarketHighs summary (2):
`composite_score`, `rank`

Notes:
- Total ≈ 45 columns.
- Decile polarity standardized to **strength** (10 = strongest) — reuse the
  existing `11 - off_low_decile` inversion so `high_decile_X` and
  `low_decile_X` share polarity.
- `column_guide.json` → **schema v3**: every column tagged with
  `view` (`base|volatility|horizon|jacoby|...`) so phase-2 views are
  declarative config, not per-view code.

## Phase plan

### Phase 0 — Shared module (inside WatchList repo)
- Scaffold `WatchList/marketdata/`: `config.py` (universe parsing),
  `store.py` (10y yfinance + parquet cache), `contract.py` (combined schema +
  column-guide merge).
- Point `WatchList/data_fetcher.py` at `marketdata` (it becomes a thin client).
- Point `MarketHighs` at the shared module by absolute path:
  - `config.yaml` → `watchlist_paths: [../WatchList/config/watchlist.yaml]`
    only (drop `etfs.yaml` merge); `etfs.yaml` retired.
  - `data_loader.py` → read from `marketdata.store` (bypass its own cache).
- Delete `WatchList/output/raw/` and `MarketHighs/data/` legacy caches.
- Rerun both pipelines against the shared store; confirm outputs match
  previous values on the same as-of date (raw-close re-baseline noted above).

### Phase 1 — Merger + sync
- `WatchList/marketdata/build_combined.py`: joins WatchList indicator rows +
  MarketHighs `leaderboard`/`detail` rows by ticker →
  `output/combined_watchlist.csv` + `output/combined_column_guide.json`
  (gitignored).
- `WatchList/marketdata/sync_to_chasix.py`: copies those files into
  `TheChasIX.com/data/watchlist/` (replacing the manual per-output copies):
  - `watchlist.csv` (combined wide table)
  - `column_guide.json` (schema v3 with `view` tags)
  - README notes updated
- Keep `data/markethighs/` syncing unchanged; the homepage/screener/stock
  endpoints are untouched.

### Phase 2 — TheChasIX backend (`src/api/watchlist.py`)
- Extend `GET /api/watchlist`:
  - `type=stocks|etfs|all` (default `all`) — filter by `Type` column
  - `q=` optional search (ticker/sector)
  - `limit`, `offset` (existing)
  - `view=` accepted but unused in v1 (reserved for phase 4)
- Loader reads the combined CSV + schema-v3 guide; `as_of` = max `Date` across
  rows.
- `/api/watchlist/guide` returns the v3 guide (including `view` tags).

### Phase 3 — TheChasIX frontend (`watchlist.html` + `watchlist.js`)
- Add segmented **All / Stocks / ETFs** toggle control.
  - Default = All.
  - Client-side filter on the `Type` column of already-fetched rows (data is
    small); the API `type` param is supported for future scale.
- Keep existing: sortable headers, ticker search filter, reset, pagination
  (10/25/50/All), column-guide accordion + hover `ⓘ`, sticky Ticker column,
  right-edge scroll fade, horizontal scroll across all columns.
- **Mandatory per AGENTS.md:**
  - Run architecture review gate first:
    `.venv/bin/python .opencode/skill/arch-review/run.py "Unified Watchlist Views"`
  - Rebuild the committed static site:
    `.venv/bin/python -m src.build_frontend`, commit updated `dist/`.

### Phase 4 — FanGraphs-style views (future, not in v1)
- Navigation of pre-set column subsets driven by the `view` tag already
  present in the schema-v3 column guide (e.g. Overview / Volatility & Volume /
  Horizon & Deciles / Jacoby / Custom).
- URL carries `?view=` so views are shareable/bookmarkable.

## Refresh workflow (post-phase-1)

```bash
# 1. Fetch/refresh shared prices (hits marketdata.store), then run both analyses:
cd ~/Documents/GeminiProjects/WatchList      # python3 main.py (indicators; fetches store)
cd ~/Documents/GeminiProjects/MarketHighs    # python3 main.py (horizon/deciles, reads shared store)
cd ~/Documents/GeminiProjects/WatchList      # python3 -m marketdata.build_combined
                                             # python3 -m marketdata.sync_to_chasix

# 2. Commit + deploy TheChasIX (Render picks up new data/watchlist files).
```

## Versioning / git layout (confirmed)

- `WatchList/` is the canonical repo for this work: `unifyData_plan.md`
  (tracked — note `.gitignore` does NOT exclude this name),
  `marketdata/` (tracked), `config/watchlist.yaml` (tracked, canonical
  universe), `output/` (gitignored, regenerated).
- `MarketHighs/` intentionally remains local-only (not a git repo); it reads
  WatchList by absolute path, mirroring the existing `config.yaml` precedent.
- `TheChasIX.com/` holds the committed, deployable artifacts synced by
  `sync_to_chasix.py`.

## Verification

- Pipeline: `combined_watchlist.csv` row count == universe count; column set
  matches the merged spec; spot-check one ticker's row against both source
  outputs.
- API: `/api/watchlist` (all, no filter), `/api/watchlist?type=etf`,
  `/api/watchlist?type=stocks` — counts sum to full set; guide returns v3.
- Frontend: `python3 -m http.server 8000 -d dist` →
  `http://localhost:8000/watchlist.html` — toggle filters the table;
  sort/search/pagination/guide continue to work.
- Regression: homepage and `/screener.html` render identical data to before
  (no code or data-format change in `data/markethighs/`).

## Out of scope / notes

- No changes to `index.html`, `screener.html`, `src/api/stocks.py`,
  `src/api/metrics.py`, or `data/markethighs/` formats.
- No intraday data; daily OHLCV only (existing behavior).
- `marketdata` is a **pipeline-time only** dependency inside the WatchList
  repo; it is never imported by the TheChasIX frontend build or Render runtime
  (data arrives as committed CSV/JSON), preserving the zero-build Netlify
  constraint.
- The `data/markethighs/` artifact may be re-pointed at the shared store later
  once `/api/stocks` and friends are migrated; not required for this plan.