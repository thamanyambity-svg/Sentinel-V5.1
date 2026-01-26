"""
Trade Counter - Daily Trade Limit Tracker
Stores trade count in JSON file, auto-resets at midnight UTC
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

COUNTER_FILE = Path(__file__).parent.parent / "data" / "trade_counter.json"

def _ensure_data_dir():
    """Create data directory if it doesn't exist"""
    COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load_counter():
    """Load counter from file"""
    _ensure_data_dir()
    if not COUNTER_FILE.exists():
        return {"date": "", "count": 0}
    
    try:
        with open(COUNTER_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"date": "", "count": 0}

def _save_counter(data):
    """Save counter to file"""
    _ensure_data_dir()
    with open(COUNTER_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def _get_today_str():
    """Get today's date as string (UTC)"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def reset_if_new_day():
    """Reset counter if it's a new day"""
    data = _load_counter()
    today = _get_today_str()
    
    if data["date"] != today:
        data = {"date": today, "count": 0}
        _save_counter(data)
    
    return data

def get_trade_count():
    """Get today's trade count"""
    data = reset_if_new_day()
    return data["count"]

def increment_trade_count():
    """Increment today's trade count"""
    data = reset_if_new_day()
    data["count"] += 1
    _save_counter(data)
    return data["count"]

def get_max_trades():
    """Get max trades per day from env"""
    return int(os.getenv("MAX_TRADES_PER_DAY", "10"))

def is_limit_reached():
    """Check if daily limit is reached"""
    return get_trade_count() >= get_max_trades()
