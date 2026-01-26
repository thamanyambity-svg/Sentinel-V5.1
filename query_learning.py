import sqlite3
import os
import json

db_path = "bot/data/sentinel.db"

if not os.path.exists(db_path):
    print("❌ No database found.")
    exit()

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("--- 🧠 SIGNALS (BRAIN) ---")
    try:
        cursor.execute("SELECT COUNT(*) FROM signals")
        total_signals = cursor.fetchone()[0]
        print(f"Total Signals Processed: {total_signals}")

        cursor.execute("SELECT decision, COUNT(*) FROM signals GROUP BY decision")
        decisions = cursor.fetchall()
        print("Decisions Distribution:", decisions)
        
        cursor.execute("SELECT strategy, outcome, COUNT(*) FROM signals WHERE outcome IS NOT NULL GROUP BY strategy, outcome")
        outcomes = cursor.fetchall()
        print("Outcomes by Strategy (1=WIN, 0=LOSS):", outcomes)

    except Exception as e:
        print(f"Error querying signals: {e}")

    print("\n--- 💪 EXECUTIONS (MUSCLE) ---")
    try:
        cursor.execute("SELECT COUNT(*), SUM(pnl) FROM executions")
        exec_stats = cursor.fetchone()
        print(f"Total Trades: {exec_stats[0]}")
        print(f"Total P&L: {exec_stats[1] if exec_stats[1] else 0.0}")

        cursor.execute("SELECT asset, count(*), sum(pnl) FROM executions GROUP BY asset")
        asset_stats = cursor.fetchall()
        for asset in asset_stats:
            print(f"Asset: {asset[0]} | Trades: {asset[1]} | P&L: {asset[2]}")

    except Exception as e:
        print(f"Error querying executions: {e}")

    conn.close()

except Exception as e:
    print(f"Database error: {e}")
