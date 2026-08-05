# The Jacoby Range Index (JRI)

## A Multi-Timeframe Range-Position Framework — Design Rationale, Empirical Validation, and Case Studies

| | |
| :--- | :--- |
| **Version** | 2.0 (linear distance weighting) |
| **Author** | Christopher Jacoby |
| **Data** | Daily OHLCV, 18 months (yfinance, raw/unadjusted) |
| **Universe** | 26-ticker watchlist (25 equities + QQQ benchmark) |
| **As of** | 2026-08-04 |

---

## 1. Executive Summary

The **Jacoby Range Index (JRI)** is a proprietary multi-timeframe range-position
indicator. It blends DeMark-style range positions measured across **four
structural timeframes — 4, 12, 26, and 52 weeks** — into a single score on the
familiar zero-centered **[-50, +50]** scale.

Version 1 blended the timeframes with an exponential distance-decay function
(`k = 0.1`). Back-testing against the live watchlist exposed a serious defect:
**the exponential decay massively overweighted short-term (4-week) highs and
lows**, sometimes completely inverting the signal of the 52-week annual trend
(e.g. AAPL scored **-21.9** while sitting in the upper 23% of its 52-week
range).

Version 2 replaces exponential decay with a **linear proximity bonus applied
on top of fixed structural base weights** (4w = 15%, 12w = 20%, 26w = 25%,
52w = 40%). Across all 26 tickers the new model:

| Metric | v1 (exponential, k=0.1) | **v2 (linear)** | TD Range Rank |
| :--- | :---: | :---: | :---: |
| Correlation with TD Range Rank | **0.687** | **0.905** | 1.000 |
| Standard deviation | 26.2 | **20.9** | 23.3 |
| Extreme values (min / max) | -35.8 / +41.8 | -33.8 / +41.8 | -37.2 / +43.3 |

The linear model is **more aligned with the annual trend, tighter in
distribution, and free of the false-signal flips** that plagued v1 — while
still rewarding genuine multi-timeframe breakouts that a single 52-week rank
misses.

---

## 2. Background & Motivation

### 2.1 The DeMark Heritage

The **TD Range Rank** (formerly "DeMark High Low Rank") in this watchlist
measures where price sits inside a single 252-trading-day high/low band:

```
TD Range Rank = ((Typical Price (TP) - 52-Week Low) / (52-Week High - 52-Week Low)) × 100 - 50
```

where `Typical Price (TP) = (Open + High + Low + Close) / 4` (the daily
substitute for intraday VWAP).

A single lookback has a structural blind spot: **it cannot distinguish between
short-, medium-, and long-term structure.** A stock making new 6-month highs
after a failed 10-month high prints the same neutral reading as a stock idling
in the middle of a year-long range. It also cannot see developing pressure —
price pushing into a stack of recent highs — until that pressure has already
materialized in the 52-week band.

### 2.2 The Multi-Timeframe Idea

JRI measures price attraction against the structural boundaries of four
timeframes at once:

| Timeframe | Lookback (trading days) |
| :--- | :---: |
| 4 weeks | 20 |
| 12 weeks | 60 |
| 26 weeks | 130 |
| 52 weeks | 252 |

Each timeframe contributes a DeMark-style range position. The question that
drove the design of v2 was: **how should the four positions be combined?**

---

## 3. The Jacoby Range Index — Version 2 (Final Formulation)

### 3.1 Range Position (same for every timeframe)

$$\text{RangePos}_T = \left( \frac{\text{TP} - \text{Low}_T}{\text{High}_T - \text{Low}_T} \right) \times 100 - 50$$

- **+50** = price at the timeframe high
- **0** = price at the midpoint
- **-50** = price at the timeframe low

### 3.2 Structural Base Weights

Macro timeframes carry a higher foundational weight than tactical ones:

