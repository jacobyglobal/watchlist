# WatchList Column Logic

This document explains every column in the watchlist. For each column we show
the **original ThinkScript** (where one exists), the **daily-data mapping**
used in this project, and the **trader meaning**.

The watchlist includes **every intermediate value** used in any calculation,
so a viewer can recompute any number by hand from the formulas below and the
base OHLCV columns.

## Conventions

- Data: 18 months of daily OHLCV from `yfinance` (raw/unadjusted prices).
- `Typical Price (TP) = (Open + High + Low + Close) / 4` per bar — the VWAP
  proxy used by the ThinkScripts. Daily data has no intraday VWAP, so
  OHLC / 4 is the standard daily substitute.
- Lookback: standardized to **21 bars** for all window-based variables,
  except the DeMark and Jacoby columns which use 52-week (252-trading-day)
  and multi-timeframe high/low lookbacks.
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

## Typical Price (TP) — VWAP proxy

**Formula:**

```
Typical Price (TP) = (Open + High + Low + Close) / 4
```

**Trader meaning:** A per-bar typical-price proxy. It stands in for intraday
VWAP throughout the watchlist (used by Normalized ATR (NATR), TD Range Rank,
Notional Turnover ($M), and the Jacoby indicators).

---

## True Range (TR)

**Formula** (ThinkScript `TrueRange(high, price, low)`):

```
True Range (TR) = Max(High - Low, |High - Typical Price (TP)|, |Typical Price (TP) - Low|)
```

**Trader meaning:** The daily true range of the bar, measured from the
Typical Price (TP) proxy instead of the close. It is the input series to
Average True Range (ATR).

---

## Average True Range (ATR)

**Original ThinkScript** (`scripts/CJ_ATRPctVWAPWATCHLIST.ts`):

```
def ATR = MovingAverage(AverageType.EXPONENTIAL, TrueRange(high, vwap, low), 21);
```

**Daily mapping:** `Average True Range (ATR) = EMA21(True Range (TR))`
(exponential smoothing, span 21, ThinkOrSwim `ExpAverage` semantics).

**Trader meaning:** The 21-day average true range anchored at the Typical
Price (TP) proxy — a volatility measure in dollar terms.

---

## Normalized ATR (NATR)

**Original ThinkScript** (`scripts/CJ_ATRPctVWAPWATCHLIST.ts`):

```
plot ATRPct = if vwap > 0 then ((vwap + ATR) / vwap) * 100 else baseValue;
```

**Daily mapping:**

```
Normalized ATR (NATR) = ((Typical Price (TP) + Average True Range (ATR)) / Typical Price (TP)) * 100
```

**Trader meaning:** The Average True Range (ATR) expressed as a percentage of
price. `Normalized ATR (NATR) - 100` is the ATR as a % of price; values well
above 100 indicate an expanded daily range relative to price.

**Recompute from the watchlist:** `(Typical Price (TP) + Average True Range (ATR)) / Typical Price (TP) * 100`
using the `Typical Price (TP)` and `Average True Range (ATR)` columns.

---

## 52-Week High / 52-Week Low

**Formula** (ThinkScript `Highest(high, 252)` / `Lowest(low, 252)`):

```
52-Week High = max(High) over the last 252 bars (52 weeks)
52-Week Low  = min(Low)  over the last 252 bars (52 weeks)
```

**Trader meaning:** The 52-week trading range boundary — the DeMark High/Low
reference levels. The denominator of TD Range Rank.

---

## 52-Week Range Position

**Formula:**

```
52-Week Range Position = 52-Week High - 52-Week Low
```

**Trader meaning:** The width of the 52-week high-low range, in dollars. The
band against which TD Range Rank places the current price.

---

## TD Range Rank

**Original ThinkScript** (`scripts/CJ_DMHLWATCHLIST.ts`):

```
input lookbackLength = 252;
input offset = 50.0;
plot DMHL = if (maxHigh - minLow) == 0 then dmhlNaN
            else Round((vwap - minLow) / (maxHigh - minLow) * 100, 1) - offset;
```

**Daily mapping:**

```
TD Range Rank = ((Typical Price (TP) - 52-Week Low) / 52-Week Range Position) * 100 - 50   (rounded to 1 decimal)
```

**Trader meaning:** Where the Typical Price (TP) sits inside the **52-week**
high-low range, on a 0-centered scale of [-50, +50] (DeMark High Low). Above
zero = upper half of the yearly range; below zero = lower half. The original
script colors `>= 44` cyan (near the yearly high) and `<= -34` yellow (near
the yearly low). The sentinel 65.0 is used when the range is zero (rare).

**Recompute from the watchlist:** `(Typical Price (TP) - 52-Week Low) / 52-Week Range Position * 100 - 50`.

