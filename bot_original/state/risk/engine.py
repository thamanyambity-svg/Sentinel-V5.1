from bot.state.risk.rules.max_trades import check_max_trades
from bot.state.risk.rules.max_loss import check_max_loss

RISK_RULES = [
    check_max_trades,
    check_max_loss,
]

def can_execute_trade(trade):
    """
    Retourne toujours (allowed: bool, reason: str | None)
    """
    for rule in RISK_RULES:
        allowed, reason = rule(trade)
        if not allowed:
            return False, reason
    return True, None