| Timeframe $T$ | Lookback | Base weight $b_T$ |
| :--- | :---: | :---: |
| 4 weeks | 20 | **0.15** |
| 12 weeks | 60 | **0.20** |
| 26 weeks | 130 | **0.25** |
| 52 weeks | 252 | **0.40** |

### 3.3 Linear Proximity Bonus

Each timeframe's weight is its base weight scaled by a bounded linear ramp as
price approaches a boundary:

$$W_T = b_T \times \left( 1 + \alpha \cdot \frac{|\text{RangePos}_T|}{50} \right), \qquad \alpha = 0.5$$

- At the range midpoint ($\text{RangePos}_T = 0$): weight = base weight.
- At a boundary ($\text{RangePos}_T = \pm 50$): weight = base weight × **1.5**.
- The bonus is **linear and capped** — a boundary-hugging timeframe can never
  exceed 1.5× its base weight.

### 3.4 Composite Score

$$\text{JRI} = \frac{\sum_T \text{RangePos}_T \times W_T}{\sum_T W_T}, \qquad \text{rounded to 1 decimal}$$

Because the 52-week timeframe starts at 40% base weight, the score **tracks the
annual DeMark position in normal conditions** and diverges deliberately only
when shorter timeframes press their boundaries.

---

## 4. Why Version 1 (Exponential Decay) Failed

### 4.1 The Exponential Cliff

Version 1 weighted each timeframe by

$$W_T = e^{-k \cdot (50 - |\text{RangePos}_T|)}, \qquad k = 0.1$$

Here `50 - |RangePos|` is the distance (in points of range position) between
price and the nearer boundary. The problem is the shape of the function:

| Distance to boundary | Weight ($e^{-0.1 \times Dist}$) |
| :---: | :---: |
| 5 (price hugging a boundary) | 0.6065 |
| 10 | 0.3679 |
| 25 | 0.0821 |
| 35 | 0.0302 |
| 47 (price near the midpoint) | 0.0091 |

A price hugging a boundary gets a weight **~67× larger** than a price near the
midpoint. In a 4-week window, price is *almost always* within a few points of
the 4-week high or low (short lookbacks have tight ranges, so price reaches
their boundaries constantly). In a 52-week window, price is frequently
mid-range. The result: **short-term timeframes systematically crushed the
long-term timeframe out of the composite.**

### 4.2 Demonstrated Damage

On the 2026-08-04 watchlist, v1 produced outright contradictions of the annual
trend:

| Ticker | TD Range Rank (52w) | v1 JRI | Interpretation |
| :--- | :---: | :---: | :--- |
| AAPL | **+23.0** (upper quartile) | **-21.9** | A 4-week pullback inverted a bullish annual position |
| LLY | **+29.2** (strongly bullish) | **-23.4** | A short-term dip inverted a strongly bullish annual position |
| INTC | **+13.9** (bullish) | **-10.0** | Mid-range drift flipped the score negative |

AAPL and LLY are instructive: their 4-week range positions were **-36.6** and
**-42.2** (price was near the *bottom* of the recent 4-week range). Under the
exponential cliff those two timeframes dominated the composite, dragging scores
deeply negative for stocks that were in the **upper 23–29 points** of their
52-week ranges. That is not signal — it is noise.

### 4.3 Why Linear Weighting Fixes This

Model 4's weight multiplier is bounded between **1.0× and 1.5×** the base
weight. The 52-week timeframe therefore always retains meaningful influence
(minimum weight share ≈ 34% of the total, see §6), while the 4-week timeframe
can at most earn a 50% bonus on its own (small) 15% base.

---

## 5. Candidate Models Compared

Five blending schemes were evaluated on the full 26-ticker watchlist:

