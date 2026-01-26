from bot.state.risk.limits import (
    get_trades_today,
    get_max_trades,
    get_daily_pnl,
    get_max_daily_loss,
)

def get_risk_state():
    """
    Snapshot lisible de l’état de risque.
    Lecture seule.
    """
    return {
        "trades_today": get_trades_today(),
        "max_trades": get_max_trades(),
        "daily_pnl": get_daily_pnl(),
        "max_daily_loss": get_max_daily_loss(),
    }
