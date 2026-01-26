from bot.state.risk.limits import get_daily_pnl, get_max_daily_loss


def check_max_loss(trade):
    """
    Vérifie si la perte journalière maximale est dépassée.
    """
    if get_daily_pnl() <= get_max_daily_loss():
        return False, "MAX_DAILY_LOSS_REACHED"
    return True, None
