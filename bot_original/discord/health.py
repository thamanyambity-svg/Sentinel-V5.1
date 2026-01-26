from bot.config.runtime import get_active_broker
from bot.state.deriv_flag import is_deriv_enabled
from bot.state.override import is_force_enabled
from bot.state.heartbeat import get_heartbeat, get_last_execution


def health_command():
    return (
        "🩺 **HEALTHCHECK**\n"
        f"Broker: {get_active_broker()}\n"
        f"Deriv: {'ON' if is_deriv_enabled() else 'OFF'}\n"
        f"Force: {'ON' if is_force_enabled() else 'OFF'}\n"
        f"Last heartbeat: {get_heartbeat()}\n"
        f"Last execution: {get_last_execution()}"
    )
