from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """
    Interface minimale d’une stratégie de trading.
    """

    name = "BASE"

    @abstractmethod
    def decide(self, context: dict):
        """
        Retourne un trade dict ou None.
        """
        raise NotImplementedError
