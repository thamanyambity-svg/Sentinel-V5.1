import sqlite3
import json
import time
import logging
import os
import uuid

logger = logging.getLogger("EXPERIENCE_LOGGER")

DB_PATH = "bot/data/sentinel.db"

class ExperienceLogger:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        """Ensure the signals table exists with the correct schema"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id TEXT PRIMARY KEY,
                    timestamp REAL,
                    asset TEXT,
                    strategy TEXT,
                    side TEXT,
                    score REAL,
                    rsi REAL,
                    atr REAL,
                    regime TEXT,
                    decision TEXT,
                    reasoning TEXT,
                    raw_data JSON,
                    outcome INTEGER
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def log_signal(self, asset, side, analysis_data, global_risk):
        """
        Records the initial signal and associated market state.
        Returns a unique signal_id to be used for outcome tracking.
        """
        signal_id = str(uuid.uuid4())
        timestamp = time.time()
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Prepare features
            regime = analysis_data.get('trend', 'UNKNOWN')
            price = analysis_data.get('price', 0)
            change_pct = analysis_data.get('change_percent', 0)
            spread = analysis_data.get('spread', 0)
            
            # Build raw features for training
            raw_features = {
                "price": price,
                "change_percent": change_pct,
                "spread": spread,
                "risk_level": global_risk
            }
            
            cursor.execute("""
                INSERT INTO signals 
                (id, timestamp, asset, strategy, side, score, rsi, atr, regime, decision, reasoning, raw_data, outcome)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_id,
                timestamp,
                asset,
                "SENTINEL_V5",
                side,
                change_pct, # Use change_pct as a simple score
                0, # Future: Add real RSI
                0, # Future: Add real ATR
                regime,
                "EXECUTE",
                f"Trend: {regime}, Risk: {global_risk}",
                json.dumps(raw_features),
                None # Outcome is pending
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"📁 Experience Logged (ID: {signal_id}) for {asset}")
            return signal_id
            
        except Exception as e:
            logger.error(f"Failed to log experience: {e}")
            return None

    def update_outcome(self, asset, profit, ticket=None):
        """
        Updates the most recent pending signal for an asset with the outcome.
        Outcome: 1 (Profit > 0), 0 (Loss <= 0)
        """
        outcome = 1 if profit > 0 else 0
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find the latest pending signal for this asset
            cursor.execute("""
                UPDATE signals 
                SET outcome = ? 
                WHERE id = (
                    SELECT id FROM signals 
                    WHERE asset = ? AND outcome IS NULL 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                )
            """, (outcome, asset))
            
            if cursor.rowcount > 0:
                logger.info(f"✅ Outcome Updated for {asset}: {'PROFIT' if outcome else 'LOSS'}")
            else:
                logger.info(f"ℹ️ No pending signal found to update outcome for {asset}")
                
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update outcome: {e}")

experience_logger = ExperienceLogger()
