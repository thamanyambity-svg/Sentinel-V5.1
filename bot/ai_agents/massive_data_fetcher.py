import requests
import os
import sqlite3
import pandas as pd
import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MASSIVE_FETCHER")

MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY", "")
DB_PATH = "bot/data/sentinel.db"

class MassiveFetcher:
    def __init__(self, api_key=MASSIVE_API_KEY, db_path=DB_PATH):
        self.api_key = api_key
        self.db_path = db_path

    def fetch_history(self, ticker, days=30):
        if not self.api_key:
            logger.error("MASSIVE_API_KEY not found.")
            return

        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Polygon API format: /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}?adjusted=true&apiKey={self.api_key}"
        
        logger.info(f"📡 Fetching history for {ticker} from {start_date} to {end_date}...")
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if not results:
                    logger.warning(f"No results returned for {ticker}.")
                    return
                
                self.save_to_db(ticker, results)
            else:
                logger.error(f"Failed to fetch {ticker}: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error fetching data: {e}")

    def save_to_db(self, ticker, results):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Mapping internally to standardized names
        # Sentinel uses asset names like 'EURUSD', 'XAUUSD'
        asset_name = ticker.replace("C:", "").replace("X:", "")
        if asset_name == "XAUUSD": asset_name = "GOLD"

        count = 0
        for r in results:
            # Polygon Agg: t (msec timestamp), o, h, l, c, v, vw, n
            epoch = int(r['t'] / 1000)
            cursor.execute('''
                INSERT OR IGNORE INTO market_data (asset, epoch, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (asset_name, epoch, r['o'], r['h'], r['l'], r['c'], r.get('v', 0)))
            count += cursor.rowcount
            
        conn.commit()
        conn.close()
        logger.info(f"✅ Saved {count} new candles for {asset_name} to {self.db_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true", help="Run in a loop")
    args = parser.parse_args()

    fetcher = MassiveFetcher()
    
    while True:
        # Focus exclusif sur l'OR (XAUUSD)
        fetcher.fetch_history("C:XAUUSD", days=365)
        logger.info("🎉 Historical data acquisition (GOLD ONLY) complete.")

        
        if not args.daemon:
            break
            
        logger.info("⏳ Mode Daemon: Prochaine mise à jour dans 24 heures...")
        import time
        time.sleep(24 * 3600)