---

## Jacoby Range Index

**Source spec:** `docs/jacoby_range_index_spec.md` (v2.0, linear distance weighting).

**Overview:** A proprietary multi-timeframe range-position score that enhances
the DeMark concept. Instead of one lookback, it measures price attraction
against the structural high/low boundaries of four timeframes — 4, 12, 26,
and 52 weeks (mapped to **20, 60, 130, 252 trading days**).

**Algorithm (per bar):**

1. Compute the four timeframe boundaries: `High_T = Highest(High, lookback_T)`
   and `Low_T = Lowest(Low, lookback_T)` for each `T` in {4, 12, 26, 52} weeks.
2. For each timeframe compute the range position
   `RangePos_T = (TP - Low_T) / (High_T - Low_T) * 100 - 50`, on the same
   zero-centered [-50, +50] scale as TD Range Rank.
3. Weight each timeframe by its **structural base weight** times a **linear
   proximity bonus**:
   `W_T = base_weight_T * (1 + 0.5 * |RangePos_T| / 50)`, with base weights
   **0.15 (4w), 0.20 (12w), 0.25 (26w), 0.40 (52w)**. A timeframe whose
   boundary price is hugging earns up to a +50% weight boost; mid-range
   timeframes keep exactly their base weight.
4. Final score = `(Σ RangePos_T × W_T) / Σ W_T`, rounded to 1 decimal.

**Trader meaning:** Same 0-centered [-50, +50] scale as TD Range Rank. Above
zero = price in the upper half of the multi-timeframe structural range;
below zero = lower half. Because the 52-week timeframe carries the largest
base weight, the score stays anchored to the annual trend; it diverges from
TD Range Rank deliberately when price is pressing on the stacked nearer-term
highs or lows of a developing move (e.g. a 6-month momentum expansion in PLTR
scores strongly positive even though the 52-week DeMark position is neutral).

**Recompute from the watchlist:** `Σ (RangePos_T × W_T) / Σ W_T` using the
`Typical Price (TP)` column plus the 20/60/130/252-bar highs/lows (the
52-week pair is exposed as `52-Week High` / `52-Week Low`).

---

## Session Return %

**Original ThinkScript** (`scripts/CJ_PctChOpWATCHLIST.ts`):

```
plot chgOpenPct = log(close / open) * 100;
```

**Daily mapping:** `Session Return % = log(Close / Open) * 100`

**Trader meaning:** Continuously-compounded percent change from the open to
the close. Positive = closed above the open; negative = closed below.

---

## 21-Period EMA Volume

**Formula** (ThinkScript `ExpAverage(volume, 21)`):

```
21-Period EMA Volume = EMA21(Volume)
```

**Trader meaning:** The 21-day exponential moving average of volume (`Vol`).
The baseline for Relative Volume (RVOL EMA). (`Vol` = raw `Volume`.)

---

## Relative Volume (RVOL EMA)

**Original ThinkScript** (`scripts/CJ_VolAvgPlusWATCHLIST.ts`):

```
input length = 13;   # standardized to 21
plot VolAvgPct = Round(ratio, 1);
```

**Daily mapping:**

```
Relative Volume (RVOL EMA) = Volume / 21-Period EMA Volume * 100   (rounded to 1 decimal)
```

**Trader meaning:** Current volume relative to its 21-day exponential average.
100 = average activity; >130 = heavy volume; <80 = light volume. This column
replaces `VolMaxRatio` (intraday-only) — under the standardized 21-day
lookback the daily proxies are mathematically identical.

**Recompute from the watchlist:** `Volume / 21-Period EMA Volume * 100`.

---

## 21-Period Median Volume

**Formula** (ThinkScript `Median(volume, 21)`):

```
21-Period Median Volume = median(Volume) over the last 21 bars
```

**Trader meaning:** The 21-day median volume (`Vol`) — the baseline for the
ticker side of Idiosyncratic RVOL.

---

## Relative Volume (RVOL Median)

**Formula** (ThinkScript `(volume / Median(volume, len)) * 100`):

```
Relative Volume (RVOL Median) = Volume / 21-Period Median Volume * 100
```

**Trader meaning:** The ticker's volume (`Vol`) as a percentage of its own
21-day median volume. 100 = median activity.

**Recompute from the watchlist:** `Volume / 21-Period Median Volume * 100`.

---

## Benchmark values (no dedicated columns)

