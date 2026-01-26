from bot.config.runtime import get_active_broker
from bot.state.deriv_flag import is_deriv_enabled

def broker_health():
    broker = get_active_broker()

    return {
        "active_broker": broker,
        "deriv_enabled": is_deriv_enabled(),
        "status": "OK"
    }
