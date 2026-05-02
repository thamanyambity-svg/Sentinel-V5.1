@app.route('/api/v1/trading_data')
def trading_data():
    """Unified endpoint for the portal stats — Elite V7.25"""
    st = rj('status.json')
    history = rj('trade_history.json') or {"trades":[]}
    trades = history.get("trades", [])
    ml_signal = rj('ml_signal.json')

    if not trades:
        return jsonify({
            "account": st,
            "metrics": {"roi": 0, "roiPct": 0, "sharpe": 0, "profitFactor": 0, "kelly": 0, "drawdown": 0, "drawdownPct": 0},
            "ai_verdict": rj('gold_sentiment.json') or {"bias":"NEUTRAL"},
            "version": "V7.25"
        })

    pnls = [float(t.get("pnl", 0)) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    
    total_pnl = sum(pnls)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0
    win_rate = len(wins) / len(trades) if trades else 0
    
    # Sharpe Proxy
    import math
    avg_pnl = total_pnl / len(trades)
    std_pnl = math.sqrt(sum((p - avg_pnl)**2 for p in pnls) / len(trades)) if len(trades) > 1 else 1
    sharpe = round((avg_pnl / std_pnl) * math.sqrt(252), 2) if std_pnl > 0 else 0

    balance = 0.0
    if isinstance(st, dict):
        balance = float(st.get("balance") or st.get("equity") or 0.0)
    
    roi_pct = round((total_pnl / balance) * 100, 2) if balance > 0 else 0
    kelly = round(win_rate - ((1 - win_rate) / (profit_factor if profit_factor > 0 else 1)), 2)

    return jsonify({
        "account": st,
        "metrics": {
            "roi": round(total_pnl, 2),
            "roiPct": roi_pct,
            "sharpe": sharpe,
            "profitFactor": profit_factor,
            "kelly": kelly,
            "drawdown": 0.0,
            "drawdownPct": 0.0
        },
        "ai_verdict": rj('gold_sentiment.json') or {"bias":"NEUTRAL"},
        "ml_signal": ml_signal or {"status": "unavailable"},
        "version": "V7.25"
    })
