import json, csv, os, math
from flask import Flask, jsonify, request, send_from_directory
from mt5_context import get_current_mt5_context
from schema_validation import (
    validate_ml_signal_payload,
    validate_status_payload,
    validate_trade_history_payload,
)

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))
MT5_PATH = os.environ.get("MT5_PATH", os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"))

# Initialisation du contexte
context_manager = get_current_mt5_context(MT5_PATH)

def find(f):
    for p in [os.path.join(BASE,f), os.path.join(MT5_PATH,f)]:
        if os.path.exists(p): return p
    return None

def rj(f):
    p = find(f)
    if not p: return None
    try:
        with open(p, encoding='utf-8') as h: return json.load(h)
    except: return None

def rj_validated(f, validator):
    data = rj(f)
    if data is None: return None, [f"{f} not found"]
    ok, errors = validator(data)
    return (data, []) if ok else (None, errors)

@app.route('/api/status')
def status():
    d, errors = rj_validated('status.json', validate_status_payload)
    if not d: return jsonify({"error": "status.json invalid", "details": errors}), 404
    ctx = context_manager.refresh()
    if ctx: d["context"] = ctx
    return jsonify(d)

@app.route('/api/ticks')
def ticks(): return jsonify(rj('ticks_v3.json') or [])

@app.route('/api/sentiment')
def sentiment():
    return jsonify(rj('gold_sentiment.json') or {"analysis":{"bias":"N/A","score":0,"summary":"En attente..."}})

@app.route('/api/learning_state')
def learning_state():
    return jsonify(rj('learning_state.json') or {})

@app.route('/api/history')
def history():
    d, _ = rj_validated('trade_history.json', validate_trade_history_payload)
    trades = d.get('trades', []) if d else []
    limit = int(request.args.get('limit', 200))
    return jsonify({'trades': trades[-limit:], 'total': len(trades)})

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
            "metrics": {"roi": 0, "roiPct": 0, "sharpe": 0, "profitFactor": 0, "kelly": 0, "drawdown": 0},
            "ai_verdict": rj('gold_sentiment.json') or {"bias":"NEUTRAL"},
            "version": "V7.25"
        })

    pnls = [float(t.get("pnl", 0)) for t in trades]
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p < 0]
    total_pnl = sum(pnls); gross_profit = sum(wins); gross_loss = abs(sum(losses))
    
    pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0
    wr = len(wins) / len(trades)
    
    # Sharpe Proxy
    avg_pnl = total_pnl / len(trades)
    std_pnl = math.sqrt(sum((p - avg_pnl)**2 for p in pnls) / len(trades)) if len(trades) > 1 else 1
    sharpe = round((avg_pnl / std_pnl) * math.sqrt(252), 2) if std_pnl > 0 else 0

    balance = float(st.get("balance", 0)) if isinstance(st, dict) else 0.0
    roi_pct = round((total_pnl / balance) * 100, 2) if balance > 0 else 0
    kelly = round(wr - ((1 - wr) / (pf if pf > 0 else 1)), 2)

    return jsonify({
        "account": st,
        "metrics": {
            "roi": round(total_pnl, 2), "roiPct": roi_pct, "sharpe": sharpe,
            "profitFactor": pf, "kelly": kelly, "drawdown": 0.0
        },
        "ai_verdict": rj('gold_sentiment.json') or {"bias":"NEUTRAL"},
        "ml_signal": ml_signal or {"status": "unavailable"},
        "version": "V7.25"
    })

@app.route('/api/gold_eod')
def gold_eod():
    d = rj('gold_analysis.json')
    if not d: return jsonify({"status": "unavailable"}), 404
    return jsonify(d)

@app.route('/api/gold_analysis')
def gold_analysis_old():
    return gold_eod()

@app.route('/api/stats')
def stats():
    d = rj('trade_history.json')
    if not d: return jsonify({'total_trades':0})
    trades = d.get('trades',[])
    if not trades: return jsonify({'total_trades':0})
    pnls = [float(t.get('pnl',0)) for t in trades]
    wins = [p for p in pnls if p>0]; losses = [p for p in pnls if p<=0]
    running=peak=max_dd=0; curve=[]
    for p in pnls:
        running+=p; peak=max(peak,running); max_dd=max(max_dd,peak-running)
        curve.append(round(running,2))
    return jsonify({
        'total_trades':len(trades),'wins':len(wins),'win_rate':round(len(wins)/len(trades)*100,1),
        'total_pnl':round(sum(pnls),2),'profit_factor':round(sum(wins)/abs(sum(losses)) if losses and sum(losses)!=0 else 0,2),
        'max_drawdown':round(max_dd,2),'equity_curve':curve
    })

@app.route('/api/v1/risk_os')
def risk_os_endpoint():
    data = rj('bot/risk/risk_state.json') or {"health_score":0}
    return jsonify({"status":"success", "data":data})

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(BASE, 'static'), filename)

@app.route('/')
def index():
    p = os.path.join(BASE, 'templates', 'dashboard.html')
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8') as f: return f.read()
    return "Dashboard not found", 404

if __name__ == '__main__':
    print('\n' + '═'*48 + '\n  ALADDIN PRO V7.25 — COMMAND CENTER ONLINE\n' + '═'*48 + '\n')
    app.run(debug=False, host='0.0.0.0', port=5000)

@app.route('/risk')
def risk_cockpit():
    p = find('static/risk_cockpit.html')
    if p:
        with open(p, 'r') as f: return f.read()
    return "Risk Cockpit not found", 404
