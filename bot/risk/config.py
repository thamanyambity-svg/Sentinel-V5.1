"""
SENTINEL RISK OS — CENTRAL CONFIGURATION
Single Source of Truth for Thresholds, Limits, and Breakers.
"""

# ATR REGIME THRESHOLDS
REGIME_DEAD_THRESHOLD = 0.20   # < 20% of 20d avg ATR
REGIME_CHAOS_THRESHOLD = 3.50  # > 350% of 20d avg ATR

# PORTFOLIO LIMITS
MAX_TOTAL_RISK_PCT = 0.02      # 2.0% Cap
BASE_TRADE_RISK_PCT = 0.0075   # 0.75% Base
CORRELATED_RISK_PCT = 0.0035   # 0.35% Reduced

# DRAWDOWN CIRCUIT BREAKERS
DAILY_DD_HALT_R = 2.0          # Stop day if DD > 2R
WEEKLY_DD_HALVE_R = 5.0        # Halve size if Weekly DD > 5R

# EDGE DECAY BREAKERS
MIN_ROLLING_EXPECTANCY_R = 0.0 # Halt setup if expectancy < 0
ROLLING_WINDOW = 20            # Trades for rolling metrics

# EXECUTION ANOMALY
MAX_SPREAD_ATR_RATIO = 0.5     # Block if spread > 50% ATR
MAX_SLIPPAGE_POINTS = 50       # Points of deviation allowed

# HEALTH WEIGHTS (Sum = 100)
HEALTH_WEIGHTS = {
    "expectancy": 30,
    "regime": 25,
    "exposure": 20,
    "correlation": 15,
    "drawdown": 10
}
