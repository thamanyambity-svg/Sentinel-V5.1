import sqlite3
import pandas as pd
import numpy as np
import logging
import os
import joblib
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import MinMaxScaler

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ORACLE_TRAINER")

DB_PATH = "bot/data/sentinel.db"
MODEL_DIR = "bot/models"

class OracleTrainer:
    def __init__(self, db_path=DB_PATH, model_dir=MODEL_DIR):
        self.db_path = db_path
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        self.lookback = 60

    def train_asset(self, asset):
        try:
            logger.info(f"🔮 Training Oracle for {asset}...")
            conn = sqlite3.connect(self.db_path)
            query = f"SELECT close FROM market_data WHERE asset = '{asset}' ORDER BY epoch"
            df = pd.read_sql_query(query, conn)
            conn.close()

            if len(df) < self.lookback + 50:
                logger.warning(f"⚠️ Insufficient data for {asset} ({len(df)} samples)")
                return False

            # Preprocessing
            data = df['close'].values.reshape(-1, 1)
            scaler = MinMaxScaler()
            scaled_data = scaler.fit_transform(data)

            X, y = [], []
            for i in range(self.lookback, len(scaled_data)):
                X.append(scaled_data[i-self.lookback:i, 0])
                y.append(scaled_data[i, 0])

            X, y = np.array(X), np.array(y)

            # Train Regressor (HistGradientBoosting is faster/stable on Mac)
            model = HistGradientBoostingRegressor(
                max_iter=300,
                learning_rate=0.07,
                max_depth=7,
                random_state=42,
                early_stopping=True
            )
            
            logger.info(f"🏋️ Fitting model for {asset}...")
            model.fit(X, y)

            # Save (Using naming convention expected by QuantPredictor)
            model_path = os.path.join(self.model_dir, f"{asset}_mlp.pkl")
            scaler_path = os.path.join(self.model_dir, f"{asset}_scaler.pkl")
            
            joblib.dump(model, model_path)
            joblib.dump(scaler, scaler_path)
            
            logger.info(f"✅ Oracle saved for {asset} ({len(X)} samples)")
            return True
        except Exception as e:
            logger.error(f"❌ Oracle Training Error for {asset}: {e}")
            return False

if __name__ == "__main__":
    trainer = OracleTrainer()
    assets = ["1HZ10V", "1HZ100V", "EURUSD", "GOLD", "NVDA", "TSLA"]
    for asset in assets:
        trainer.train_asset(asset)
    logger.info("🎉 All Oracles updated.")
