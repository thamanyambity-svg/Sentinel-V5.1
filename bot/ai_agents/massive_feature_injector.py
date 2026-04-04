import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger("MASSIVE_INJECTOR")

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/sentinel.db")

def get_closest_daily_candle(cursor, asset, epoch):
    """
    Finds the latest daily candle for 'asset' occurring at or before 'epoch'.
    """
    try:
        cursor.execute('''
            SELECT open, close, volume 
            FROM market_data 
            WHERE asset = ? AND epoch <= ?
            ORDER BY epoch DESC
            LIMIT 1
        ''', (asset, epoch))
        return cursor.fetchone()
    except Exception as e:
        logger.warning(f"Error querying massive db for {asset}: {e}")
        return None

def get_macro_features(symbol, timestamp_iso):
    """
    Given an MT5 symbol and ISO timestamp, returns macro features from Massive (sentinel.db).
    Secured with neutral fallbacks if API/DB fails.
    """
    features = {
        "massive_volume_d1": 0.0,
        "daily_trend": 0.0,
        "macro_spy_trend": 0.0,
        "macro_spy_volume": 0.0
    }
    
    if not os.path.exists(DB_PATH):
        return features
        
    try:
        # Convert timestamp to epoch
        dt = datetime.fromisoformat(timestamp_iso)
        epoch = int(dt.timestamp())
        
        # Standardize symbol name
        asset_name = symbol.replace("C:", "").replace("X:", "")
        if asset_name == "XAUUSD": 
            asset_name = "GOLD"
            
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 1. Fetch target asset daily data
            asset_data = get_closest_daily_candle(cursor, asset_name, epoch)
            if asset_data:
                o, c, v = asset_data
                features["massive_volume_d1"] = float(v)
                features["daily_trend"] = float(c - o)
                
            # 2. Fetch SPY macro context
            spy_data = get_closest_daily_candle(cursor, "SPY", epoch)
            if spy_data:
                so, sc, sv = spy_data
                features["macro_spy_trend"] = float(sc - so)
                features["macro_spy_volume"] = float(sv)
                
    except Exception as e:
        logger.error(f"Failed to lookup Massive features: {e}. Falling back to neutral.")
        
    return features

if __name__ == "__main__":
    print(get_macro_features("EURUSD", datetime.now().isoformat()))
