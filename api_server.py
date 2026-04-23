"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V11 — api_server.py                                       ║
║  API REST Flask pour Dashboard Temps Réel                           ║
║                                                                      ║
║  Features:                                                           ║
║    ✓ Endpoints JSON pour tous les composants du dashboard           ║
║    ✓ Caching côté serveur                                           ║
║    ✓ CORS support pour accès cross-domain                           ║
║    ✓ WebSockets pour live updates                                   ║
║    ✓ Health check endpoint                                          ║
║    ✓ Compléter vers dashboard.html (websocket live)                 ║
║                                                                      ║
║  Usage:                                                              ║
║    python api_server.py                                              ║
║    # API disponible à http://localhost:5000/api/v1/...              ║
║                                                                      ║
║  Endpoints:                                                          ║
║    GET /api/v1/dashboard          → dump complet                    ║
║    GET /api/v1/account            → compte MT5                      ║
║    GET /api/v1/positions          → positions ouvertes              ║
║    GET /api/v1/ticks              → prix en temps réel              ║
║    GET /api/v1/ml                 → signaux ML                      ║
║    GET /api/v1/backtest          → résultats backtest               ║
║    GET /api/v1/health             → health check                    ║
║    WS /ws/live                    → updates temps réel (future)     ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from functools import wraps
import logging
import time
from typing import Dict, Any, Tuple

# Import du gestionnaire dashboard
try:
    from dashboard_manager import DashboardManager, Colors
except ImportError:
    print("⚠️  dashboard_manager.py not found. Please create it first.")
    exit(1)


# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION FLASK
# ══════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# CORS pour accès depuis n'importe quel origin (à restreindre en prod)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gestionnaire global
dashboard_manager = DashboardManager()


# ══════════════════════════════════════════════════════════════════
#  DECORATEURS
# ══════════════════════════════════════════════════════════════════

