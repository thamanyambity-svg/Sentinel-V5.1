from bot.strategy.registry import get_strategy


def run_strategy(name: str, context: dict):
    """
    Exécute une stratégie et retourne un trade ou None.
    """
    strategy = get_strategy(name)
    return strategy.decide(context)
