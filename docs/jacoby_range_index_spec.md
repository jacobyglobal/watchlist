# Jacoby Range Index (JRI) — Indicator Specification

> **Version:** 2.0 (linear distance weighting)
> **Supersedes:** v1.0 (exponential decay weighting, `k = 0.1`)
> See `docs/jacoby_range_index_whitepaper.md` for the design rationale and the
> empirical comparison that led to this version.

## Overview

The **Jacoby Range Index (JRI)** is a proprietary multi-timeframe technical
indicator that enhances traditional DeMark range positioning concepts. Instead
of evaluating price position against a single lookback window (such as 52
weeks), JRI measures price attraction across four distinct structural
timeframes (**4, 12, 26, and 52 weeks**).

Each timeframe contributes a DeMark-style range position, and the timeframes
are blended with a **linear proximity bonus** applied on top of fixed
structural base weights. The result stays anchored to the annual trend while
still rewarding price action that is actively pressing on nearer-term
boundaries.

---

## Mathematical Formulation

### 1. Inputs & Base Definitions

- **Typical Price ($\text{TP}$):** $\text{TP} = \text{OHLC} / 4 = \frac{\text{Open} + \text{High} + \text{Low} + \text{Close}}{4}$
- **Timeframe Lookbacks ($T$) and Base Weights ($b_T$):**

| Timeframe | Trading Days | Base Weight $b_T$ |
| :--- | :---: | :---: |
| 4 weeks | 20 | 0.15 |
| 12 weeks | 60 | 0.20 |
| 26 weeks | 130 | 0.25 |
| 52 weeks | 252 | 0.40 |

- **Boundaries:** For each timeframe $T$, define $\text{High}_T$ and $\text{Low}_T$
  as the rolling highest high / lowest low over the lookback, with
  $\text{Range}_T = \text{High}_T - \text{Low}_T$.

### 2. Range Position Calculation

For each timeframe $T$:

$$\text{RangePos}_T = \left( \frac{\text{TP} - \text{Low}_T}{\text{Range}_T} \right) \times 100 - 50$$

*(Zero-centered scale from $-50$ to $+50$. Above zero = upper half of the
range; below zero = lower half. A zero-width range yields $\text{RangePos} = 0$.)*

### 3. Linear Distance Weighting

Each timeframe is weighted by its **structural base weight** multiplied by a
**linear proximity bonus** that grows smoothly as price approaches a boundary:

$$W_T = b_T \times \left( 1 + \alpha \cdot \frac{|\text{RangePos}_T|}{50} \right)$$

Where:
- $b_T$ = the timeframe's base weight (0.15 / 0.20 / 0.25 / 0.40).
- $\alpha$ = the proximity scale factor, fixed at **0.5**.
- $|\text{RangePos}_T| / 50$ = normalized proximity to a boundary, in $[0, 1]$.

At the middle of a range ($\text{RangePos}_T = 0$) a timeframe keeps exactly its
base weight; at a boundary ($\text{RangePos}_T = \pm 50$) it earns a **+50%
weight bonus** ($1 + 0.5$). The bonus is a smooth, bounded linear ramp — it
never collapses a timeframe's contribution to zero.

### 4. Final Composite Score

$$\text{Jacoby Range Index (JRI)} = \frac{\sum_{T} \left( \text{RangePos}_T \times W_T \right)}{\sum_{T} W_T}$$

*(Rounded to 1 decimal for the watchlist column.)*

---

## Interpretation

- **Positive values** = price in the upper half of the multi-timeframe
  structural range; strongly positive values indicate price pressing on
  stacked highs across several timeframes.
- **Negative values** = price in the lower half; strongly negative values
  indicate price pressing on stacked lows.
- Because the 52-week timeframe carries the largest base weight (0.40), the
  score tracks the annual DeMark position closely in normal conditions, and
  diverges deliberately only when shorter timeframes show boundary pressure
  (see the PLTR case study in the whitepaper).

---

## Revision History

| Version | Date | Change |
| :--- | :--- | :--- |
| 1.0 | Initial | Exponential decay weighting $W = e^{-k(50-|\text{RangePos}|)}$, $k = 0.1$, with unique-boundary grouping. |
| 2.0 | 2026 | **Linear distance weighting** with structural base weights (0.15/0.20/0.25/0.40) and proximity scale $\alpha = 0.5$. Replaces exponential decay to remove short-term overweighting of recent highs/lows. |
