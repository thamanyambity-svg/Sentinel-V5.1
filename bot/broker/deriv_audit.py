# Audit minimal Deriv — H21

def audit_trade(trade: dict) -> bool:
    """
    Audit avant exécution réelle
    """
    required = {"asset", "side"}
    if not required.issubset(trade.keys()):
        return False

    if trade["side"] not in {"BUY", "SELL"}:
        return False

    return True
