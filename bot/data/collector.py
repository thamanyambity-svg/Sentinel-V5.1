
import os
import logging
import sqlite3
import json
import time
from typing import List, Dict, Any

logger = logging.getLogger("DATA_COLLECTOR")

class DataCollector:
    """
    Phase 0 Instrumentation: SQLite Data Warehousing.
    Logs EVERYTHING: Signals (valid/rejected), Executions, and Market Data.
    Target DB: bot/data/sentinel.db
    """
    
    def __init__(self, data_dir="bot/data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "sentinel.db")
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Create tables if not exist"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 1. SIGNALS TABLE (The Brain's Output)
        cursor.execute('''
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
                outcome INTEGER,
                raw_data JSON
            )
        ''')
        
        # Migration: Add outcome column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE signals ADD COLUMN outcome INTEGER")
        except sqlite3.OperationalError:
            pass # Column already exists
        
        # 2. EXECUTIONS TABLE (The Muscle's Output)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS executions (
                ticket TEXT PRIMARY KEY,
                signal_id TEXT,
                asset TEXT,
                direction TEXT,
                open_time REAL,
                open_price REAL,
                close_time REAL,
                close_price REAL,
                pnl REAL,
                commission REAL,
                status TEXT
            )
        ''')
        
        # 3. TICKS/CANDLES (The Raw Material) for Replay
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                asset TEXT,
                epoch INTEGER,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (asset, epoch)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"🗄️ [DB] Sentinel SQLite initialized at {self.db_path}")

    def save_candles(self, asset: str, candles: List[Dict]):
        """Insert candles into SQLite"""
        if not candles: return
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Prepare batch
        data = []
        for c in candles:
            # Deriv candles: epoch, open, high, low, close
            data.append((
                asset, 
                int(c.get('epoch')), 
                float(c.get('open')), 
                float(c.get('high')), 
                float(c.get('low')), 
                float(c.get('close')),
                0.0 # Volume often unavailable in simple candles
            ))
            
        # Bulk Insert (Ignore duplicates)
        cursor.executemany('''
            INSERT OR IGNORE INTO market_data (asset, epoch, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', data)
        
        conn.commit()
        conn.close()
        # logger.debug(f"💾 [DB] Saved {len(data)} candles for {asset}")

    def log_signal(self, signal_data: Dict):
        """Log a decision (Execute OR Wait)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Generate ID if missing
        sig_id = signal_data.get("id", f"sig_{int(time.time()*1000)}")
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO signals (id, timestamp, asset, strategy, side, score, rsi, atr, regime, decision, reasoning, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sig_id,
                time.time(),
                signal_data.get("asset"),
                signal_data.get("strategy", "UNKNOWN"),
                signal_data.get("side", "NONE"),
                float(signal_data.get("score", 0)),
                float(signal_data.get("rsi", 0)),
                float(signal_data.get("atr", 0)),
                signal_data.get("regime", "UNKNOWN"),
                signal_data.get("decision", "WAIT"),
                signal_data.get("reasoning", ""),
                json.dumps(signal_data)
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"❌ [DB] Signal logging error: {e}")
        finally:
            conn.close()

    def sync_signal_outcome(self, signal_id: str, outcome: int):
        """Update a signal with its trade outcome (1=WIN, 0=LOSS)"""
        if not signal_id: return
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE signals SET outcome = ? WHERE id = ?', (outcome, signal_id))
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"🔄 [DB] Signal {signal_id} synced with outcome: {outcome}")
        except Exception as e:
            logger.error(f"❌ [DB] Signal sync error: {e}")
        finally:
            conn.close()

    def log_trade_result(self, trade: Dict):
        """Log a closed trade result"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO executions (ticket, signal_id, asset, direction, open_time, open_price, close_time, close_price, pnl, commission, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(trade.get("ticket", f"mock_{int(time.time())}")),
                trade.get("signal_id", ""),
                trade.get("asset"),
                trade.get("type", "UNKNOWN"),
                trade.get("open_time", 0),
                float(trade.get("price_in", 0)),
                trade.get("close_time", time.time()),
                float(trade.get("price_out", 0)),
                float(trade.get("pnl", 0)),
                0.0,
                trade.get("result", "CLOSED")
            ))
            conn.commit()
            logger.info(f"💾 [DB] Trade Logged: {trade.get('pnl')}$")
        except Exception as e:
            logger.error(f"❌ [DB] Trade logging error: {e}")
        finally:
            conn.close()
            
    def log_market_health(self, data: Dict):
        # Optional: Store health metrics in a separate table if needed
        # For Phase 0, we focus on Signals/Executions
        pass
