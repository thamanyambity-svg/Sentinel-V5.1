from bot.config.runtime import get_active_broker
from bot.config.strategy import get_active_strategy
from bot.state.pending import has_pending_trade
from bot.state.override import is_force_enabled
from bot.state.deriv_flag import is_deriv_enabled
from bot.state.risk import get_risk_state

def get_bot_status():
    """
    Snapshot global de l’état du bot.
    Lecture seule.
    """
    return {
        "broker": get_active_broker(),
        "strategy": get_active_strategy(),
        "pending_trade": has_pending_trade(),
        "force_mode": is_force_enabled(),
        "deriv_enabled": is_deriv_enabled(),
        "risk": get_risk_state(),
    }
