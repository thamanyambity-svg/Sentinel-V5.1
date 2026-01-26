"""
Active Trade State Management
Tracks trades that have been executed but not yet closed.
"""

from typing import Dict, List, Optional
import time

# Dictionary to store active trades
# Key: Trade ID (contract_id)
# Value: Dict with trade details
_ACTIVE_TRADES: Dict[str, dict] = {}

import json
import os

STATE_FILE = "bot_state.json"

def save_state():
    """Saves active trades to JSON file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(_ACTIVE_TRADES, f, indent=4)
    except Exception as e:
        print(f"❌ Failed to save state: {e}")

def load_state():
    """Loads active trades from JSON file."""
    global _ACTIVE_TRADES
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                _ACTIVE_TRADES = json.load(f)
            print(f"💾 State loaded: {len(_ACTIVE_TRADES)} active trades.")
        except Exception as e:
            print(f"❌ Failed to load state: {e}")

# Load on module import
load_state()

def add_active_trade(trade_id: str, asset: str, stake: float, duration: str = "1m", grid_plan: Optional[dict] = None, metadata: Optional[dict] = None, signal_id: Optional[str] = None):
    """
    Registers a new active trade.
    """
    import traceback
    print(f"🕵️ [TRACE] Adding Active Trade {trade_id} (Asset: {asset}, Signal: {signal_id})")
    # traceback.print_stack() # Optional: noisy but useful if desperate
    
    global _ACTIVE_TRADES
    _ACTIVE_TRADES[str(trade_id)] = {
        "id": str(trade_id),
        "signal_id": signal_id,
        "asset": asset,
        "stake": stake,
        "duration": duration,
        "start_time": time.time(),
        "status": "RUNNING",
        "grid_plan": grid_plan if isinstance(grid_plan, list) else [],
        "metadata": metadata or {}
    }
    save_state()

def get_active_trades() -> List[dict]:
    """
    Returns a list of all active trades.
    """
    return list(_ACTIVE_TRADES.values())

def get_active_trade(trade_id: str) -> Optional[dict]:
    """
    Get details of a specific active trade.
    """
    return _ACTIVE_TRADES.get(str(trade_id))

def remove_active_trade(trade_id: str):
    """
    Removes a trade from the active list (e.g., when closed).
    """
    global _ACTIVE_TRADES
    cid = str(trade_id)
    if cid in _ACTIVE_TRADES:
        del _ACTIVE_TRADES[cid]
        save_state()

def count_active_trades() -> int:
    return len(_ACTIVE_TRADES)
