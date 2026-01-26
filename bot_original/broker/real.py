from bot.broker.base import BaseBroker


class RealBroker(BaseBroker):
    """
    Broker réel (désactivé par défaut)
    """

    def execute(self, trade: dict) -> dict:
        raise RuntimeError(
            "🚫 RealBroker désactivé — aucune exécution réelle autorisée"
        )
