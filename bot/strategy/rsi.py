from bot.strategy.base import BaseStrategy
from bot.strategy.registry import register_strategy

@register_strategy
class RSIStrategy(BaseStrategy):
    """
    RSI Mean Reversion Strategy:
    - Generates BUY signal if RSI < 35 (will be filtered by RSI Extreme Gate at < 28)
    - Generates SELL signal if RSI > 65 (will be filtered by RSI Extreme Gate at > 72)
    
    Two-stage filtering:
    1. Strategy generates signals in wider range (35/65)
    2. RSI Extreme Gate filters to extreme levels (28/72)
    """
    name = "RSI_BASIC"

    def decide(self, context: dict):
        # context contains market data and indicators
        # We assume context['indicators']['rsi'] exists
        
        indicators = context.get("indicators", {})
        rsi = indicators.get("rsi")
        
        if rsi is None:
            return None

        current_price = context.get("price")
        if not current_price:
            return None

        # Oversold zone - potential BUY
        if rsi < 35:
            return {
                "asset": context.get("asset", "V75"),
                "side": "BUY",
                "amount": 0.50,
                "strategy": self.name,
                "type": "MEAN_REVERSION"
            }
        
        # Overbought zone - potential SELL
        if rsi > 65:
            return {
                "asset": context.get("asset", "V75"),
                "side": "SELL",
                "amount": 0.50,
                "strategy": self.name,
                "type": "MEAN_REVERSION"
            }
            
        return None
