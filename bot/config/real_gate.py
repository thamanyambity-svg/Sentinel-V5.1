"""
Gate central pour autoriser le trading réel.
TOUT doit être explicitement activé.
"""

_REAL_ENABLED = False

def enable_real_trading():
    global _REAL_ENABLED
    _REAL_ENABLED = True

def disable_real_trading():
    global _REAL_ENABLED
    _REAL_ENABLED = False

def is_real_trading_enabled():
    return _REAL_ENABLED