| Model | Weighting formula |
| :--- | :--- |
| **v1** | $W_T = e^{-0.1 \cdot (50 - |\text{RangePos}_T|)}$ (equal base) |
| **M1** | $b_T \cdot e^{-0.03 \cdot (50 - |\text{RangePos}_T|)}$ (mild exp. decay + base weights) |
| **M2** | $b_T \cdot e^{-0.02 \cdot (50 - |\text{RangePos}_T|)}$ (weak exp. decay + base weights) |
| **M3** | $0.25 \cdot e^{-0.02 \cdot (50 - |\text{RangePos}_T|)}$ (weak exp. decay, equal base) |
| **M4 (v2)** | $b_T \cdot \left(1 + 0.5 \cdot \frac{|\text{RangePos}_T|}{50}\right)$ (linear + base weights) |

### 5.1 Full Watchlist Comparison (2026-08-04)

| Ticker | TD 52w | v1 | M1 | M2 | M3 | **M4 (v2)** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| MU | 17.4 | 6.3 | 7.7 | 7.4 | 3.8 | **7.0** |
| MSFT | 17.9 | 41.3 | 36.2 | 35.0 | 37.8 | **33.4** |
| NVDA | 15.3 | 32.7 | 18.8 | 17.4 | 19.8 | **15.8** |
| AMZN | 39.5 | 37.5 | 37.8 | 37.8 | 37.0 | **37.7** |
| AAPL | 23.0 | -21.9 | 2.5 | 3.8 | -5.2 | **5.0** |
| SNDK | 8.4 | -12.3 | -4.2 | -3.6 | -6.9 | **-3.0** |
| PLTR | -3.0 | 29.6 | 22.8 | 21.1 | 24.7 | **18.8** |
| AMD | 33.7 | 30.7 | 28.4 | 27.5 | 24.4 | **26.4** |
| GOOGL | 33.9 | 34.7 | 30.2 | 29.5 | 29.3 | **28.6** |
| META | -26.5 | -21.7 | -21.3 | -21.0 | -18.9 | **-20.6** |
| SPCX | -36.4 | -35.5 | -34.6 | -34.3 | -32.7 | **-33.8** |
| TSLA | -36.1 | -32.7 | -33.0 | -32.9 | -31.7 | **-32.8** |
| INTC | 13.9 | -10.0 | 0.3 | 0.9 | -3.0 | **1.5** |
| AVGO | 10.6 | 25.6 | 12.2 | 11.1 | 13.2 | **10.0** |
| ORCL | -37.2 | -11.0 | -21.9 | -22.0 | -13.6 | **-22.1** |
| MRVL | 7.1 | -4.2 | 0.9 | 1.3 | 0.1 | **1.8** |
| NBIS | 18.4 | 35.4 | 21.5 | 19.9 | 22.4 | **18.2** |
| LITE | 25.6 | 28.5 | 22.6 | 21.7 | 21.9 | **20.6** |
| STX | 21.6 | 13.4 | 13.3 | 13.0 | 10.8 | **12.6** |
| WDC | 15.7 | 9.8 | 8.3 | 8.1 | 7.3 | **7.9** |
| BE | 10.9 | -0.4 | 2.2 | 2.2 | 0.7 | **2.3** |
| CAT | 24.0 | 16.1 | 14.4 | 13.7 | 10.4 | **12.8** |
| LLY | 29.2 | -23.4 | 6.9 | 8.6 | -1.8 | **10.4** |
| WMT | -12.9 | -35.8 | -29.4 | -28.1 | -29.7 | **-26.4** |
| JPM | 43.3 | 41.8 | 42.0 | 41.9 | 41.0 | **41.8** |
| QQQ | 33.3 | 32.9 | 31.1 | 30.6 | 30.0 | **29.9** |

---

## 6. Distribution Analysis

### 6.1 Spread, Center, and Dispersion

