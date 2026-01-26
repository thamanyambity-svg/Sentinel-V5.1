"""
Health Deriv – état runtime réel
Lecture seule par défaut.
Modifié uniquement via fonctions explicites.
"""

import time

_LAST_OK = 0.0
_CONNECTED = False
_TIMEOUT = 15  # secondes


def mark_connected() -> None:
    global _CONNECTED, _LAST_OK
    _CONNECTED = True
    _LAST_OK = time.time()


def mark_disconnected() -> None:
    global _CONNECTED
    _CONNECTED = False


def heartbeat() -> None:
    global _LAST_OK
    _LAST_OK = time.time()


def is_deriv_healthy() -> bool:
    if not _CONNECTED:
        return False
    return (time.time() - _LAST_OK) < _TIMEOUT
