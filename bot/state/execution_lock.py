import time
from threading import Lock

_EXECUTION_LOCK = Lock()
_LOCK_TS = None


def acquire_lock():
    """
    Tente d'acquérir le lock d'exécution.
    Retourne True si acquis, False sinon.
    """
    global _LOCK_TS
    acquired = _EXECUTION_LOCK.acquire(blocking=False)
    if acquired:
        _LOCK_TS = time.time()
    return acquired


def release_lock():
    """
    Libère le lock si détenu.
    """
    global _LOCK_TS
    if _EXECUTION_LOCK.locked():
        _EXECUTION_LOCK.release()
    _LOCK_TS = None


def lock_status():
    """
    État du lock pour debug / healthcheck.
    """
    return {
        "locked": _EXECUTION_LOCK.locked(),
        "since": _LOCK_TS
    }