| Model | Min | Max | Mean | Std Dev |
| :--- | :---: | :---: | :---: | :---: |
| TD Range Rank | -37.2 | +43.3 | +11.2 | 23.3 |
| v1 (exponential k=0.1) | -35.8 | +41.8 | +8.0 | **26.2** |
| M1 (k=0.03 + base) | -34.6 | +42.0 | +8.3 | 22.0 |
| M2 (k=0.02 + base) | -34.3 | +41.9 | +8.1 | 21.5 |
| M3 (k=0.02, equal) | -32.7 | +41.0 | +7.3 | 21.4 |
| **M4 / v2 (linear)** | **-33.8** | **+41.8** | **+7.8** | **20.9** |

- **v1 has the widest dispersion (std 26.2)** — wild, threshold-sensitive
  swings driven by short-term boundary proximity.
- **M4 / v2 has the tightest dispersion (std 20.9)** and the narrowest
  min-to-max span of the viable candidates. Scores are smooth and predictable,
  with no compressed tail collapse on either side.

### 6.2 Correlation with the Annual (TD) Position

| Model | Pearson correlation vs TD Range Rank |
| :--- | :---: |
| v1 (exponential k=0.1) | **0.687** |
| M1 (k=0.03 + base) | 0.880 |
| M2 (k=0.02 + base) | 0.892 |
| M3 (k=0.02, equal) | 0.807 |
| **M4 / v2 (linear)** | **0.905** |

**M4 / v2 is the most aligned with the annual trend of every candidate.**
This is the quantitative confirmation of the qualitative observation: M4
"feels" closer to TD because it *is* closest — 0.905 correlation, versus 0.687
for v1.

### 6.3 How M4 Achieves Both Anchoring and Sensitivity

Consider PLTR, where v1 and M4 diverge most meaningfully (see §7.1). The
effective weight each timeframe earned in the final composite:

| Timeframe | v1 weight share | **M4 weight share** |
| :--- | :---: | :---: |
| 4 weeks | 24.3% | **16.0%** |
| 12 weeks | 38.1% | **22.1%** |
| 26 weeks | 35.5% | **27.4%** |
| 52 weeks | **2.2%** | **34.5%** |

Under v1 the 52-week annual structure contributed **just 2.2%** of the weight —
practically invisible. Under M4 it contributes **34.5%**, while the three
shorter timeframes retain a combined 65.5% that still rewards momentum. This
is the entire design: *anchor the score in macro structure, let short-term
pressure modulate rather than override it.*

### 6.4 Conclusions from the Distribution Analysis

1. **v1 was mis-scaled.** Its exponential cliff inflated the standard deviation
   by 25% relative to TD and produced false sign flips.
2. **Base weights matter more than the decay shape.** M2 vs M3 shows that
   giving the 52-week timeframe a heavier base weight (0.40 vs 0.25) raises
   correlation with the annual rank by ~0.09.
3. **Linear weighting is strictly better than every exponential variant
   tested** on both objectives: alignment with macro structure (0.905) and
   distributional discipline (std 20.9).
4. **M4 retains the multi-timeframe edge.** Its 0.905 correlation is
   deliberately below 1.000 — the whole point of JRI is to deviate from the
   single-lookback rank when structure develops at shorter horizons (PLTR,
   §7.1).

---

## 7. Case Studies

### 7.1 PLTR — The Flagship Case

> A powerful 6-month momentum expansion that a single 52-week rank completely
> misses.

**Market state (2026-08-04):** Close **$162.66**, Typical Price **$153.90**.

| Timeframe | High | Low | Range | RangePos | Boundary distance |
| :--- | :---: | :---: | :---: | :---: | :---: |
| 4 weeks | $164.51 | $117.89 | $46.62 | **+27.2** | 22.8 |
| 12 weeks | $164.51 | $106.37 | $58.14 | **+31.7** | 18.3 |
| 26 weeks | $165.08 | $106.37 | $58.71 | **+31.0** | 19.0 |
| 52 weeks | $207.52 | $106.37 | $101.15 | **-3.0** | 47.0 |

