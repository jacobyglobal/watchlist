"""
Jacoby Range Index (JRI) Calculation Module
------------------------------------------
Enhances traditional DeMark range positioning across multiple timeframes (4, 12, 26, 52 weeks)
using unique boundary grouping and distance-weighted exponential scoring.
"""

import numpy as np
import pandas as pd

def compute_jacoby_range_index(df: pd.DataFrame, k_decay: float = 0.1) -> pd.Series:
    """
    Computes the Jacoby Range Index (JRI) for a pandas DataFrame containing OHLC data 
    and pre-calculated high/low lookbacks for 4, 12, 26, and 52 weeks.
    
    Expected DataFrame columns:
    - Open, High, Low, Close
    - High_4w, Low_4w
    - High_12w, Low_12w
    - High_26w, Low_26w
    - High_52w, Low_52w
    """
    tp = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4.0
    
    timeframes = [
        ('4w', 'High_4w', 'Low_4w'),
        ('12w', 'High_12w', 'Low_12w'),
        ('26w', 'High_26w', 'Low_26w'),
        ('52w', 'High_52w', 'Low_52w')
    ]
    
    jri_scores = []
    
    for idx, row in df.iterrows():
        tp_val = tp.loc[idx]
        levels = []
        
        for name, h_col, l_col in timeframes:
            h_val = row[h_col]
            l_val = row[l_col]
            levels.append((h_val, l_val))
            
        # Group by unique high/low price pairs to handle overlapping durations
        unique_levels = {}
        for h_val, l_val in levels:
            key = (round(h_val, 4), round(l_val, 4))
            if key not in unique_levels:
                unique_levels[key] = {'high': h_val, 'low': l_val}
                
        # If all timeframes collapse to 1 unique level, use standard 52-week DeMark calculation
        if len(unique_levels) == 1:
            h_52, l_52 = levels[-1] # 52w is last
            rng_52 = h_52 - l_52
            if rng_52 == 0:
                score = 65.0 # Sentinel value for zero range
            else:
                score = ((tp_val - l_52) / rng_52) * 100 - 50
            jri_scores.append(score)
            continue
            
        # Multi-level distance weighting
        pos_list = []
        weight_list = []
        
        for key, lvl in unique_levels.items():
            h_val = lvl['high']
            l_val = lvl['low']
            rng = h_val - l_val
            
            if rng == 0:
                pos = 0.0
            else:
                pos = ((tp_val - l_val) / rng) * 100 - 50
                
            dist = 50 - abs(pos)
            weight = np.exp(-k_decay * dist)
            
            pos_list.append(pos)
            weight_list.append(weight)
            
        pos_arr = np.array(pos_list)
        weight_arr = np.array(weight_list)
        
        if np.sum(weight_arr) == 0:
            composite_score = np.mean(pos_arr)
        else:
            composite_score = np.sum(pos_arr * weight_arr) / np.sum(weight_arr)
            
        jri_scores.append(round(composite_score, 1))
        
    return pd.Series(jri_scores, index=df.index, name="Jacoby_Range_Index")
