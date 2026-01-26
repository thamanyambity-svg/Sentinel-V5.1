"""
Health global du système
Lecture seule.
"""

from bot.config.runtime import get_active_broker
from bot.broker.deriv.health import is_deriv_healthy


def get_health() -> str:
    broker = get_active_broker()

    if broker == "deriv":
        return "OK" if is_deriv_healthy() else "DERIV_DOWN"

    return "OK"
