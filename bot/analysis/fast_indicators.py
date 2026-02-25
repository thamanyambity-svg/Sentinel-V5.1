import numpy as np
import pandas as pd
from numba import jit

# Fallback if numba is not installed or fails
try:
    from numba import jit
    NUMBA_AVAILABLE = True
except ImportError:
    # Dummy decorator if numba missing
    def jit(nopython=True):
        def decorator(func):
            return func
        return decorator
    NUMBA_AVAILABLE = False
    print("⚠️ Numba not available. Running in standard Python mode.")

@jit(nopython=True)
def fast_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """
    RSI calculation optimized with Numba.
    Speedup: ~10x-50x vs standard Pandas apply/rolling.
    """
    n = len(prices)
    rsi = np.full(n, np.nan)
    
    if n <= period:
        return rsi
        
    deltas = np.diff(prices)
    seed = deltas[:period]
    # Initial averages
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    
    if down != 0:
        rs = up / down
    else:
        rs = np.inf
        
    rsi[period] = 100 - (100 / (1 + rs))
    
    # Smoothing
    for i in range(period + 1, n):
        delta = deltas[i - 1]
        
        if delta > 0:
            up_val = delta
            down_val = 0.
        else:
            up_val = 0.
            down_val = -delta
            
        up = (up * (period - 1) + up_val) / period
        down = (down * (period - 1) + down_val) / period
        
        if down != 0:
            rs = up / down
            rsi[i] = 100 - (100 / (1 + rs))
        else:
            rsi[i] = 100
            
    return rsi

@jit(nopython=True)
def fast_ema(prices: np.ndarray, period: int) -> np.ndarray:
    """
    Exponential Moving Average optimized with Numba.
    """
    n = len(prices)
    ema = np.full(n, np.nan)
    if n < period:
        return ema
        
    alpha = 2 / (period + 1)
    
    # Start with SMA for the first valid point (classic EMA definition varies, 
    # but often SMA is seeded)
    ema[period-1] = np.mean(prices[:period])
    
    for i in range(period, n):
        ema[i] = (prices[i] * alpha) + (ema[i-1] * (1 - alpha))
        
    return ema

class OptimizedIndicators:
    def __init__(self):
        self.use_numba = NUMBA_AVAILABLE

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates indicators using optimized functions and injects them into DataFrame.
        """
        if df.empty:
            return df
            
        # Ensure numpy array
        prices = df['close'].values.astype(np.float64)
        
        # RSI 14
        df['rsi'] = fast_rsi(prices, 14)
        
        # EMA 12, 26 (MACD components)
        df['ema_12'] = fast_ema(prices, 12)
        df['ema_26'] = fast_ema(prices, 26)
        
        # Basic MACD from EMAs
        df['macd'] = df['ema_12'] - df['ema_26']
        
        return df

if __name__ == "__main__":
    # verification
    prices = np.random.random(100) * 100
    df = pd.DataFrame({"close": prices})
    opt = OptimizedIndicators()
    df_result = opt.calculate_all(df)
    print(df_result[['close', 'rsi', 'ema_12']].tail())
