import sqlite3
import pandas as pd
import numpy as np
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DATA_LABELER")

DB_PATH = "bot/data/sentinel.db"

class DataLabeler:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.tp_multiplier = 2.0  # Reward/Risk Ratio
        self.sl_multiplier = 1.0  # ATR Multiplier for SL
        
    def connect(self):
        return sqlite3.connect(self.db_path)

    def add_label_column(self):
        """Ensure the signals table has a 'outcome' column."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE signals ADD COLUMN outcome INTEGER")
            logger.info("Added 'outcome' column to signals table.")
        except sqlite3.OperationalError:
            logger.info("'outcome' column already exists.")
        conn.commit()
        conn.close()

    def label_signals(self):
        """
        Iterate through all signals and label them based on future market data.
        Label 1 = Win (Hit TP before SL)
        Label 0 = Loss (Hit SL before TP, or Timeout)
        """
        self.add_label_column()
        
        conn = self.connect()
        # Get all unlabeled signals
        query = "SELECT * FROM signals WHERE outcome IS NULL"
        signals_df = pd.read_sql_query(query, conn)
        
        if signals_df.empty:
            logger.info("✅ All signals are already labeled.")
            conn.close()
            return

        logger.info(f"🏷️ Labeling {len(signals_df)} signals...")
        
        updates = []
        
        for index, row in signals_df.iterrows():
            signal_id = row['id']
            asset = row['asset']
            timestamp = row['timestamp']
            side = row['side']
            
            # Parse raw data for ATR if available, else standard fallback
            try:
                raw = json.loads(row['raw_data'])
                atr = float(raw.get('atr', 1.0)) # Fallback
                close_price = float(raw.get('current_price', 0.0))
            except:
                atr = 1.0
                close_price = 0.0 # Will fetch from market data if 0
            
            # Get future market data (Next 60 minutes)
            # Assuming M1 data in market_data table
            # epoch is timestamp
            market_query = f"""
                SELECT * FROM market_data 
                WHERE asset = '{asset}' AND epoch >= {timestamp} 
                ORDER BY epoch ASC LIMIT 120
            """
            market_df = pd.read_sql_query(market_query, conn)
            
            if market_df.empty or len(market_df) < 5:
                # Not enough data to judge
                continue
                
            if close_price == 0.0:
                close_price = market_df.iloc[0]['close']
                
            # Define TP/SL
            sl_dist = atr * self.sl_multiplier * 5 # x5 because raw ATR might be small or specific scale
            # To be more robust, let's use percentage if ATR is suspicious
            if sl_dist < close_price * 0.0005: sl_dist = close_price * 0.005 # Min 0.5% SL
            
            tp_dist = sl_dist * self.tp_multiplier
            
            if side == "BUY":
                tp_price = close_price + tp_dist
                sl_price = close_price - sl_dist
            else: # SELL
                tp_price = close_price - tp_dist
                sl_price = close_price + sl_dist
                
            # Simulation Loop
            outcome = 0 # Assume loss/timeout unless proven win
            
            for _, candle in market_df.iterrows():
                high = candle['high']
                low = candle['low']
                
                if side == "BUY":
                    if low <= sl_price:
                        outcome = 0 # Stop Loss Hit
                        break
                    if high >= tp_price:
                        outcome = 1 # Take Profit Hit
                        break
                else: # SELL
                    if high >= sl_price:
                        outcome = 0 # Stop Loss Hit
                        break
                    if low <= tp_price:
                        outcome = 1 # Take Profit Hit
                        break
            
            updates.append((outcome, signal_id))
            
            if len(updates) % 100 == 0:
                print(f".", end="", flush=True)

        # Batch Update
        cursor = conn.cursor()
        cursor.executemany("UPDATE signals SET outcome = ? WHERE id = ?", updates)
        conn.commit()
        conn.close()
        
        win_rate = sum([u[0] for u in updates]) / len(updates) if updates else 0
        logger.info(f"\n✅ Labeling Complete. Labeled {len(updates)} signals.")
        logger.info(f"📊 Simulated Win Rate: {win_rate*100:.2f}%")

if __name__ == "__main__":
    labeler = DataLabeler()
    labeler.label_signals()