**Why TD Range Rank says -3.0:** PLTR printed a 52-week high of **$207.52**
earlier in the year, then corrected to a low of **$106.37**. With price at
$153.90, the stock sits just below the midpoint of that wide annual band.

**Why JRI v2 says +18.8:** the 4-, 12-, and 26-week highs all sit at ~$164–165,
and price is trading **right into that stack**. Three of the four timeframes
read +27 to +32 (upper quartile of their ranges). M4's weights were:

| Timeframe | RangePos | Weight | Weight × RangePos |
| :--- | :---: | :---: | :---: |
| 4 weeks | +27.2 | 0.1908 | +5.19 |
| 12 weeks | +31.7 | 0.2634 | +8.35 |
| 26 weeks | +31.0 | 0.3275 | +10.15 |
| 52 weeks | -3.0 | 0.4120 | -1.24 |

$$\text{JRI} = \frac{5.19 + 8.35 + 10.15 - 1.24}{0.1908 + 0.2634 + 0.3275 + 0.4120} = \frac{22.46}{1.1937} = +18.8$$

**The insight:** PLTR is in the middle of a **six-month momentum expansion** —
pressing a stack of converging near-term highs. The 52-week rank is anchored to
a ten-month-old high and reports "neutral." JRI correctly reports "strongly
upper-range on every active timeframe." **This is precisely the case where the
multi-timeframe score earns its keep.**

### 7.2 AAPL & LLY — False Negatives Fixed

These were v1's worst failures: strongly bullish annual positions flipped
deeply negative by a 4-week pullback.

| Ticker | 4w | 12w | 26w | 52w | v1 JRI | **v2 JRI** | TD 52w |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| AAPL | **-36.6** | -4.5 | +11.0 | +23.0 | -21.9 | **+5.0** | +23.0 |
| LLY | **-42.2** | +7.6 | +17.4 | +29.2 | -23.4 | **+10.4** | +29.2 |

- **AAPL:** a 4-week range position of -36.6 (price near the recent 4-week
  low) carried the v1 composite to -21.9. Under v2, the 4-week timeframe
  contributes at most 15% × 1.5 = 22.5% weight, and its penalty is linear, not
  exponential. The composite lands at **+5.0** — positive, reflecting the
  bull-ish annual structure, but tempered by the short-term pullback.
- **LLY:** same story — a -42.2 four-week reading dragged v1 to -23.4. v2
  lands at **+10.4**: bullish annual structure (52w = +29.2) with a haircut
  for the near-term dip. No sign flip.

**The lesson:** a 4-week pullback inside a strong uptrend is *context*, not a
reversal signal. v1 turned context into catastrophe; v2 keeps it in scale.

### 7.3 MSFT — Multi-Timeframe Breakout Confirmation

| Ticker | 4w | 12w | 26w | 52w | v1 JRI | **v2 JRI** | TD 52w |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| MSFT | +41.0 | +42.4 | +42.4 | +17.9 | 41.3 | **+33.4** | +17.9 |

MSFT is consolidating just below a **stacked** 4w/12w/26w high of $499.44 —
three timeframes reading +41 to +42. TD says +17.9 (upper half, nothing
special); v1 says +41.3 (essentially ignoring the 52-week band). v2 settles at
**+33.4**: strongly upper-range on the active timeframes, while still
respecting that price remains well inside its 52-week band. The score is
sensitive, but not monomaniacal.

### 7.4 INTC — Mid-Range Drift No Longer Flips Sign

| Ticker | 4w | 12w | 26w | 52w | v1 JRI | **v2 JRI** | TD 52w |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| INTC | -3.7 | -23.3 | +6.4 | +13.9 | -10.0 | **+1.5** | +13.9 |

INTC's 12-week position of -23.3 (price in the lower half of its 3-month
range) dragged v1 to -10.0. Under v2, that single soft timeframe cannot flip a
bullish annual position (52w = +13.9); the composite reads +1.5 — effectively
neutral, which accurately describes a stock drifting mid-range across horizons.

