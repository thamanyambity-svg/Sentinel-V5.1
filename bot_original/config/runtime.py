"""
Configuration runtime globale
H24.1
"""

# Broker actif : "paper" ou "deriv"
ACTIVE_BROKER = "paper"


def get_active_broker():
    return ACTIVE_BROKER


def set_active_broker(name: str):
    global ACTIVE_BROKER
    if name not in ("paper", "deriv"):
        raise ValueError("Broker invalide")
    ACTIVE_BROKER = name
