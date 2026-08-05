# WatchList Column Logic

This document explains every column in the watchlist. For each column we show
the **original ThinkScript** (where one exists), the **daily-data mapping**
used in this project, and the **trader meaning**.

The watchlist includes **every intermediate value** used in any calculation,
so a viewer can recompute any number by hand from the formulas below and the
base OHLCV columns.

## Conventions

- Data: 18 months of daily OHLCV from `yfinance` (raw/unadjusted prices).
- `OHLC / 4 = (Open + High + Low + Close) / 4` per bar — the VWAP proxy used by
  the ThinkScripts. Daily data has no intraday VWAP, so OHLC / 4 is the
  standard daily substitute.
- Lookback: standardized to **21 bars** for all window-based variables,
  except DMHL which uses the **52-week (252-trading-day)** high/low per the
  DeMark High Low intent.
- Logs use the natural logarithm (ThinkScript `log()` is natural log).

---

## Base columns

| Column | Meaning |
|--------|---------|
| Ticker | Symbol from the watchlist. |
| Date | Trading date of the latest bar used for the row. |
| Open / High / Low / Close | Raw daily OHLC from yfinance. |
| Volume (Vol) | Raw daily share volume (`Vol` = Volume; basis for all `Vol …` columns). |

---

## OHLC / 4 (VWAP proxy)

**Formula:**

```
OHLC / 4 = (Open + High + Low + Close) / 4
```

**Trader meaning:** A per-bar typical-price proxy. It stands in for intraday
VWAP throughout the watchlist (used by ATR as % Price, DeMark High Low Rank,
and Notional Value $M).

---

## True Range

**Formula** (ThinkScript `TrueRange(high, price, low)`):

```
True Range = Max(High - Low, |High - OHLC / 4|, |OHLC / 4 - Low|)
```

**Trader meaning:** The daily true range of the bar, measured from the OHLC / 4
proxy price instead of the close. It is the input series to Average True Range (ATR).

---

## Average True Range (ATR)

**Original ThinkScript** (`scripts/CJ_ATRPctVWAPWATCHLIST.ts`):

```
def ATR = MovingAverage(AverageType.EXPONENTIAL, TrueRange(high, vwap, low), 21);
```

**Daily mapping:** `Average True Range (ATR) = EMA21(True Range)` (exponential
smoothing, span 21, ThinkOrSwim `ExpAverage` semantics).

**Trader meaning:** The 21-day average true range anchored at the OHLC / 4
proxy price — a volatility measure in dollar terms.

---

## ATR as % Price

**Original ThinkScript** (`scripts/CJ_ATRPctVWAPWATCHLIST.ts`):

```
plot ATRPct = if vwap > 0 then ((vwap + ATR) / vwap) * 100 else baseValue;
```

**Daily mapping:**

```
ATR as % Price = ((OHLC / 4 + Average True Range (ATR)) / OHLC / 4) * 100
```

**Trader meaning:** The Average True Range (ATR) expressed as a percentage of
price. `ATR as % Price - 100` is the ATR as a % of price; values well above
100 indicate an expanded daily range relative to price.

**Recompute from the watchlist:** `(OHLC / 4 + Average True Range (ATR)) / OHLC / 4 * 100`
using the `OHLC / 4` and `Average True Range (ATR)` columns.

---

## 52-Wk High / 52-Wk Low

**Formula** (ThinkScript `Highest(high, 252)` / `Lowest(low, 252)`):

```
52-Wk High = max(High) over the last 252 bars (52 weeks)
52-Wk Low  = min(Low)  over the last 252 bars (52 weeks)
```

**Trader meaning:** The 52-week trading range boundary — the DeMark High/Low
reference levels. The denominator of DeMark High Low Rank.

---

## 52-Wk Range

**Formula:**

```
52-Wk Range = 52-Wk High - 52-Wk Low
```

**Trader meaning:** The width of the 52-week high-low range, in dollars.

---

## DeMark High Low Rank

**Original ThinkScript** (`scripts/CJ_DMHLWATCHLIST.ts`):

```
input lookbackLength = 252;
input offset = 50.0;
plot DMHL = if (maxHigh - minLow) == 0 then dmhlNaN
            else Round((vwap - minLow) / (maxHigh - minLow) * 100, 1) - offset;
```

**Daily mapping:**

```
DeMark High Low Rank = ((OHLC / 4 - 52-Wk Low) / 52-Wk Range) * 100 - 50   (rounded to 1 decimal)
```

**Trader meaning:** Where the OHLC / 4 price sits inside the **52-week** high-low
range, on a 0-centered scale of [-50, +50] (DeMark High Low). Above zero =
upper half of the yearly range; below zero = lower half. The original script
colors `>= 44` cyan (near the yearly high) and `<= -34` yellow (near the
yearly low). The sentinel 65.0 is used when the range is zero (rare).

**Recompute from the watchlist:** `(OHLC / 4 - 52-Wk Low) / 52-Wk Range * 100 - 50`.

---

## Close vs Open %

**Original ThinkScript** (`scripts/CJ_PctChOpWATCHLIST.ts`):

