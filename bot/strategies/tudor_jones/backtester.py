# strategies/tudor_jones/backtester.py
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from dataclasses import dataclass

@dataclass
class BacktestResult:
    strategy_name: str
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    total_trades: int
    avg_profit_per_trade: float
    sortino_ratio: float

class TudorJonesBacktester:
    def __init__(self, market_data: pd.DataFrame, initial_capital: float = 100000):
        self.market_data = market_data
        self.initial_capital = initial_capital
        self.results = {}
        
    def backtest_tudor_reversal(self, start_date: datetime, end_date: datetime) -> BacktestResult:
        """Backtest la stratégie de retournement Tudor Jones"""
        # Ensure dates are in the index range
        try:
             data = self.market_data[start_date:end_date].copy()
        except KeyError:
             print("Date range not available in market data.")
             return BacktestResult("Error", 0,0,0,0,0,0,0,0,0)

        if data.empty:
             return BacktestResult("No Data", 0,0,0,0,0,0,0,0,0)

        
        # Identifier les patterns de retournement
        capitulation_days = self._identify_capitulation_days(data)
        morning_after_signals = self._identify_morning_after(data, capitulation_days)
        
        # Simuler les trades
        trades = []
        equity_curve = [self.initial_capital]
        current_capital = self.initial_capital
        
        for i in range(1, len(data)):
            if morning_after_signals.iloc[i]:
                # Entrée en achat
                entry_price = data['open'].iloc[i]
                stop_loss = entry_price * 0.98  # -2%
                take_profit = entry_price * 1.05  # +5%
                
                # Simuler jusqu'à sortie
                exit_price, exit_date, profit = self._simulate_trade(
                    data[i:], entry_price, stop_loss, take_profit, 'BUY'
                )
                
                if exit_price is not None:
                    # Calculate position size (simplified 2% risk)
                    risk_per_trade = current_capital * 0.02
                    # Position = Risk / (Entry - SL)
                    # Here we treat 'profit' as per-unit profit, so we need volume
                    # Volume = Risk / (Entry - SL) 
                    # Profit Real = Volume * (Exit - Entry)
                    
                    price_risk = entry_price - stop_loss
                    if price_risk > 0:
                         volume = risk_per_trade / price_risk
                         real_profit = volume * (exit_price - entry_price)
                    else:
                         real_profit = 0

                    trades.append({
                        'entry_date': data.index[i],
                        'exit_date': exit_date,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'profit': real_profit,
                        'return': real_profit / current_capital # Return on capital
                    })
                    current_capital += real_profit
                    equity_curve.append(current_capital)
        
        # Calculer les métriques
        if not trades:
            return BacktestResult("Tudor Reversal", 0, 0, 0, 1, 0, 0, 0, 0, 0)
        
        # Reconstruct equity series properly with dates
        # Note: simplistic equity curve, only updates on trade exit
        equity_series = pd.Series(equity_curve) 
        returns = equity_series.pct_change().dropna()
        
        total_return = (current_capital - self.initial_capital) / self.initial_capital
        days = (end_date - start_date).days
        if days > 0:
            annualized_return = (1 + total_return) ** (365 / days) - 1
        else:
            annualized_return = 0
            
        sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std() if returns.std() != 0 else 0
        max_drawdown = self._calculate_max_drawdown(equity_series)
        calmar_ratio = annualized_return / max_drawdown if max_drawdown != 0 else 0
        
        win_trades = sum(1 for t in trades if t['profit'] > 0)
        win_rate = win_trades / len(trades)
        avg_profit = np.mean([t['profit'] for t in trades])
        
        sortino_ratio = self._calculate_sortino_ratio(returns)
        
        return BacktestResult(
            strategy_name="Tudor Reversal",
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            total_trades=len(trades),
            avg_profit_per_trade=avg_profit,
            sortino_ratio=sortino_ratio
        )
    
    def _identify_capitulation_days(self, data: pd.DataFrame) -> pd.Series:
        """Identifie les jours de capitulation"""
        returns = data['close'].pct_change()
        # Handle cases where volume might be constant or NaN
        rolling_vol = data['volume'].rolling(50).mean()
        volume_spike = data['volume'] > rolling_vol * 2
        large_drop = returns < -0.04  # -4%
        
        return large_drop & volume_spike
    
    def _identify_morning_after(self, data: pd.DataFrame, capitulation_days: pd.Series) -> pd.Series:
        """Identifie les signaux 'morning after'"""
        signals = pd.Series(False, index=data.index)
        
        for i in range(1, len(data)):
            if capitulation_days.iloc[i-1]:  # Hier était capitulation
                # Vérifier si aujourd'hui est un 'morning after'
                gap_down = data['open'].iloc[i] < data['close'].iloc[i-1]
                green_close = data['close'].iloc[i] > data['open'].iloc[i]
                
                if gap_down and green_close:
                    signals.iloc[i] = True
        
        return signals
    
    def _simulate_trade(self, data: pd.DataFrame, entry_price: float, 
                       stop_loss: float, take_profit: float, direction: str) -> Tuple:
        """Simule un trade jusqu'à sortie"""
        for i in range(len(data)):
            current_price = data['close'].iloc[i]
            
            if direction == 'BUY':
                if current_price >= take_profit:
                    return take_profit, data.index[i], take_profit - entry_price
                elif current_price <= stop_loss:
                    return stop_loss, data.index[i], stop_loss - entry_price
            else:  # SELL
                if current_price <= take_profit:
                    return take_profit, data.index[i], entry_price - take_profit
                elif current_price >= stop_loss:
                    return stop_loss, data.index[i], entry_price - stop_loss
        
        return None, None, 0
    
    def _calculate_max_drawdown(self, equity_series: pd.Series) -> float:
        """Calcule le drawdown maximum"""
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        return abs(drawdown.min())
    
    def _calculate_sortino_ratio(self, returns: pd.Series) -> float:
        """Calcule le ratio de Sortino"""
        negative_returns = returns[returns < 0]
        if len(negative_returns) == 0:
            return 0
        
        downside_std = np.sqrt(np.mean(negative_returns ** 2))
        if downside_std == 0:
            return 0
        
        return np.sqrt(252) * returns.mean() / downside_std
    
    def generate_performance_report(self, results: List[BacktestResult]) -> str:
        """Génère un rapport de performance complet"""
        report = "TUDOR JONES BACKTEST REPORT\n"
        report += "=" * 50 + "\n\n"
        
        for result in results:
            report += f"Strategy: {result.strategy_name}\n"
            report += f"Total Return: {result.total_return:.2%}\n"
            report += f"Annualized Return: {result.annualized_return:.2%}\n"
            report += f"Sharpe Ratio: {result.sharpe_ratio:.3f}\n"
            report += f"Sortino Ratio: {result.sortino_ratio:.3f}\n"
            report += f"Max Drawdown: {result.max_drawdown:.2%}\n"
            report += f"Calmar Ratio: {result.calmar_ratio:.3f}\n"
            report += f"Win Rate: {result.win_rate:.1%}\n"
            report += f"Total Trades: {result.total_trades}\n"
            report += f"Avg Profit/Trade: ${result.avg_profit_per_trade:.2f}\n"
            report += "-" * 30 + "\n"
        
        return report
    
    def plot_equity_curves(self, results: Dict[str, pd.Series]):
        """Trace les courbes d'équité"""
        plt.figure(figsize=(12, 8))
        
        for strategy_name, equity_series in results.items():
            equity_series.plot(label=strategy_name)
        
        plt.title('Tudor Jones Strategies - Equity Curves')
        plt.xlabel('Date')
        plt.ylabel('Equity ($)')
        plt.legend()
        plt.grid(True)
        # plt.show() # Disabled for headless env
        plt.savefig("tudor_backtest_equity.png")

