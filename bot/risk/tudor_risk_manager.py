# risk/tudor_risk_manager.py
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

class TudorJonesRiskManager:
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.daily_high_watermark = initial_capital
        self.trade_history = []
        self.logger = logging.getLogger("TUDOR_RISK")
        
        # Paramètres Tudor Jones
        self.max_daily_loss_percent = 0.02  # 2% par jour
        self.max_weekly_loss_percent = 0.05  # 5% par semaine
        self.max_monthly_loss_percent = 0.10  # 10% par mois
        
        self.max_position_size_percent = 0.10  # 10% du capital
        self.max_correlation_exposure = 0.30  # 30% d'exposition corrélée
        
        self.consecutive_loss_limit = 5  # Limite de pertes consécutives
        self.current_consecutive_losses = 0
        
        self.volatility_adjustment_factor = 1.0
        
    def calculate_position_size(self, signal_strength: float, volatility_percent: float, 
                           stop_loss_percent: float) -> float:
        """Calcule la taille de position selon les règles Tudor Jones"""
        # Règle de base : 2% du capital par trade
        base_risk_amount = self.initial_capital * 0.02
        
        # Ajuster selon la force du signal
        risk_adjustment = 0.5 + (signal_strength * 0.5)  # 0.5 à 1.0
        adjusted_risk = base_risk_amount * risk_adjustment
        
        # Ajuster selon la volatilité
        if volatility_percent > 0.25:  # Haute volatilité
            self.volatility_adjustment_factor = 0.7
        elif volatility_percent < 0.15:  # Basse volatilité
            self.volatility_adjustment_factor = 1.3
        
        final_risk = adjusted_risk * self.volatility_adjustment_factor
        
        # Calculer la taille de position
        # Position = RiskAmount / SL_Percent
        if stop_loss_percent <= 0:
             # Safety fallback
             return 0.0

        position_size = final_risk / stop_loss_percent
        
        # Appliquer les limites
        max_position_size = self.current_capital * self.max_position_size_percent
        position_size = min(position_size, max_position_size)
        
        return position_size
    
    def check_risk_limits(self, current_date: datetime) -> Dict[str, bool]:
        """Vérifie toutes les limites de risque"""
        risk_status = {
            'daily_limit_ok': True,
            'weekly_limit_ok': True,
            'monthly_limit_ok': True,
            'consecutive_loss_limit_ok': True,
            'correlation_limit_ok': True
        }
        
        # Calculer les pertes sur différentes périodes
        recent_trades = self._get_recent_trades(current_date)
        
        # Perte journalière
        daily_pnl = sum(t['profit'] for t in recent_trades 
                        if (current_date - t['date']).days <= 1)
        daily_loss_percent = abs(daily_pnl) / self.current_capital if daily_pnl < 0 else 0
        risk_status['daily_limit_ok'] = daily_loss_percent < self.max_daily_loss_percent
        
        # Perte hebdomadaire
        weekly_pnl = sum(t['profit'] for t in recent_trades 
                         if (current_date - t['date']).days <= 7)
        weekly_loss_percent = abs(weekly_pnl) / self.current_capital if weekly_pnl < 0 else 0
        risk_status['weekly_limit_ok'] = weekly_loss_percent < self.max_weekly_loss_percent
        
        # Perte mensuelle
        monthly_pnl = sum(t['profit'] for t in recent_trades 
                          if (current_date - t['date']).days <= 30)
        monthly_loss_percent = abs(monthly_pnl) / self.current_capital if monthly_pnl < 0 else 0
        risk_status['monthly_limit_ok'] = monthly_loss_percent < self.max_monthly_loss_percent
        
        # Pertes consécutives
        if recent_trades:
            last_trades = sorted(recent_trades, key=lambda x: x['date'], reverse=True)
            consecutive_losses = 0
            for trade in last_trades:
                if trade['profit'] < 0:
                    consecutive_losses += 1
                else:
                    break
            
            risk_status['consecutive_loss_limit_ok'] = consecutive_losses < self.consecutive_loss_limit
            self.current_consecutive_losses = consecutive_losses
        
        # Vérifier l'exposition corrélée
        correlation_exposure = self._calculate_correlation_exposure(recent_trades)
        risk_status['correlation_limit_ok'] = correlation_exposure < self.max_correlation_exposure
        
        return risk_status
    
    def _get_recent_trades(self, current_date: datetime, days: int = 90) -> List[Dict]:
        """Récupère les trades récents"""
        cutoff_date = current_date - timedelta(days=days)
        return [t for t in self.trade_history if t['date'] >= cutoff_date]
    
    def _calculate_correlation_exposure(self, trades: List[Dict]) -> float:
        """Calcule l'exposition aux corrélations"""
        if len(trades) < 2:
            return 0.0
        
        # Calculer la matrice de corrélation des rendements
        symbols = list(set([t['symbol'] for t in trades]))
        returns_matrix = {}
        
        for symbol in symbols:
            symbol_trades = [t for t in trades if t['symbol'] == symbol]
            # Need return per trade
            returns = [t['return'] for t in symbol_trades]
            if len(returns) > 1:
                returns_matrix[symbol] = returns
        
        # Calculer la corrélation moyenne
        correlations = []
        valid_symbols = list(returns_matrix.keys())
        
        for i, symbol1 in enumerate(valid_symbols):
            for j, symbol2 in enumerate(valid_symbols[i+1:], i+1):
                # We need aligned time series for proper correlation, 
                # but for simplicity here we assume sequential lists or padded
                # This is a robust estimation placeholder
                r1 = returns_matrix[symbol1]
                r2 = returns_matrix[symbol2]
                
                min_len = min(len(r1), len(r2))
                if min_len > 2:
                     corr = np.corrcoef(r1[:min_len], r2[:min_len])[0, 1]
                     if not np.isnan(corr):
                         correlations.append(abs(corr))
        
        return np.mean(correlations) if correlations else 0.0
    
    def should_stop_trading(self, risk_status: Dict[str, bool]) -> Tuple[bool, str]:
        """Détermine si le trading doit être arrêté"""
        stop_reasons = []
        
        if not risk_status['daily_limit_ok']:
            stop_reasons.append("Daily loss limit reached")
        
        if not risk_status['weekly_limit_ok']:
            stop_reasons.append("Weekly loss limit reached")
        
        if not risk_status['monthly_limit_ok']:
            stop_reasons.append("Monthly loss limit reached")
        
        if not risk_status['consecutive_loss_limit_ok']:
            stop_reasons.append(f"Consecutive loss limit reached ({self.current_consecutive_losses} losses)")
        
        if not risk_status['correlation_limit_ok']:
            stop_reasons.append("Correlation exposure limit reached")
        
        should_stop = len(stop_reasons) > 0
        return should_stop, ", ".join(stop_reasons)
    
    def record_trade(self, symbol: str, entry_price: float, exit_price: float, 
                   profit: float, signal_type: str):
        """Enregistre un trade dans l'historique"""
        trade = {
            'date': datetime.now(),
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'profit': profit,
            'return': profit / entry_price if entry_price != 0 else 0,
            'signal_type': signal_type
        }
        
        self.trade_history.append(trade)
        
        # Mettre à jour le capital
        self.current_capital += profit
        
        # Mettre à jour le high water mark
        if self.current_capital > self.daily_high_watermark:
            self.daily_high_watermark = self.current_capital
        
        # Logger le trade
        profit_color = "🟢" if profit > 0 else "🔴"
        self.logger.info(f"{profit_color} Trade: {signal_type} {symbol} | P&L: ${profit:.2f}")
    
    def get_risk_report(self) -> str:
        """Génère un rapport de risque"""
        if not self.trade_history:
            return "No trades recorded yet"
        
        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t['profit'] > 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        total_profit = sum(t['profit'] for t in self.trade_history)
        avg_profit = total_profit / total_trades if total_trades > 0 else 0
        
        # Calculer le drawdown actuel
        current_drawdown = (self.daily_high_watermark - self.current_capital) / self.daily_high_watermark
        
        report = f"""
TUDOR JONES RISK REPORT
{'='*50}
Current Capital: ${self.current_capital:,.2f}
Total Profit/Loss: ${total_profit:,.2f}
Win Rate: {win_rate:.1%}
Average Profit/Trade: ${avg_profit:.2f}
Current Drawdown: {current_drawdown:.1%}
Daily High Water Mark: ${self.daily_high_watermark:,.2f}
Total Trades: {total_trades}
"""
        
        return report

# Mock StrategyManager for Dashboard
class TudorJonesStrategyManager:
     def __init__(self, market_data):
          pass
     def get_combined_signals(self):
          return []
     def get_strategy_performance(self):
          return {}
