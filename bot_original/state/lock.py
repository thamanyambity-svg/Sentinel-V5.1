"""
Verrou global d’exécution
Empêche deux exécutions simultanées
"""

_LOCKED = False


def is_locked():
    return _LOCKED


def lock():
    global _LOCKED
    _LOCKED = True


def unlock():
    global _LOCKED
    _LOCKED = False
