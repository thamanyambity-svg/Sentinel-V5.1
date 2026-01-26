import time

_LAST_TRADE_TS = 0
COOLDOWN_SECONDS = 60


def in_cooldown():
    return time.time() - _LAST_TRADE_TS < COOLDOWN_SECONDS


def mark_trade():
    global _LAST_TRADE_TS
    _LAST_TRADE_TS = time.time()
