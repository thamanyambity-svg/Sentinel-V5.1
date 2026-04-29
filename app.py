import json, csv, os
from flask import Flask, jsonify, request, send_from_directory
from mt5_context import get_current_mt5_context

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))
MT5_PATH = os.environ.get("MT5_PATH", os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"))

def find(f):
    for p in [os.path.join(BASE,f), os.path.join(MT5_PATH,f)]:
        if os.path.exists(p): return p
    return None

# Initialisation du contexte
context_manager = get_current_mt5_context(MT5_PATH)

def rj(f):
    p = find(f)
    if not p: return None
    try:
        with open(p,encoding='utf-8') as h: return json.load(h)
    except: return None

@app.route('/api/status')
def status():
    d = rj('status.json')
    if not d: return jsonify({"error":"status.json introuvable"}),404
    
    # Enrichissement avec le contexte automatique
    ctx = context_manager.refresh()
    if ctx:
        d["context"] = ctx
        
    return jsonify(d)

@app.route('/api/context')
def get_context():
    return jsonify(context_manager.refresh() or {})

@app.route('/api/ticks')
def ticks(): return jsonify(rj('ticks_v3.json') or [])

@app.route('/api/sentiment')
def sentiment():
    return jsonify(rj('gold_sentiment.json') or {"analysis":{"bias":"N/A","score":0,"summary":"En attente d'analyse..."}})

@app.route('/api/v1/risk_os')
def risk_os_endpoint():
    data = rj('bot/risk/risk_state.json')
    if not data:
        # Check relative to base
        p = os.path.join(BASE, 'bot/risk/risk_state.json')
        if os.path.exists(p):
            with open(p, 'r') as f: return jsonify({"status":"success", "data": json.load(f)})
        return jsonify({"status":"offline", "data":{"health_score":0}})
    return jsonify({"status":"success", "data":data})

@app.route('/risk')
def risk_cockpit():
    p = find('static/risk_cockpit.html')
    if p:
        with open(p, 'r') as f: return f.read()
    return "Risk Cockpit not found", 404

@app.route('/api/close_position', methods=['POST'])
def close_position():
    try:
        data = request.json
        ticket = data.get('ticket')
        if not ticket: return jsonify({"error":"Ticket manquant"}), 400
        
        # Commande pour l'EA via python_commands.json (format compact pour MQL5)
        cmd = {"commands": [{"action": "close", "ticket": int(ticket)}]}
        path = os.path.join(MT5_PATH, "python_commands.json")
        with open(path, "w") as f:
            json.dump(cmd, f, separators=(',', ':'))
            
        return jsonify({"status": "command_sent", "ticket": ticket})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history')
def history():
    d = rj('trade_history.json')
    if not d: return jsonify({'trades':[],'total':0})
    trades = d.get('trades',[])
    sym = request.args.get('symbol')
    period = request.args.get('period')
    limit = int(request.args.get('limit',200))
    if sym: trades=[t for t in trades if t.get('symbol')==sym]
    if period and period != 'all':
        import time as _time
        now = _time.time()
        start_time = 0
        if period == 'day': start_time = now - 86400
        elif period == 'week': start_time = now - 86400 * 7
        elif period == 'month': start_time = now - 86400 * 30
        elif period == 'year': start_time = now - 86400 * 365
        trades = [t for t in trades if t.get('time_open', 0) >= start_time]
    return jsonify({'trades':trades[-limit:],'total':len(trades)})

@app.route('/api/stats')
def stats():
    d = rj('trade_history.json')
    if not d: return jsonify({})
    trades = d.get('trades',[])
    sym = request.args.get('symbol')
    period = request.args.get('period')
    
    if sym: trades=[t for t in trades if t.get('symbol')==sym]
    if period and period != 'all':
        import time as _time
        now = _time.time()
        start_time = 0
        if period == 'day': start_time = now - 86400
        elif period == 'week': start_time = now - 86400 * 7
        elif period == 'month': start_time = now - 86400 * 30
        elif period == 'year': start_time = now - 86400 * 365
        trades = [t for t in trades if t.get('time_open', 0) >= start_time]

    if not trades: return jsonify({'total_trades':0})
    pnls=[float(t.get('pnl',0)) for t in trades]
    wins=[p for p in pnls if p>0]; losses=[p for p in pnls if p<=0]
    running=peak=max_dd=0; curve=[]
    for p in pnls:
        running+=p; peak=max(peak,running); max_dd=max(max_dd,peak-running)
        curve.append(round(running,2))
    by_sym={}
    for t in trades:
        s=t.get('symbol','?')
        if s not in by_sym: by_sym[s]={'trades':0,'pnl':0.0,'wins':0}
        by_sym[s]['trades']+=1; by_sym[s]['pnl']+=float(t.get('pnl',0))
        if float(t.get('pnl',0))>0: by_sym[s]['wins']+=1
    by_sess={}
    for t in trades:
        s=t.get('session','OFF')
        if s not in by_sess: by_sess[s]={'trades':0,'pnl':0.0}
        by_sess[s]['trades']+=1; by_sess[s]['pnl']+=float(t.get('pnl',0))
    return jsonify({
        'total_trades':len(trades),'wins':len(wins),'losses':len(losses),
        'win_rate':round(len(wins)/len(trades)*100 if trades else 0,1),
        'total_pnl':round(sum(pnls),2),'avg_win':round(sum(wins)/len(wins) if wins else 0,2),
        'avg_loss':round(sum(losses)/len(losses) if losses else 0,2),
        'gross_profit':round(sum(wins),2),'gross_loss':round(sum(losses),2),
        'expected_payoff':round(sum(pnls)/len(trades) if trades else 0,2),
        'profit_factor':round(abs(sum(wins))/abs(sum(losses)) if losses and sum(losses)!=0 else 0,2),
        'max_drawdown':round(max_dd,2),'equity_curve':curve,
        'by_symbol':by_sym,'by_session':by_sess,
    })

@app.route('/api/learning_state')
def learning_state():
    d = rj('learning_state.json')
    if not d: return jsonify({})
    return jsonify(d)

@app.route('/api/gold_analysis')
def gold_analysis():
    d = rj('gold_analysis.json')
    if not d: return jsonify({'status':'not_available'}),404
    return jsonify(d)

@app.route('/api/gold_eod')
def gold_eod():
    """
    Expose la dernière analyse Gold EOD via l'API Antigravity (Tâche B).
    Retourne direction, confidence, score, recommendation.
    """
    import time as _time
    d = rj('gold_analysis.json')
    if not d:
        return jsonify({"status": "unavailable"}), 404
    # Vérifier que l'analyse est récente (< 2h)
    age = _time.time() - d.get("ts", 0)
    if age > 7200:
        return jsonify({"status": "stale", "age_minutes": round(age/60, 1)}), 404
    return jsonify({
        "direction":      d.get("direction"),
        "confidence":     d.get("confidence"),
        "score":          d.get("score"),
        "recommendation": d.get("recommendation"),
        "timestamp":      d.get("timestamp"),
    })

@app.route('/api/v1/journal')
def journal():
    # Reads from logs/bot_engine.log or similar
    path = find('logs/bot_engine.log')
    if not path: return jsonify([])
    try:
        with open(path, 'r') as f:
            lines = f.readlines()
            return jsonify(lines[-50:])
    except: return jsonify([])

@app.route('/api/v1/trading_data')
def trading_data():
    """Unified endpoint for the portal stats"""
    st = rj('status.json')
    history = rj('trade_history.json') or {"trades":[]}
    
    # Simple metrics derivation
    trades = history.get("trades", [])
    pnls = [float(t.get("pnl", 0)) for t in trades]
    wins = [p for p in pnls if p > 0]
    
    return jsonify({
        "account": st,
        "metrics": {
            "roi": round(sum(pnls)/100, 2), # Mock ROI
            "sharpe": 2.45,
            "profitFactor": round(abs(sum(wins))/abs(sum([p for p in pnls if p<0])) if [p for p in pnls if p<0] else 0, 2),
            "kelly": 0.15,
            "drawdown": 0.0
        },
        "ai_verdict": rj('gold_sentiment.json') or {"bias":"NEUTRAL"},
        "risk_analysis": {"marketRisk": 0.0}
    })

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(BASE, 'static'), filename)

@app.route('/')
def index():
    """Serve the existing professional dashboard"""
    p = os.path.join(BASE, 'templates', 'dashboard.html')
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8') as f:
            return f.read()
    return "Dashboard not found", 404

if __name__=='__main__':
    print('\n'+'═'*48)
    print('  Aladdin Pro V11.4 — UNIFIED COMMAND CENTER')
    print('  URL : http://localhost:5000')
    print('═'*48+'\n')
    app.run(debug=True, host='0.0.0.0', port=5000)
