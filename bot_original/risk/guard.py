from datetime import datetime, timezone

# RÈGLES HARD
MAX_TRADES_PER_DAY = 5
MAX_LOSING_STREAK = 3
MAX_DAILY_DRAWDOWN = -3.0
MIN_EXPECTANCY = 0.0
MIN_WIN_RATE = 55.0
MIN_SAMPLES = 50

def _today_utc():
    return datetime.now(timezone.utc).date()

def _trade_date(ts):
    # accepte int (epoch) ou str (iso)
    if isinstance(ts, int):
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()
    if isinstance(ts, str):
        return datetime.fromisoformat(ts).date()
    return None

def guard(trades, stats):
    if not trades:
        return {"allowed": True, "reason": "Aucun trade enregistré"}

    today = _today_utc()

    trades_today = [
        t for t in trades
        if _trade_date(t.get("timestamp")) == today
    ]

    if len(trades_today) >= MAX_TRADES_PER_DAY:
        return {"allowed": False, "reason": "Limite trades journaliers atteinte"}

    if stats["losing_streak"] >= MAX_LOSING_STREAK:
        return {"allowed": False, "reason": "Série de pertes consécutives atteinte"}

    if stats["daily_dd"] <= MAX_DAILY_DRAWDOWN:
        return {"allowed": False, "reason": "Drawdown journalier dépassé"}

    if stats["samples"] < MIN_SAMPLES:
        return {"allowed": False, "reason": "Échantillon statistique insuffisant"}

    if stats["win_rate"] < MIN_WIN_RATE:
        return {"allowed": False, "reason": "Win rate insuffisant"}

    if stats["expectancy"] <= MIN_EXPECTANCY:
        return {"allowed": False, "reason": "Expectancy négative ou nulle"}

    return {"allowed": True, "reason": "Conditions de risque respectées"}
