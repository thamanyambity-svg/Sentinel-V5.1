from datetime import date

_risk_state = {
    "trades_today": 0,
    "last_trade_day": None,
    "max_trades": 1,          # ⬅️ LIMITE RÉELLE
    "daily_pnl": 0.0,
    "max_daily_loss": -100.0,
}

def _rollover_if_new_day():
    today = date.today().isoformat()
    if _risk_state["last_trade_day"] != today:
        _risk_state["trades_today"] = 0
        _risk_state["last_trade_day"] = today

def get_risk_state():
    _rollover_if_new_day()
    return dict(_risk_state)

def can_execute_trade():
    _rollover_if_new_day()
    return _risk_state["trades_today"] < _risk_state["max_trades"]

def register_trade(pnl: float = 0.0):
    _rollover_if_new_day()
    _risk_state["trades_today"] += 1
    _risk_state["daily_pnl"] += pnl