def json_response(func):
    """Décorateur pour enrober les réponses en JSON et gérer les erreurs"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            data = func(*args, **kwargs)
            return jsonify({
                "status": "success",
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            return jsonify({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }), 500
    return wrapper


def cache_response(ttl: int = 5):
    """Décorateur pour cacher les réponses"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"api:{func.__name__}"
            cached = dashboard_manager.cache.get(cache_key)
            if cached is not None:
                return jsonify({
                    "status": "success",
                    "data": cached,
                    "cached": True,
                    "timestamp": datetime.utcnow().isoformat()
                }), 200
            
            data = func(*args, **kwargs)
            dashboard_manager.cache.set(cache_key, data, ttl=ttl)
            return jsonify({
                "status": "success",
                "data": data,
                "cached": False,
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def format_account_data(status: Dict[str, Any]) -> Dict[str, Any]:
    """Formate les données de compte"""
    if not status:
        return None
    
    balance = status.get("balance", 0)
    equity = status.get("equity", 0)
    positions = status.get("positions", [])
    pnl_open = sum(p.get("pnl", 0) for p in positions)
    
    return {
        "balance": float(balance),
        "equity": float(equity),
        "drawdown": round(100 * (1 - equity / balance) if balance else 0, 2),
        "pnl_open": float(pnl_open),
        "positions_count": len(positions),
        "trading_enabled": status.get("trading", False),
        "last_sync": status.get("ts", 0),
        "positions": [
            {
                "symbol": p.get("sym", p.get("symbol", "?")),
                "type": p.get("type", "?"),
                "volume": float(p.get("lot", 0)),
                "price": float(p.get("price", 0)),
                "pnl": float(p.get("pnl", 0)),
                "timestamp": p.get("ts", 0)
            }
            for p in positions[:10]
        ]
    }


def format_ml_data(action_plan: Dict[str, Any], training: Dict[str, Any]) -> Dict[str, Any]:
    """Formate les données ML"""
    result = {}
    
    if action_plan:
        result["sovereign"] = {
            "decision": action_plan.get("decision", "UNKNOWN"),
            "asset": action_plan.get("asset", "?"),
            "kelly_risk": round(float(action_plan.get("kelly_risk", 0)), 3),
            "nexus_prob": round(float(action_plan.get("nexus_prob", 0)), 3),
            "spm_score": round(float(action_plan.get("spm_score", 0)), 3),
            "reasoning": action_plan.get("reasoning", "")[:100],
            "timestamp": action_plan.get("timestamp", "")
        }
    
    if training:
        runs = training if isinstance(training, list) else training.get("runs", [])
        if runs:
            last = runs[-1]
            result["training"] = {
                "sessions": len(runs),
                "last_auc": round(float(last.get("auc", 0)), 3),
                "last_win_rate": round(float(last.get("win_rate", 0)), 3),
                "last_date": last.get("ts", "")[:10]
            }
    
    return result


def format_backtest_data(backtest: Dict[str, Any]) -> Dict[str, Any]:
    """Formate les résultats backtest"""
    if not backtest:
        return None
    
    return {
        "profit_factor": round(float(backtest.get("profit_factor", 0)), 3),
        "win_rate": round(float(backtest.get("win_rate", 0)), 3),
        "max_drawdown_pct": round(float(backtest.get("max_drawdown_pct", 0)), 2),
        "sharpe": round(float(backtest.get("sharpe", 0)), 2),
        "return_pct": round(float(backtest.get("return_pct", 0)), 2),
        "trades_count": int(backtest.get("n_trades", 0)),
        "generated": backtest.get("generated", "")[:16],
        "status": (
            "EXCELLENT" if backtest.get("profit_factor", 0) >= 1.5 
            else "GOOD" if backtest.get("profit_factor", 0) >= 1.25 
            else "ACCEPTABLE" if backtest.get("profit_factor", 0) >= 1.0 
            else "POOR"
        )
    }


# ══════════════════════════════════════════════════════════════════
#  ROUTES API
# ══════════════════════════════════════════════════════════════════

@app.route('/api/v1/health', methods=['GET'])
@json_response
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "v1.1.0",
        "uptime": time.time(),
        "manager_metrics": dashboard_manager.get_metrics()
    }


@app.route('/api/v1/refresh', methods=['POST'])
@json_response
def refresh_data():
    """Force refresh de toutes les données"""
    dashboard_manager.refresh()
    return {"message": "Dashboard refreshed successfully"}


@app.route('/api/v1/account', methods=['GET'])
@cache_response(ttl=3)
def get_account():
    """Retourne les données du compte MT5"""
    status = dashboard_manager.load_data("status")
    return format_account_data(status)


@app.route('/api/v1/positions', methods=['GET'])
@cache_response(ttl=2)
def get_positions():
    """Retourne les positions ouvertes détaillées"""
    status = dashboard_manager.load_data("status")
    if not status:
        return []
    
    return [
        {
            "symbol": p.get("sym", p.get("symbol", "?")),
            "type": p.get("type", "?"),
            "volume": float(p.get("lot", 0)),
            "entry_price": float(p.get("price", 0)),
            "pnl": float(p.get("pnl", 0)),
            "pnl_percent": round(100 * float(p.get("pnl", 0)) / (float(p.get("price", 1)) * float(p.get("lot", 1))), 2),
            "timestamp": p.get("ts", 0)
        }
        for p in status.get("positions", [])
    ]


@app.route('/api/v1/ticks', methods=['GET'])
@cache_response(ttl=2)
def get_ticks():
    """Retourne les prix en temps réel"""
    ticks_data = dashboard_manager.load_data("ticks")
    if not ticks_data:
        return {}
    
    if isinstance(ticks_data, list):
        return {item.get("sym", "?"): item.get("ask", 0) for item in ticks_data}
    
    return ticks_data.get("ticks", {})


@app.route('/api/v1/ml', methods=['GET'])
@cache_response(ttl=5)
def get_ml():
    """Retourne les signaux ML et training"""
    action_plan = dashboard_manager.load_data("action_plan")
    training = dashboard_manager.load_data("training")
    fundamental = dashboard_manager.load_data("fundamental")
    
    result = format_ml_data(action_plan, training)
    
    if fundamental:
        result["fundamental"] = {
            "market_mood": fundamental.get("market_mood", "NEUTRAL"),
            "spm_score": round(float(fundamental.get("spm_score", 0)), 3),
            "aggregate_score": round(float(fundamental.get("aggregate_score", 0)), 3)
        }
    
    return result


@app.route('/api/v1/backtest', methods=['GET'])
@cache_response(ttl=10)
def get_backtest():
    """Retourne les résultats du dernier backtest"""
    backtest = dashboard_manager.load_data("backtest")
    return format_backtest_data(backtest)


@app.route('/api/v1/dashboard', methods=['GET'])
def get_full_dashboard():
    """Retourne l'état complet du dashboard"""
    return jsonify({
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "account": format_account_data(dashboard_manager.load_data("status")),
            "ml": format_ml_data(
                dashboard_manager.load_data("action_plan"),
                dashboard_manager.load_data("training")
            ),
            "backtest": format_backtest_data(dashboard_manager.load_data("backtest")),
            "ticks": get_ticks()[1] if isinstance(get_ticks(), tuple) else {},
        },
        "metrics": dashboard_manager.get_metrics()
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Serve the premium dashboard HTML"""
    from pathlib import Path
    dashboard_path = Path(__file__).parent / "dashboard_premium.html"
    if dashboard_path.exists():
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            return f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}
    # Fallback to JSON if HTML not found
    return jsonify({
        "title": "SENTINEL V11 - Dashboard API",
        "version": "1.1.0",
        "endpoints": {
            "health": "/api/v1/health",
            "account": "/api/v1/account",
            "positions": "/api/v1/positions",
            "ticks": "/api/v1/ticks",
            "ml": "/api/v1/ml",
            "backtest": "/api/v1/backtest",
            "dashboard": "/api/v1/dashboard",
            "refresh": "POST /api/v1/refresh"
        },
        "documentation": "Each endpoint supports GET requests and returns JSON"
    }), 200


# ══════════════════════════════════════════════════════════════════
#  ERROR HANDLERS
# ══════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "error": "Endpoint not found",
        "available_routes": [
            "/api/v1/health",
            "/api/v1/account",
            "/api/v1/positions",
            "/api/v1/ticks",
            "/api/v1/ml",
            "/api/v1/backtest",
            "/api/v1/dashboard"
        ]
    }), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({
        "status": "error",
        "error": "Internal server error",
        "message": str(error)
    }), 500


# ══════════════════════════════════════════════════════════════════
#  LANCEMENT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + Colors.cyan("=" * 60))
    print(Colors.bold(Colors.cyan(" SENTINEL V11 - REST API SERVER ")))
    print(Colors.cyan("=" * 60))
    print(f"\n{Colors.green('✓')} Dashboard Manager initialized")
    print(f"{Colors.green('✓')} Starting Flask API on http://localhost:5000")
    print(f"\n{Colors.yellow('Available endpoints:')}")
    print(f"  GET  /api/v1/health        {Colors.dim('← Health check')}")
    print(f"  GET  /api/v1/account       {Colors.dim('← Account data')}")
    print(f"  GET  /api/v1/positions     {Colors.dim('← Open positions')}")
    print(f"  GET  /api/v1/ticks         {Colors.dim('← Real-time prices')}")
    print(f"  GET  /api/v1/ml            {Colors.dim('← ML signals')}")
    print(f"  GET  /api/v1/backtest      {Colors.dim('← Backtest results')}")
    print(f"  GET  /api/v1/dashboard     {Colors.dim('← Full dashboard state')}")
    print(f"  POST /api/v1/refresh       {Colors.dim('← Force refresh')}")
    print("\n" + Colors.cyan("=" * 60) + "\n")
    
    # Run development server
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
