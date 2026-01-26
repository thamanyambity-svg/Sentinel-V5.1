"""
Risk rules engine
Décide si un trade peut être exécuté
"""

from bot.config.real_gate import is_real_trading_enabled
from bot.state.risk.limits import (
    get_trades_today,
    get_max_trades,
    get_daily_pnl,
    get_max_daily_loss,
    increment_trades,
    add_pnl,
)


def can_execute_trade(trade: dict):
    if not is_real_trading_enabled():
        return True, "SIMULATION_ALLOWED"

    if get_trades_today() >= get_max_trades():
        return False, "DAILY_TRADE_LIMIT_REACHED"

    if get_daily_pnl() <= get_max_daily_loss():
        return False, "MAX_DAILY_LOSS_REACHED"

    return True, "ALLOWED"


def register_trade(result: dict):
    increment_trades()
    add_pnl(result.get("pnl", 0.0))
