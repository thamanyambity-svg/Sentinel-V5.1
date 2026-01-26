"""
Watchdog Deriv : reconnexion automatique WS
"""
import time
import threading

from bot.monitor.health import get_health
from bot.config.runtime import get_active_broker
from bot.broker.deriv.client import DerivClient
from bot.broker.deriv.health import mark_disconnected

_RETRY_DELAY = 5  # secondes
_running = False


def _loop():
    global _running
    while _running:
        try:
            if get_active_broker() == "deriv" and get_health() != "OK":
                try:
                    client = DerivClient()
                    client.connect()
                    client.close()
                except Exception:
                    mark_disconnected()
        finally:
            time.sleep(_RETRY_DELAY)


def start_deriv_watchdog():
    global _running
    if _running:
        return

    _running = True
    t = threading.Thread(target=_loop, daemon=True)
    t.start()


def stop_deriv_watchdog():
    global _running
    _running = False
