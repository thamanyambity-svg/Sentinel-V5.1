"""
Flags globaux de sécurité.
Aucun effet de bord implicite.
"""

REAL_TRADING_ENABLED = False


def enable_real_trading():
    global REAL_TRADING_ENABLED
    REAL_TRADING_ENABLED = True


def disable_real_trading():
    global REAL_TRADING_ENABLED
    REAL_TRADING_ENABLED = False
