from datetime import datetime, timezone
from collections import defaultdict

def _is_today(timestamp):
    dt = datetime.fromisoformat(timestamp)
    return dt.date() == datetime.now(timezone.utc).date()

def _valid_trades(trades):
    return [
        t for t in trades
        if isinstance(t, dict)
        and "pnl" in t
        and "timestamp" in t
        and isinstance(t["pnl"], (int, float))
    ]

def series_status(trades):
    """
    Analyse la série de trading et décide si le trading est autorisé.
    Retourne un dict structuré.
    """

    trades = _valid_trades(trades)

    today_trades = [t for t in trades if _is_today(t["timestamp"])]

    trades_today = len(today_trades)

    # Drawdown journalier
    daily_pnl = sum(t["pnl"] for t in today_trades)

    # Série de pertes en cours (on part du plus récent)
    losing_streak = 0
    for t in reversed(trades):
        if t["pnl"] < 0:
            losing_streak += 1
        else:
            break

    # Décision
    allowed = True
    reason = "Conditions OK"

    if trades_today >= 5:
        allowed = False
        reason = "Nombre maximum de trades atteint"

    elif losing_streak >= 2:
        allowed = False
        reason = "Série de pertes consécutives atteinte"

    elif daily_pnl <= -3:
        allowed = False
        reason = "Drawdown journalier maximal atteint"

    return {
        "allowed": allowed,
        "reason": reason,
        "trades_today": trades_today,
        "losing_streak": losing_streak,
        "daily_drawdown": round(daily_pnl, 2)
    }
