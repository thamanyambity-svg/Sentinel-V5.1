"""
Verrou processus : un seul pilote Sentinel peut tourner.
Utilise un fichier lock avec PID (évite doublons et orphelins).
"""
import os
import atexit
import logging

logger = logging.getLogger("PROCESS_LOCK")

LOCK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sentinel_v5.lock")


def _is_process_running(pid: int) -> bool:
    """Vérifie si le processus pid est encore actif (Unix)."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire():
    """Prend le lock. Retourne True si acquis, False si un autre pilote tourne."""
    global _lock_acquired
    try:
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, "r") as f:
                    old_pid = int(f.read().strip())
            except (ValueError, OSError):
                old_pid = None
            if old_pid is not None and _is_process_running(old_pid):
                logger.warning("Another Sentinel is already running (PID %s). Exiting.", old_pid)
                return False
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        _lock_acquired = True
        logger.info("Process lock acquired (PID %s)", os.getpid())
        return True
    except Exception as e:
        logger.error("Failed to acquire lock: %s", e)
        return False


def release():
    """Relâche le lock (appelé à la sortie)."""
    global _lock_acquired
    try:
        if _lock_acquired and os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, "r") as f:
                if f.read().strip() == str(os.getpid()):
                    os.remove(LOCK_FILE)
            _lock_acquired = False
            logger.info("Process lock released.")
    except Exception as e:
        logger.debug("Lock release: %s", e)


_lock_acquired = False
atexit.register(release)
