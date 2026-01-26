import random
from bot.strategy.base import BaseStrategy
from bot.strategy.registry import register_strategy


@register_strategy
class RandomStrategy(BaseStrategy):
    """
    Stratégie de démonstration.
    """

    name = "RANDOM"

    def decide(self, context: dict):
        if random.random() < 0.5:
            return None

        return {
            "asset": "V75",
            "side": random.choice(["BUY", "SELL"]),
            "amount": 0.35
        }
