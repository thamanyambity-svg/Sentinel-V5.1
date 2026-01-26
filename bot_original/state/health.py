"""
GLOBAL HEALTH GATE
Aucun trade réel ne peut passer si HEALTH != OK
"""

_HEALTH_OK = False


def set_health_ok():
    global _HEALTH_OK
    _HEALTH_OK = True


def reset_health():
    global _HEALTH_OK
    _HEALTH_OK = False


def is_health_ok():
    return _HEALTH_OK