---

## 8. Interpretation & Usage Guidelines

1. **Scale semantics.** The [-50, +50] scale matches TD Range Rank: positive =
   upper half of the structural range, negative = lower half, magnitude = how
   far from center. Values above ~+30 indicate price pressing into stacked
   highs; below ~-30, stacked lows.
2. **JRI vs TD Range Rank.** Read them as a pair:
   - **JRI ≈ TD:** all timeframes agree — the trend is coherent.
   - **JRI > TD materially (≥ +10):** short/medium-term expansion above a
     stagnant annual band — a developing move (see PLTR, MSFT).
   - **JRI < TD materially (≤ -10):** short/medium-term compression below the
     annual position — a pullback, a bearish divergence, or distribution
     (see AAPL, LLY, INTC before the fix).
3. **Confirmation, not prediction.** JRI describes *where price is* across
   horizons. It does not forecast direction; it contextualizes it.
4. **Smoothing.** Because the weights are linear and bounded, JRI is
   substantially less jumpy than v1 — a single day near a 4-week boundary
   moves the score by a few points, not a sign flip.

---

## 9. Limitations & Future Work

1. **Single snapshot.** All figures in this whitepaper are from one date
   (2026-08-04). Distributional properties (correlation, std) should be
   re-verified over rolling windows before production thresholds are set.
2. **Base weights are a design choice.** 15/20/25/40 were chosen to express
   "macro dominance with tactical modulation." They are tunable; the whitepaper
   methodology allows any `b_T` and any proximity scale `α` to be evaluated the
   same way.
3. **Daily-resolution VPOC-like boundaries.** The 20/60/130/252 lookbacks are
   trading-day approximations of 4/12/26/52 weeks. Holiday calendars and
   halts shift the exact boundaries slightly.
4. **Recent-IPO tickers (e.g. SPCX).** With fewer than 252 bars, the 52-week
   lookback degrades gracefully (rolling min-periods), but the 52-week position
   is not a true annual reading until full history accumulates.
5. **Future work.** (a) rolling-window validation of correlation/stability;
   (b) threshold testing (e.g. JRI ≥ +30 as a momentum-scan filter);
   (c) an explicit bull/bear label derived from the sign spread
   `JRI - TD Range Rank`.

---

## Appendix A. Model Definitions (reproduction)

All models use `RangePos_T` from §3.1 and, where present, base weights
`b = (0.15, 0.20, 0.25, 0.40)` for the 4/12/26/52-week timeframes.

| Model | Weight $W_T$ | Notes |
| :--- | :--- | :--- |
| v1 | $e^{-0.1 \cdot (50 - \|\text{RangePos}_T\|)}$ | equal base; exponential cliff |
| M1 | $b_T \cdot e^{-0.03 \cdot (50 - \|\text{RangePos}_T\|)}$ | base + mild decay |
| M2 | $b_T \cdot e^{-0.02 \cdot (50 - \|\text{RangePos}_T\|)}$ | base + weak decay |
| M3 | $0.25 \cdot e^{-0.02 \cdot (50 - \|\text{RangePos}_T\|)}$ | equal base + weak decay |
| **M4 / v2** | $b_T \cdot \left(1 + 0.5 \cdot \frac{\|\text{RangePos}_T\|}{50}\right)$ | **base + linear bonus** |

Composite in all cases:

$$\text{Score} = \frac{\sum_T \text{RangePos}_T \cdot W_T}{\sum_T W_T}$$

## Appendix B. Related Documents

- `docs/jacoby_range_index_spec.md` — formal v2 specification.
- `docs/jacoby_volume_profile_oscillator_spec.md` — the companion JVPO
  indicator (volume-migration oscillator).
- `docs/columns_logic.md` — full watchlist column documentation.
- `output/watchlist.csv`, `output/column_guide.json` — generated data and
  column metadata.
