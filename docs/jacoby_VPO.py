"""
Jacoby Volume Profile Oscillator (JVPO) Watchlist Scorer
-------------------------------------------------------
Computes a single numerical percentage divergence score for watchlist columns.
"""

import numpy as np
import pandas as pd

def compute_synthetic_vpoc(df: pd.DataFrame, window: int, num_bins: int = 70) -> pd.Series:
    vpoc_series = []
    
    for i in range(len(df)):
        if i < window - 1:
            vpoc_series.append(np.nan)
            continue
            
        window_df = df.iloc[i - window + 1: i + 1]
        min_p = window_df['Low'].min()
        max_p = window_df['High'].max()
        
        if min_p == max_p or np.isnan(min_p):
            vpoc_series.append(window_df['Close'].iloc[-1])
            continue
            
        bins = np.linspace(min_p, max_p, num_bins + 1)
        bin_volumes = np.zeros(num_bins)
        
        for _, row in window_df.iterrows():
            h, l, v = row['High'], row['Low'], row['Volume']
            if h == l or v == 0 or np.isnan(v):
                continue
            for b in range(num_bins):
                b_low, b_high = bins[b], bins[b+1]
                overlap = max(0, min(h, b_high) - max(l, b_low))
                if overlap > 0:
                    fraction = overlap / (h - l)
                    bin_volumes[b] += v * fraction
                    
        max_bin_idx = np.argmax(bin_volumes)
        estimated_vpoc = (bins[max_bin_idx] + bins[max_bin_idx + 1]) / 2.0
        vpoc_series.append(estimated_vpoc)
        
    return pd.Series(vpoc_series, index=df.index)

def get_watchlist_jvpo_score(df: pd.DataFrame, fast_window: int = 20, slow_window: int = 252) -> float:
    """
    Returns the latest scalar numerical score for a watchlist column.
    Positive values = Fast VPOC above Slow VPOC (upward structural migration).
    Negative values = Fast VPOC below Slow VPOC (downward structural compression).
    """
    fast_vpoc_series = compute_synthetic_vpoc(df, fast_window, num_bins=40)
    slow_vpoc_series = compute_synthetic_vpoc(df, slow_window, num_bins=70)
    
    fast_latest = fast_vpoc_series.iloc[-1]
    slow_latest = slow_vpoc_series.iloc[-1]
    
    if pd.isna(fast_latest) or pd.isna(slow_latest) or slow_latest == 0:
        return 0.0
        
    score = ((fast_latest - slow_latest) / slow_latest) * 100
    return round(float(score), 2)