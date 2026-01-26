class BotError(Exception):
    """Erreur générique du bot"""

class TradeBlocked(BotError):
    """Trade refusé par la logique"""

class BrokerError(BotError):
    """Erreur d'exécution broker"""

class StateError(BotError):
    """Erreur d'état (pending / confirmed)"""
