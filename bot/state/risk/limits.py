"""
Risk limits & counters
État persistant en mémoire (session)
"""

_TRADES_TODAY = 0
_MAX_TRADES = 5      # ← 5 trades réels / jour
_DAILY_PNL = 0.0
_MAX_DAILY_LOSS = -100.0


# =========================
# Getters
# =========================
def get_trades_today():
    return _TRADES_TODAY


def get_max_trades():
    return _MAX_TRADES


def get_daily_pnl():
    return _DAILY_PNL


def get_max_daily_loss():
    return _MAX_DAILY_LOSS


# =========================
# Mutators (INTERNES)
# =========================
def increment_trades():
    global _TRADES_TODAY
    _TRADES_TODAY += 1


def add_pnl(value: float):
    global _DAILY_PNL
    _DAILY_PNL += float(value)


def reset_daily_limits():
    global _TRADES_TODAY, _DAILY_PNL
    _TRADES_TODAY = 0
    _DAILY_PNL = 0.0
