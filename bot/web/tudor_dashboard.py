# web/tudor_dashboard.py
from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import plotly.graph_objs as go
import plotly.express as px
from typing import Dict, List
import sys
import os

# Ensure bot modules are in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from bot.strategies.tudor_jones.ml_enhanced import TudorJonesMLEnhancer
    from bot.strategies.tudor_jones.backtester import TudorJonesBacktester
    from bot.risk.tudor_risk_manager import TudorJonesRiskManager, TudorJonesStrategyManager
except ImportError as e:
    print(f"Import Error: {e}") 
    # Fallback/Mock classes if real ones not found in path for quick UI testing...
    # But we expect them to exist now.

app = Flask(__name__, template_folder='templates')

class TudorJonesDashboard:
    def __init__(self):
        self.strategy_manager = None
        self.risk_manager = None
        self.ml_enhancer = None
        self.backtester = None
    
    def initialize_components(self):
        """Initialise tous les composants"""
        # Charger les données - Mock for now / Real implementation would hook to MT5 Data
        market_data = self.load_market_data()
        
        # Initialiser les composants
        self.strategy_manager = TudorJonesStrategyManager(market_data)
        self.risk_manager = TudorJonesRiskManager(initial_capital=100000)
        self.ml_enhancer = TudorJonesMLEnhancer(market_data)
        self.backtester = TudorJonesBacktester(market_data)
    
    def load_market_data(self) -> pd.DataFrame:
        """Charge les données de marché (exemple)"""
        # Dans la vraie application, ceci viendrait de votre base de données
        dates = pd.date_range(start='2020-01-01', end=datetime.now(), freq='D')
        np.random.seed(42)
        
        data = pd.DataFrame({
            'open': np.random.uniform(100, 110, len(dates)),
            'high': np.random.uniform(110, 120, len(dates)),
            'low': np.random.uniform(90, 100, len(dates)),
            'close': np.random.uniform(100, 110, len(dates)),
            'volume': np.random.uniform(1000000, 5000000, len(dates))
        }, index=dates)
        
        return data

dashboard = TudorJonesDashboard()

@app.route('/')
def index():
    """Page principale du dashboard"""
    return render_template('tudor_dashboard.html')

@app.route('/api/current_signals')
def get_current_signals():
    """API pour les signaux actuels"""
    if not dashboard.strategy_manager:
        return jsonify({'error': 'Strategy manager not initialized'})
    
    signals = dashboard.strategy_manager.get_combined_signals()
    
    # Formater pour le frontend
    formatted_signals = []
    for signal in signals:
        formatted_signals.append({
            'strategy': getattr(signal, 'strategy_name', 'Unknown'),
            'symbol': getattr(signal, 'symbol', 'Unknown'),
            'action': getattr(signal, 'action', 'HOLD'),
            'strength': getattr(signal, 'strength', 0),
            'confidence': getattr(signal, 'confidence', 0),
            'timestamp': datetime.now().isoformat()
        })
    
    # Mock data for UI if empty
    if not formatted_signals:
         formatted_signals = [
              {'strategy': 'Tudor Reversal', 'symbol': 'EURUSD', 'action': 'BUY', 'strength': 0.85, 'confidence': 0.9, 'timestamp': datetime.now().isoformat()},
              {'strategy': 'Volatility Breakout', 'symbol': 'GOLD', 'action': 'SELL', 'strength': 0.75, 'confidence': 0.8, 'timestamp': datetime.now().isoformat()}
         ]

    return jsonify(formatted_signals)

@app.route('/api/performance')
def get_performance():
    """API pour les performances"""
    if not dashboard.risk_manager:
        return jsonify({'error': 'Risk manager not initialized'})
    
    return jsonify({
        'risk_report': dashboard.risk_manager.get_risk_report(),
        'strategy_performance': {} # dashboard.strategy_manager.get_strategy_performance()
    })

@app.route('/api/portfolio')
def get_portfolio():
    """API pour l'état du portefeuille"""
    if not dashboard.risk_manager:
        return jsonify({'error': 'Risk manager not initialized'})
    
    # Mock positions for now, real implementation needs Position tracker
    positions = {} 
    
    return jsonify({
        'positions': positions,
        'allocation': {},
        'total_value': dashboard.risk_manager.current_capital
    })

@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    """API pour lancer un backtest"""
    try:
        data = request.get_json()
        if not data:
             data = {'start_date': '2023-01-01', 'end_date': '2023-12-31'}

        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        
        # Lancer le backtest
        result = dashboard.backtester.backtest_tudor_reversal(start_date, end_date)
        
        return jsonify({
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown,
            'win_rate': result.win_rate
        })
    except Exception as e:
         return jsonify({'error': str(e)})

@app.route('/api/ml_predictions')
def get_ml_predictions():
    """API pour les prédictions ML"""
    if not dashboard.ml_enhancer:
        return jsonify({'error': 'ML enhancer not initialized'})
    
    try:
        current_data = dashboard.ml_enhancer.market_data.iloc[-1:]
        predictions = dashboard.ml_enhancer.predict_tudor_signals(current_data)
        return jsonify(predictions)
    except Exception as e:
         return jsonify({'error': str(e)})

if __name__ == '__main__':
    dashboard.initialize_components()
    app.run(debug=True, host='0.0.0.0', port=5000)
