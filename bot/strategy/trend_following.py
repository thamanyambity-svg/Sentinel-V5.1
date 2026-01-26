from bot.strategy.base import BaseStrategy
from bot.strategy.registry import register_strategy

@register_strategy
class TrendFollowingStrategy(BaseStrategy):
    """
    Trend Following Strategy:
    - BUY if Current Price > EMA 20 AND Price > Current Candle Open (Bullish momentum)
    - SELL if Current Price < EMA 20 AND Price < Current Candle Open (Bearish momentum)
    - Primarily active in TREND_STABLE regime.
    """
    name = "TREND_FOLLOWING"

    def decide(self, context: dict):
        indicators = context.get("indicators", {})
        ema20 = indicators.get("ema20")
        current_price = context.get("price")
        
        if ema20 is None or current_price is None:
            return None

        # momentum check
        is_bullish = current_price > ema20
        is_bearish = current_price < ema20

        if is_bullish:
            return {
                "asset": context.get("asset"),
                "side": "BUY",
                "amount": 0.50,
                "strategy": self.name,
                "type": "TREND_FOLLOWING"
            }
        
        if is_bearish:
            return {
                "asset": context.get("asset"),
                "side": "SELL",
                "amount": 0.50,
                "strategy": self.name,
                "type": "TREND_FOLLOWING"
            }
            
        return None
