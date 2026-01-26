from bot.config.runtime import get_active_broker
from bot.config.shadow import is_shadow_enabled
from bot.config.flags import REAL_TRADING_ENABLED
from bot.config.kill_switch import is_trading_halted
from bot.monitor.health import get_health
from bot.state.pending import get_state

class InvariantViolation(Exception):
    pass


def check_invariants():
    """
    Vérifie les règles NON négociables du système.
    Lève InvariantViolation si incohérence.
    """

    # 1. Kill switch
    if is_trading_halted():
        raise InvariantViolation("KILL_SWITCH_ACTIVE")

    # 2. Santé globale
    if get_health() != "OK":
        raise InvariantViolation("HEALTH_NOT_OK")

    broker = get_active_broker()

    # 3. Deriv => shadow obligatoire
    if broker == "deriv" and not is_shadow_enabled():
        raise InvariantViolation("DERIV_REQUIRES_SHADOW")

    # 4. Trading réel interdit si flags off
    if REAL_TRADING_ENABLED and broker != "deriv":
        raise InvariantViolation("REAL_TRADING_ONLY_ALLOWED_ON_DERIV")

    # 5. Pending confirmé uniquement
    if get_state() == "PENDING":
        raise InvariantViolation("UNCONFIRMED_TRADE_PRESENT")
