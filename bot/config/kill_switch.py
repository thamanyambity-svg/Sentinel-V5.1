"""
Kill-switch global.
Priorité absolue sur tout le reste du système.
"""

_TRADING_HALTED = False


from typing import Optional

def halt_trading(reason: Optional[str] = None):
    global _TRADING_HALTED
    _TRADING_HALTED = True


def resume_trading():
    global _TRADING_HALTED
    _TRADING_HALTED = False


def is_trading_halted() -> bool:
    return _TRADING_HALTED
