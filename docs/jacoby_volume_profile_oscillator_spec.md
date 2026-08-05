# Jacoby Volume Profile Oscillator (JVPO) — Complete Specification & Implementation Guide

## 1. Core Concept & Institutional Logic
The **Jacoby Volume Profile Oscillator (JVPO)** measures the structural migration of institutional volume by comparing a short-term fair-value anchor (**Fast VPOC**) against a macro annual baseline (**Slow VPOC**). 

By evaluating how short-term volume nodes diverge from the long-term annual liquidity center, the indicator highlights institutional accumulation phases, trend expansions, and mean-reversion exhaustion points.

---

## 2. Mathematical Foundation

### A. Synthetic Volume Point of Control (VPOC) Binning
Using daily OHLCV time series data without tick-level order flow, true VPOC is approximated via synthetic histogram binning over a rolling window ($W$):
1. Determine the window's lowest low ($L_{\text{min}}$) and highest high ($H_{\text{max}}$).
2. Divide the price span into $N$ global bins ($70$ bins for slow baseline, $40$ bins for fast trend).
3. For each daily bar within the window, allocate the daily volume $V_t$ proportionally across any bins touched by that day's High-Low range.
4. The estimated VPOC is the midpoint of the price bin with the highest accumulated volume.

### B. Log-Scaled Divergence Score
To ensure the oscillator is fully scale-invariant across stocks with varying share prices, the final score measures the log percentage divergence:
$$\text{JVPO} = \ln\left( \frac{\text{Fast VPOC}}{\text{Slow VPOC}} \right) \times 100$$

* **Positive Values:** Fast VPOC is above Slow VPOC, indicating upward structural volume migration.
* **Negative Values:** Fast VPOC is below Slow VPOC, indicating downward structural compression.
* **Why log scaling:** The fast/slow pair is fixed at 20/252 bars (12.6× gap). A linear percentage `(F - S) / S * 100` explodes to +500%+ on multi-bagger re-ratings (e.g. WDC +590%, SNDK +537%). Log scaling preserves the 1-year macro anchor while compressing those outliers to ~+193%, so the practical watchlist scale is roughly [-35%, +200%]. For moderate values (-30% to +30%) log scaling is nearly identical to the linear percentage (e.g. NVDA +13.16% linear vs +12.36% log).

---

## 3. Implementation Views

### View A: Python Watchlist Engine (Numerical Score)
* **Target Environment:** Python / Pandas backend & website database (`thechasix.com`).
* **Output:** A single floating-point scalar percentage (e.g., `+2.45` or `-1.12`) optimized for watchlist column sorting.
* **Interpretation:** 
  * Positive score = Short-term institutional volume migrating above annual macro fair value.
  * Negative score = Short-term volume compressed below macro fair value.

### View B: ThinkScript Chart Indicator (Visual Histogram)
* **Target Environment:** ThinkOrSwim charting platform.
* **Output:** A zero-centered visual histogram with automatic color coding (Green for expansion, Red for compression).
* **Interpretation:** 
  * Bars expanding above the zero line visually confirm the bullish structural momentum captured by the Python watchlist score.
  * Bars contracting below zero signal distribution or mean-reversion exhaustion.