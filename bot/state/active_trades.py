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
    """Saves active trades to JSON file using atomic writes to prevent corruption."""
    import json
    import os
    from tempfile import NamedTemporaryFile
    import shutil
    
    try:
        # 1. Create a temporary file
        # delete=False is required to close and then rename on some systems, 
        # though strictly on Unix we can rename open files, it's safer to close first.
        # We use the same directory to ensure atomic move (rename) is possible.
        dir_name = os.path.dirname(os.path.abspath(STATE_FILE)) or "."
        with NamedTemporaryFile('w', delete=False, dir=dir_name, suffix='.tmp') as tmp_file:
            json.dump(_ACTIVE_TRADES, tmp_file, indent=4)
            tmp_path = tmp_file.name
        
        # 2. Rename temporary file to target file (Atomic operation)
        os.replace(tmp_path, STATE_FILE)
        
    except Exception as e:
        print(f"❌ Failed to save state safely: {e}")
        # Attempt to clean up temp file if it exists and wasn't renamed
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass

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
