#!/usr/bin/env python3
import time
import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# Configuration
DB_PATH = "bot/data/sentinel.db"
MODEL_PATH = "bot/models/signal_filter_sklearn.pkl"
LOG_FILE = "evolution.log"
REFRESH_RATE = 300 # 5 minutes

class SentinelMonitor:
    def __init__(self):
        self.db_path = DB_PATH
        
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def get_db_stats(self):
        if not os.path.exists(self.db_path):
            return "❌ Database not found"
        
        try:
            conn = sqlite3.connect(self.db_path)
            # Today's trades (simulated or real from signals table if linked to executions)
            # Assuming 'signals' has 'outcome' populated by labeler
            today = datetime.now().strftime("%Y-%m-%d")
            query = f"SELECT * FROM signals WHERE date(datetime(timestamp, 'unixepoch')) = '{today}'"
            df = pd.read_sql_query(query, conn)
            
            total = len(df)
            wins = len(df[df['outcome'] == 1]) if 'outcome' in df.columns else 0
            
            conn.close()
            return {"total": total, "wins": wins, "rate": (wins/total*100) if total > 0 else 0}
        except Exception as e:
            return f"Error: {e}"

    def get_model_age(self):
        if not os.path.exists(MODEL_PATH):
            return "❌ No Model"
        mtime = os.path.getmtime(MODEL_PATH)
        dt = datetime.fromtimestamp(mtime)
        age = datetime.now() - dt
        return f"{dt.strftime('%Y-%m-%d %H:%M')} ({age.days}d {age.seconds//3600}h ago)"

    def get_last_evolution(self):
        log_path = os.path.abspath(LOG_FILE)
        if not os.path.exists(log_path):
            return "File Not Found"
        try:
            # Read last few lines to find 'Validation AUC'
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if "Validation AUC" in line:
                        # Extract the number
                        # Line format: ... Validation AUC: 0.6678
                        parts = line.split("AUC:")
                        if len(parts) > 1:
                            return parts[1].strip()
            return "AUC Not Found"
        except Exception as e:
            return f"Error: {str(e)}"

    def display(self):
        self.clear_screen()
        stats = self.get_db_stats()
        model_age = self.get_model_age()
        auc = self.get_last_evolution()
        
        print("="*50)
        print(f"👁️  SENTINEL MONITORING DASHBOARD  👁️")
        print(f"    Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)
        
        print(f"\n🧠  AI HYPOTHALAMUS")
        print(f"    Model Age:      {model_age}")
        print(f"    Last AUC:       {auc}")
        print(f"    Status:         {'✅ ACTIVE' if os.path.exists(MODEL_PATH) else '❌ MISSING'}")
        
        print(f"\n📊  TODAY'S ACTIVITY (Raw Signals)")
        if isinstance(stats, dict):
            print(f"    Signals Gen:    {stats['total']}")
            print(f"    Potential Wins: {stats['wins']} (Backtest/Labeling)")
            print(f"    Raw Quality:    {stats['rate']:.1f}% Win Rate")
        else:
            print(f"    {stats}")
            
        print(f"\n⚠️  ALERTS (Thresholds)")
        # Simple Logic
        auc_val = float(auc) if auc.replace('.','',1).isdigit() else 0.0
        if auc_val < 0.60:
            print("    [!] CRITICAL: Model Performance Low (< 0.60)")
        elif auc_val < 0.65:
            print("    [!] WARNING: Model Performance Degraded (< 0.65)")
        else:
            print("    [OK] Model Healthy")
            
        print("\n" + "="*50)
        print("Press Ctrl+C to Stop. Refreshing every 5m...")

    def run(self):
        try:
            while True:
                self.display()
                time.sleep(REFRESH_RATE)
        except KeyboardInterrupt:
            print("\n🛑 Surveillance Stopped.")

if __name__ == "__main__":
    monitor = SentinelMonitor()
    monitor.run()
