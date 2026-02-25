import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Robust import for vectorbt
try:
    import vectorbt as vbt
    VBT_AVAILABLE = True
except ImportError:
    VBT_AVAILABLE = False
    print("⚠️ vectorbt not found. Backtesting running in limited mode.")

class ProfessionalBacktester:
    def __init__(self, data: pd.DataFrame, initial_capital: float = 10000):
        self.data = data
        self.initial_capital = initial_capital
        self.results = {}
        
        # Ensure data has datetime index
        if not isinstance(self.data.index, pd.DatetimeIndex):
            # Try to find a date column or assume numeric index is not checking dates
            pass

    def add_strategy(self, name: str, entries: pd.Series, exits: pd.Series):
        """Ajoute une stratégie au backtest"""
        if not VBT_AVAILABLE:
            print(f"❌ Cannot run strategy '{name}': vectorbt missing.")
            return

        try:
            portfolio = vbt.Portfolio.from_signals(
                close=self.data['close'],
                entries=entries,
                exits=exits,
                init_cash=self.initial_capital,
                fees=0.001,  # 0.1% transaction fee
                freq='1min'  # Default frequency
            )
            self.results[name] = portfolio
        except Exception as e:
            print(f"❌ Error adding strategy '{name}': {e}")

    def run_all_strategies(self) -> Dict[str, Any]:
        """Exécute tous les backtests et retourne les stats"""
        stats = {}
        for name, portfolio in self.results.items():
            try:
                # Basic stats
                stats[name] = portfolio.stats()
            except Exception as e:
                print(f"❌ Error calculating stats for '{name}': {e}")
        return stats

    def generate_report(self, stats: Dict) -> str:
        """Génère un rapport détaillé formatted string"""
        if not stats:
            return "No strategies tested or no results."
            
        report = ["📊 === BACKTEST REPORT === 📊"]
        for name, stat in stats.items():
            # Handle pandas Series output from vbt
            try:
                ret = stat.get('Total Return [%]', 0.0)
                sharpe = stat.get('Sharpe Ratio', 0.0)
                dd = stat.get('Max Drawdown [%]', 0.0)
                winrate = stat.get('Win Rate [%]', 0.0)
                trades = stat.get('Total Trades', 0)
                
                report.append(f"""
Strategy: {name}
-------------------------
Total Return: {ret:.2f}%
Sharpe Ratio: {sharpe:.2f}
Max Drawdown: {dd:.2f}%
Win Rate:     {winrate:.2f}%
Total Trades: {trades}
""")
            except Exception:
                # Fallback for raw output
                report.append(f"\nStrategy: {name}\n{stat}\n")
                
        return '\n'.join(report)

if __name__ == "__main__":
    # Test Data Generation
    print("🧪 Generating test data...")
    index = pd.date_range("2023-01-01", periods=1000, freq="1H")
    price = 100 + np.random.randn(1000).cumsum()
    market_data = pd.DataFrame({'close': price}, index=index)
    
    backtester = ProfessionalBacktester(market_data)
    
    if VBT_AVAILABLE:
        # RSI Strategy
        rsi = vbt.RSI.run(market_data['close'], window=14)
        rsi_entries = rsi.rsi_crossed_below(30)
        rsi_exits = rsi.rsi_crossed_above(70)
        backtester.add_strategy('RSI_Standard', rsi_entries, rsi_exits)
        
        # MACD Strategy
        macd = vbt.MACD.run(market_data['close'])
        macd_entries = macd.macd_above_signal()
        macd_exits = macd.macd_below_signal()
        backtester.add_strategy('MACD_Trend', macd_entries, macd_exits)
        
        stats = backtester.run_all_strategies()
        print(backtester.generate_report(stats))
    else:
        print("⏭️ Skipping vectorbt execution (module missing).")
