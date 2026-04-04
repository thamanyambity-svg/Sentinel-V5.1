"""
Price Action Scanner Module
===========================
Detects high-probability candlestick patterns like Pin Bars and Engulfing patterns.
Acts as a precision confirmation filter for the V5 AI.
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class PriceActionScanner:
    def __init__(self):
        logger.info("🕯️ PriceActionScanner Initialized. Ready for OHLC Pattern detection.")

    def analyze_candles(self, candles: List[List[float]], signal_direction: str) -> Dict[str, Any]:
        """
        Analyzes recent OHLC candles to confirm or reject a technical signal.
        candles: List of arrays like [[open, high, low, close], ...]
                 Ordered from oldest to newest (index -1 is the current/latest completed candle).
        signal_direction: "BUY" or "SELL" (from EMA/RSI logic)
        """
        if not candles or len(candles) < 2:
            return {"confirmed": True, "reason": "Not enough candles to analyze"}

        # Format: [open, high, low, close]
        latest = {
            "open": candles[-1][0], "high": candles[-1][1],
            "low": candles[-1][2], "close": candles[-1][3]
        }
        previous = {
            "open": candles[-2][0], "high": candles[-2][1],
            "low": candles[-2][2], "close": candles[-2][3]
        }
        
        # Calculate Candle Physics
        body_size = abs(latest["close"] - latest["open"])
        total_range = latest["high"] - latest["low"]
        
        if total_range == 0:
            return {"confirmed": True, "reason": "Zero range candle"}

        upper_wick = latest["high"] - max(latest["open"], latest["close"])
        lower_wick = min(latest["open"], latest["close"]) - latest["low"]
        
        # Pin Bar Definitions
        is_bullish_pin = (lower_wick > (2 * body_size)) and (upper_wick < body_size)
        is_bearish_pin = (upper_wick > (2 * body_size)) and (lower_wick < body_size)
        
        # Engulfing Definitions
        prev_body = abs(previous["close"] - previous["open"])
        latest_bullish = latest["close"] > latest["open"]
        prev_bearish = previous["close"] < previous["open"]
        
        is_bullish_engulfing = latest_bullish and prev_bearish and latest["close"] > previous["open"] and latest["open"] < previous["close"]
        is_bearish_engulfing = not latest_bullish and not prev_bearish and latest["close"] < previous["open"] and latest["open"] > previous["close"]

        # ----------------------------------------------------------------
        # FILTERING LOGIC
        # ----------------------------------------------------------------
        if signal_direction == "BUY":
            # If the tech indicator says BUY, but the recent price action shows a massive rejection from above
            if is_bearish_pin or is_bearish_engulfing:
                return {
                    "confirmed": False, 
                    "reason": f"VETO: Bearish Price Action (Pin={is_bearish_pin}, Engulfing={is_bearish_engulfing})"
                }
            
            # Bonus confirmation
            if is_bullish_pin or is_bullish_engulfing:
                return {"confirmed": True, "reason": "STRONG CONFIRMATION: Bullish Price Action"}

        elif signal_direction == "SELL":
            # If tech says SELL, but price action shows heavy rejection from bottom
            if is_bullish_pin or is_bullish_engulfing:
                return {
                    "confirmed": False,
                    "reason": f"VETO: Bullish Price Action (Pin={is_bullish_pin}, Engulfing={is_bullish_engulfing})"
                }
            
            # Bonus confirmation
            if is_bearish_pin or is_bearish_engulfing:
                return {"confirmed": True, "reason": "STRONG CONFIRMATION: Bearish Price Action"}

        return {"confirmed": True, "reason": "Standard Execution (No aggressive counter-PA)"}
