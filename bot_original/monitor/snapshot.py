"""
Snapshot global du bot.
Lecture seule.
Aucune logique métier.
"""

from bot.config.runtime import get_active_broker
from bot.config.real_gate import is_real_trading_enabled
from bot.config.kill_switch import is_trading_halted
from bot.config.shadow import is_shadow_enabled
from bot.state.pending import has_pending_trade
from bot.state.risk import get_risk_state
from bot.broker.deriv.health import is_deriv_healthy


def get_snapshot() -> dict:
    broker = get_active_broker()
    pending = has_pending_trade()

    snapshot = {
        "broker": broker,
        "real_trading": is_real_trading_enabled(),
        "kill_switch": is_trading_halted(),
        "shadow_mode": is_shadow_enabled(),
        "pending_trade": pending,
        "execution_phase": "PRE" if pending else "IDLE",
        "risk": get_risk_state(),
    }

    if broker == "deriv":
        snapshot["deriv_health"] = is_deriv_healthy()

    return snapshot