QQQ's `QQQ ETF Vol`, `QQQ 21-Period Median Volume`, and `QQQ Relative Volume
(RVOL Median)` were removed as redundant now that QQQ is a watchlist row. The
benchmark side of `Idiosyncratic RVOL` uses QQQ's own columns:

| Benchmark value (former column) | Now read from QQQ's row |
|---------------------------------|--------------------------|
| QQQ ETF Vol                     | `Volume (Vol)`           |
| QQQ 21-Period Median Volume     | `21-Period Median Volume` |
| QQQ Relative Volume (RVOL Median) | `Relative Volume (RVOL Median)` |

The internal calculation still aligns QQQ's daily volume to the ticker's
trading calendar, so the benchmark side is exact even for tickers with
partial histories.

---

## Idiosyncratic RVOL

**Original ThinkScript** (`scripts/CJ_VolQQQPlusWATCHLIST.ts`):

```
input benchmarkSymbol = "QQQ";
plot RelVolPlus = log(volAvg / qqqVolAvg) * 100;
```

**Daily mapping:**

```
Idiosyncratic RVOL = log(Relative Volume (RVOL Median) / qqqVolPct) * 100
where qqqVolPct = QQQ's own Relative Volume (RVOL Median) (QQQ row)
```

**Trader meaning:** The ticker's volume (`Vol`) normalized against the market's
(QQQ's) relative volume, log-scaled. 0 = the stock's volume activity matches
the market's; positive = trading on relatively higher volume than the
market; negative = lighter. The name reflects the market-normalized,
asset-specific (idiosyncratic) component of volume activity.

**Recompute from the watchlist:** `log(Relative Volume (RVOL Median) / QQQ's Relative Volume (RVOL Median)) * 100`,
using the `QQQ` row for the denominator.

---

## Jacoby Volume Profile Oscillator

**Source spec:** `docs/jacoby_volume_profile_oscillator_spec.md`.

**Overview:** Measures the structural migration of institutional volume by
comparing a short-term fair-value anchor (**Fast VPOC**) against a macro
annual baseline (**Slow VPOC**).

**Daily mapping:**

1. **Fast VPOC** = synthetic Volume Point of Control over the trailing
   **20 bars** (40 price bins).
2. **Slow VPOC** = synthetic VPOC over the trailing **252 bars** (70 bins) —
   the annual baseline.
3. `Jacoby Volume Profile Oscillator = ln(Fast VPOC / Slow VPOC) * 100`,
   rounded to 2 decimals.

**Log scaling rationale:** The 20/252 fast/slow pair (12.6× gap) is a macro
annual-regime anchor. A linear percentage `(F - S) / S * 100` explodes to
+500%+ on multi-bagger re-ratings (e.g. WDC +590%, SNDK +537%). Log scaling
preserves the 1-year anchor while compressing those outliers to ~+193%,
bringing the practical watchlist scale to roughly [-35%, +200%]. For moderate
values (-30% to +30%) log scaling is nearly identical to the linear
percentage (e.g. NVDA +13.16% linear vs +12.36% log).

**Synthetic VPOC binning:** within the window, divide the price span between
the lowest low and highest high into `N` equal bins. Allocate each bar's
daily volume proportionally across the bins its High-Low range touches. The
estimated VPOC is the midpoint of the bin with the most accumulated volume.

**Trader meaning:** Positive = the fast 20-bar VPOC sits above the 252-bar
annual VPOC (upward structural volume migration / accumulation); negative =
short-term volume compressed below the annual fair value (distribution /
mean-reversion exhaustion).

> **Note — recent IPOs:** Tickers with fewer than 252 bars of history (e.g.
> SPCX, ~36 bars since listing) use the **full available history** as the slow
> baseline and an **8-bar fast window**, since the 252-bar annual baseline is
> unavailable. The column meaning is unchanged.

---

## Notional Turnover ($M)

**Original ThinkScript** (`scripts/CJ_vwapXVolWATCHLIST.ts`):

```
input divisor = 1000000.0;
plot VWAP_DollarVol = Round((volume * vwap) / divisor);
```

**Daily mapping:**

```
Notional Turnover ($M) = round(Volume * Typical Price (TP) / 1_000_000)
```

**Trader meaning:** Dollar value traded for the day in millions (volume
weighted at the Typical Price (TP) proxy). A liquidity/participation measure:
large, liquid names show high values. `$M` = millions of USD; the column holds
the raw numeric value for easy sorting.

**Recompute from the watchlist:** `Volume * Typical Price (TP) / 1_000_000`, rounded.

---

## Dropped columns

| Column | Source script | Reason |
|--------|---------------|--------|
| NumHighLow | `CJ_NumHighLowWATCHLIST.ts` | Counts intraday new highs/lows within market hours; not reproducible from daily bars. |
| VolMaxRatio | `CJ_BarVolVMMaxWATCHLIST.ts` | Intraday max-volume ratio; identical to `Relative Volume (RVOL EMA)` under the 21-day rule. |
| MomRk | `CJ_MomRkWATCHLIST.ts` | Placeholder file containing only "x"; no definition to port. |
