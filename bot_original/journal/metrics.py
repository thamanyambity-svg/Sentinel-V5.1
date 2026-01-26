def _valid_trades(trades):
    """Filtre les trades valides contenant un pnl numérique."""
    return [
        t for t in trades
        if isinstance(t, dict) and "pnl" in t and isinstance(t["pnl"], (int, float))
    ]

def win_rate(trades):
    trades = _valid_trades(trades)
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t["pnl"] > 0)
    return round((wins / len(trades)) * 100, 2)

def expectancy(trades):
    trades = _valid_trades(trades)
    if not trades:
        return 0.0
    total = sum(t["pnl"] for t in trades)
    return round(total / len(trades), 4)

def max_drawdown(trades):
    trades = _valid_trades(trades)
    if not trades:
        return 0.0

    equity = 0
    peak = 0
    max_dd = 0

    for t in trades:
        equity += t["pnl"]
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)

    return round(max_dd, 4)
