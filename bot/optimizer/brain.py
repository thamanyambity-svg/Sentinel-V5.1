
import sqlite3
import pandas as pd
import numpy as np
import logging
import json
import os
from typing import Dict, List, Tuple

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [OPTIMIZER] - %(message)s')
logger = logging.getLogger("OPTIMIZER")

class OptimizerBrain:
    """
    🧠 THE EVOLUTIONARY BRAIN
    Objective: Find the 'Champion' parameter set for next week.
    Source: bot/data/sentinel.db (Instrumentation Phase 0)
    """
    
    def __init__(self, db_path="bot/data/sentinel.db"):
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            logger.error(f"❌ DB not found at {self.db_path}. Run Phase 0 first.")
            
    def load_history(self, asset="1HZ100V", days=7):
        """Fetch last X days of M1 data from SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            # Epoch math: 86400 seconds per day
            cutoff = pd.Timestamp.now().timestamp() - (days * 86400)
            
            query = f"""
                SELECT epoch, open, high, low, close, volume 
                FROM market_data 
                WHERE asset = '{asset}' AND epoch > {cutoff}
                ORDER BY epoch ASC
            """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                logger.warning(f"⚠️ No data found for {asset} in last {days} days.")
                return None
                
            logger.info(f"📥 Loaded {len(df)} candles for {asset}.")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error loading history: {e}")
            return None

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def backtest_strategy(self, df, rsi_period=14, buy_threshold=30, sell_threshold=70):
        """
        Fast Vectorized Backtest
        Returns: { 'trades': X, 'winrate': %, 'profit_factor': Y }
        """
        df = df.copy()
        
        # 1. Compute Indicators
        df['rsi'] = self.calculate_rsi(df['close'], rsi_period)
        
        # 2. Logic (Simplified Project 100)
        # Buy: RSI < buy_threshold
        # Sell: RSI > sell_threshold
        
        df['signal'] = 0
        df.loc[df['rsi'] < buy_threshold, 'signal'] = 1  # BUY
        df.loc[df['rsi'] > sell_threshold, 'signal'] = -1 # SELL
        
        # 3. Simulate Execution (next candle open)
        # Shift signal by 1 so we enter on next candle
        df['position'] = df['signal'].shift(1)
        
        # Return = (Close - Open) * Position
        # If BUY (1), we want Close > Open
        # If SELL (-1), we want Open > Close => (Open - Close) -> -(Close - Open)
        
        # Simple assumption: Hold for 1 candle (Scalping)
        # Improvement: Hold until RSI reverse or TP/SL
        
        # For 'Project 100', we often exit quickly. Let's assume 3-candle hold or reversal.
        # MVP: 1-candle return
        df['return'] = (df['close'] - df['open']) * df['position']
        
        # Filter trades (non-zero position)
        trades = df[df['position'] != 0]['return']
        
        if len(trades) == 0:
            return {'trades': 0, 'winrate': 0.0, 'profit': 0.0, 'profit_factor': 0.0}
            
        wins = trades[trades > 0]
        losses = trades[trades < 0]
        
        win_rate = len(wins) / len(trades) if len(trades) > 0 else 0
        gross_profit = wins.sum()
        gross_loss = abs(losses.sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99.0
        
        return {
            'trades': len(trades),
            'winrate': round(win_rate * 100, 2),
            'profit': round(trades.sum(), 2),
            'profit_factor': round(profit_factor, 2)
        }

    def evolve(self, asset="1HZ100V"):
        """Run the Evolutionary Loop"""
        df = self.load_history(asset, days=3) # Test last 3 days
        if df is None: return
        
        logger.info(f"🧬 STARTING EVOLUTION FOR {asset}...")
        
        # Genome Space (Parameters to test)
        rsi_periods = [7, 10, 14, 21]
        thresholds = [ (20,80), (25,75), (30,70), (35,65) ]
        
        top_score = -float('inf')
        champion = None
        
        for p in rsi_periods:
            for (low, high) in thresholds:
                result = self.backtest_strategy(df, rsi_period=p, buy_threshold=low, sell_threshold=high)
                
                # Fitness Function: Profit Factor * sqrt(Trades)
                # We want profitable strategies that actually trade.
                score = result['profit_factor'] * np.log(result['trades'] + 1)
                
                # Log Candidate
                # logger.info(f"Testing RSI({p}) [{low}/{high}] -> PF: {result['profit_factor']} | Win: {result['winrate']}% | Score: {score:.2f}")
                
                if score > top_score:
                    top_score = score
                    champion = {
                        'params': {'rsi_period': p, 'buy': low, 'sell': high},
                        'metrics': result
                    }
        
        logger.info("="*40)
        logger.info(f"🏆 CHAMPION FOUND: RSI({champion['params']['rsi_period']}) Bounds: {champion['params']['buy']}/{champion['params']['sell']}")
        logger.info(f"   - Profit Factor: {champion['metrics']['profit_factor']}")
        logger.info(f"   - Win Rate: {champion['metrics']['winrate']}%")
        logger.info(f"   - Total Trades: {champion['metrics']['trades']}")
        logger.info("="*40)
        
        return champion

if __name__ == "__main__":
    brain = OptimizerBrain()
    # Mock data check (if DB empty, this will warn)
    brain.evolve("1HZ100V")
