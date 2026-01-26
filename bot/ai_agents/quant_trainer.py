import sqlite3
import pandas as pd
import numpy as np
import logging
import os
import json
import joblib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("QUANT_TRAINER")


try:
    # Fallback to Sklearn's HistGradientBoostingClassifier (LightGBM equivalent)
    # to avoid libomp dependency issues on macOS
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, roc_auc_score
except ImportError as e:
    logger.error(f"❌ Missing dependencies: {e}")
    exit(1)

DB_PATH = "bot/data/sentinel.db"
MODEL_DIR = "bot/models"

class QuantTrainer:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        os.makedirs(MODEL_DIR, exist_ok=True)
        
    def load_training_data(self):
        conn = sqlite3.connect(self.db_path)
        # Load labeled signals
        query = "SELECT * FROM signals WHERE outcome IS NOT NULL"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            logger.error("No labeled data found!")
            return None, None
            
        features = df[['rsi', 'atr', 'score']].copy()
        
        # Encode Regime
        regime_map = {
            "RANGE_CALM": 0,
            "TREND_STABLE": 1, 
            "VOLATILE_FAST": 2, 
            "CRASH_CHAOS": 3,
            "UNKNOWN": 0 
        }
        features['regime_val'] = df['regime'].map(regime_map).fillna(0)
        
        # Target
        # Ensure target is integer
        target = df['outcome'].astype(int)
        
        logger.info(f"Loaded {len(df)} samples. Positive samples: {target.sum()} ({target.mean():.2%})")
        
        return features, target

    def train(self):
        logger.info("🚀 Starting HistGradientBoosting Training (Sklearn)...")
        
        X, y = self.load_training_data()
        if X is None: return
        
        # Split
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        
        # Build Model
        # HistGradientBoostingClassifier is very similar to LightGBM
        model = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=500,
            max_leaf_nodes=31,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=10,
            random_state=42,
            verbose=1
        )
        
        # Train
        logger.info("Fitting model...")
        model.fit(X_train, y_train)
        
        # Evaluation
        y_pred_prob = model.predict_proba(X_val)[:, 1]
        y_pred = model.predict(X_val)
        
        auc = roc_auc_score(y_val, y_pred_prob)
        logger.info(f"✅ Training Complete. Validation AUC: {auc:.4f}")
        logger.info("\n" + classification_report(y_val, y_pred))
        
        # Save Model (Pickle only for Sklearn)
        model_path_pkl = os.path.join(MODEL_DIR, "signal_filter_sklearn.pkl")
        joblib.dump(model, model_path_pkl)
        logger.info(f"💾 Model saved to {model_path_pkl}")

if __name__ == "__main__":
    trainer = QuantTrainer()
    trainer.train()
