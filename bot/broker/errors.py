class BrokerError(Exception):
    """Erreur générique broker"""
    pass


class ExecutionError(BrokerError):
    """Erreur pendant l'exécution du trade"""
    pass