```
plot chgOpenPct = log(close / open) * 100;
```

**Daily mapping:** `Close vs Open % = log(Close / Open) * 100`

**Trader meaning:** Continuously-compounded percent change from the open to
the close. Positive = closed above the open; negative = closed below.

---

## Vol EMA 21

**Formula** (ThinkScript `ExpAverage(volume, 21)`):

```
Vol EMA 21 = EMA21(Volume)
```

**Trader meaning:** The 21-day exponential moving average of volume (`Vol`).
The baseline for Vol % of Vol EMA 21. (`Vol` = raw `Volume`.)

---

## Vol % of Vol EMA 21

**Original ThinkScript** (`scripts/CJ_VolAvgPlusWATCHLIST.ts`):

```
input length = 13;   # standardized to 21
plot VolAvgPct = Round(ratio, 1);
```

**Daily mapping:**

```
Vol % of Vol EMA 21 = Volume / Vol EMA 21 * 100   (rounded to 1 decimal)
```

**Trader meaning:** Current volume relative to its 21-day exponential average.
100 = average activity; >130 = heavy volume; <80 = light volume. This column
replaces `VolMaxRatio` (intraday-only) — under the standardized 21-day
lookback the daily proxies are mathematically identical.

**Recompute from the watchlist:** `Volume / Vol EMA 21 * 100`.

---

## Vol Median 21

**Formula** (ThinkScript `Median(volume, 21)`):

```
Vol Median 21 = median(Volume) over the last 21 bars
```

**Trader meaning:** The 21-day median volume (`Vol`) — the baseline for the
ticker side of Relative Vol vs QQQ Market.

---

## Vol % of Vol Median 21

**Formula** (ThinkScript `(volume / Median(volume, len)) * 100`):

```
Vol % of Vol Median 21 = Volume / Vol Median 21 * 100
```

**Trader meaning:** The ticker's volume (`Vol`) as a percentage of its own
21-day median volume. 100 = median activity.

**Recompute from the watchlist:** `Volume / Vol Median 21 * 100`.

---

## Benchmark values (no dedicated columns)

QQQ's `QQQ ETF Vol`, `QQQ Vol Median 21`, and `QQQ Vol % of QQQ Vol Median 21`
were removed as redundant now that QQQ is a watchlist row. The benchmark side
of `Relative Vol vs QQQ Market` uses QQQ's own columns:

| Benchmark value (former column) | Now read from QQQ's row |
|---------------------------------|--------------------------|
| QQQ ETF Vol                     | `Volume (Vol)`           |
| QQQ Vol Median 21               | `Vol Median 21`          |
| QQQ Vol % of QQQ Vol Median 21  | `Vol % of Vol Median 21` |

The internal calculation still aligns QQQ's daily volume to the ticker's
trading calendar, so the benchmark side is exact even for tickers with
partial histories.

---

## Relative Vol vs QQQ Market

**Original ThinkScript** (`scripts/CJ_VolQQQPlusWATCHLIST.ts`):

```
input benchmarkSymbol = "QQQ";
plot RelVolPlus = log(volAvg / qqqVolAvg) * 100;
```

**Daily mapping:**

```
Relative Vol vs QQQ Market = log(Vol % of Vol Median 21 / qqqVolPct) * 100
where qqqVolPct = QQQ's own Vol % of Vol Median 21 (QQQ row)
```

**Trader meaning:** The ticker's volume (`Vol`) normalized against the market's
(QQQ's) relative volume, log-scaled. 0 = the stock's volume activity matches
the market's; positive = trading on relatively higher volume than the
market; negative = lighter. (The original script's trailing "+", inspired by
sabermetrics like OPS+, is dropped here for clarity.)

**Recompute from the watchlist:** `log(Vol % of Vol Median 21 / QQQ's Vol % of Vol Median 21) * 100`,
using the `QQQ` row for the denominator.

---

## Notional Value $M

**Original ThinkScript** (`scripts/CJ_vwapXVolWATCHLIST.ts`):

```
input divisor = 1000000.0;
plot VWAP_DollarVol = Round((volume * vwap) / divisor);
```

**Daily mapping:**

```
Notional Value $M = round(Volume * OHLC / 4 / 1_000_000)
```

**Trader meaning:** Dollar value traded for the day in millions (volume
weighted at the OHLC / 4 proxy price). A liquidity/participation measure:
large, liquid names show high values. `$M` = millions of USD; the column holds
the raw numeric value for easy sorting.

**Recompute from the watchlist:** `Volume * OHLC / 4 / 1_000_000`, rounded.

---

## Dropped columns

| Column | Source script | Reason |
|--------|---------------|--------|
| NumHighLow | `CJ_NumHighLowWATCHLIST.ts` | Counts intraday new highs/lows within market hours; not reproducible from daily bars. |
| VolMaxRatio | `CJ_BarVolVMMaxWATCHLIST.ts` | Intraday max-volume ratio; identical to `Vol % of Vol EMA 21` under the 21-day rule. |
| MomRk | `CJ_MomRkWATCHLIST.ts` | Placeholder file containing only "x"; no definition to port. |
