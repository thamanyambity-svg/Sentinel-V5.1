from bot.state.risk.limits import get_trades_today, get_max_trades


def check_max_trades(trade):
    """
    Vérifie si le nombre de trades journaliers est dépassé.
    Retourne (allowed: bool, reason: str | None)
    """
    if get_trades_today() >= get_max_trades():
        return False, "MAX_TRADES_REACHED"
    return True, None
