
def _normalize_status(result, reason=None):
    if reason:
        return {"status": "BLOCKED", "reason": reason}
    return result

from bot.config.runtime import get_active_broker
import os
from bot.config.shadow import is_shadow_enabled
from bot.config.flags import REAL_TRADING_ENABLED
from bot.config.kill_switch import is_trading_halted
from bot.state.pending import pop_pending_trade
from bot.state.risk import can_execute_trade, register_trade
from bot.monitor.health import get_health
from bot.monitor.logger import log_event, log_audit
from bot.broker.factory import get_broker

def run_orchestrator():
    # HARD GUARDS (runtime)
    if os.getenv("KILL_SWITCH") == "1":
        return {"status": "BLOCKED", "reason": "KILL_SWITCH_ACTIVE"}

    if os.getenv("FORCE_HEALTH_KO") == "1":
        return {"status": "BLOCKED", "reason": "HEALTH_NOT_OK"}

    log_event("orchestrator_start")
    # 🔴 KILL SWITCH GLOBAL
    if is_trading_halted():
        log_event("orchestrator_blocked", reason="KILL_SWITCH_ACTIVE")
        return {"status": "BLOCKED", "reason": "KILL_SWITCH_ACTIVE"}

    # 🩺 HEALTH CHECK
    if get_health() != "OK":
        return _normalize_status({}, "HEALTH_NOT_OK")
        log_event("orchestrator_blocked", reason="HEALTH_NOT_OK")
        return {"status": "BLOCKED", "reason": "HEALTH_NOT_OK"}

    trade = pop_pending_trade()
    if not trade:
        return {"status": "NO_TRADE"}

    broker_name = get_active_broker()
    shadow = is_shadow_enabled()

    # 🔒 VERROU RÉEL DERIV
    if broker_name == "deriv" and not shadow:
        if not REAL_TRADING_ENABLED:
            return {"status": "BLOCKED", "reason": "REAL_TRADING_DISABLED"}

        if not can_execute_trade():
            return {"status": "BLOCKED", "reason": "DAILY_TRADE_LIMIT_REACHED"}

    broker = get_broker(broker_name)
    log_audit("trade_execute", broker=broker_name, shadow=shadow)
    result = broker.execute(trade, shadow=shadow)

    if result.get("status") == "EXECUTED" and broker_name == "deriv" and not shadow:
        register_trade(result.get("pnl", 0.0))

    log_event("trade_result", status=result.get("status"))
    return result
