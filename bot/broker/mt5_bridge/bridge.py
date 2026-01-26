import json
import os
import time
import logging
from typing import Optional, Dict, Any

# Configure logging
logger = logging.getLogger("MT5_BRIDGE")

class MT5Bridge:
    """
    A file-based bridge to communicate with MetaTrader 5 (MT5).
    Writes generic command files that the 'Sentinel' EA in MT5 reads and executes.
    
    Architecture:
    1. Python writes command to `command.tmp`.
    2. Python renames `command.tmp` to `command.json` (Atomic operation).
    3. MT5 Sentinel reads `command.json`.
    4. MT5 Sentinel executes and deletes `command.json`.
    """

    def __init__(self, mt5_files_path: str):
        """
        Initialize the bridge.
        
        Args:
            mt5_files_path (str): Absolute path to the MT5 'MQL5/Files' directory.
        """
        self.mt5_path = mt5_files_path
        self.mt5_path = mt5_files_path
        self.cmd_dir = os.path.join(self.mt5_path, "Command")
        # Ensure command dir exists
        if os.path.exists(self.mt5_path) and not os.path.exists(self.cmd_dir):
             try: os.makedirs(self.cmd_dir, exist_ok=True)
             except: pass
             
        self.command_file = os.path.join(self.cmd_dir, "command.json") # Base name, but we will use unique names
        self.temp_file = os.path.join(self.cmd_dir, "command.tmp")
        self.ack_file = os.path.join(self.mt5_path, "ack.json")
        
        # Ensure path exists (if local). If it's a shared drive, it might be tricky, 
        # but we assume the user provides a valid valid local path.
        if not os.path.exists(self.mt5_path):
            logger.warning(f"MT5 Files path does not exist yet: {self.mt5_path}")
            # We don't raise error yet, allowing for lazy configuration

    def send_order(self, 
                   action: str, 
                   symbol: str, 
                   volume: float, 
                   sl: Optional[float] = None, 
                   tp: Optional[float] = None, 
                   magic: int = 123456) -> bool:
        """
        Send a trading order to MT5.
        
        Args:
            action (str): "BUY", "SELL", "CLOSE_ALL", "CLOSE_ONE"
            symbol (str): Asset symbol (e.g., "Crash 1000 Index")
            volume (float): Lot size (e.g., 0.2)
            sl (float, optional): Stop Loss price
            tp (float, optional): Take Profit price
            magic (int): Magic number for the trade ID
            
        Returns:
            bool: True if command successfully written, False otherwise.
        """
        if not self.mt5_path or not os.path.exists(self.mt5_path):
            logger.error("MT5 Path not configured or invalid.")
            return False

        command = {
            "id": int(time.time() * 1000),  # Unique command ID
            "action": action.upper(),
            "symbol": symbol,
            "volume": float(volume),
            "magic": int(magic),
            "timestamp": time.time()
        }
        
        if sl is not None:
            command["sl"] = float(sl)
        if tp is not None:
            command["tp"] = float(tp)

        return self._write_command(command)

    def _write_command(self, data: Dict[str, Any]) -> bool:
        """Writes the command dictionary to the JSON file atomically."""
        try:
            # 1. Write to temp file
            with open(self.temp_file, 'w') as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno()) # Ensure write to disk

            # 2. Atomic Rename
            os.replace(self.temp_file, self.command_file)
            logger.info(f"Command sent to MT5: {data['action']} {data.get('symbol', '')}")
            return True
        except Exception as e:
            logger.error(f"Failed to write MT5 command: {e}")
            return False

    def check_ack(self) -> Optional[Dict[str, Any]]:
        """
        Check if MT5 has processed the command (optional, if Sentinel writes back).
        """
        if os.path.exists(self.ack_file):
            try:
                with open(self.ack_file, 'r') as f:
                    data = json.load(f)
                # We could delete it after reading, or leave it for log
                return data
            except Exception as e:
                logger.error(f"Error reading ack file: {e}")
        return None

    def write_ai_bias(self, signal: str, trend: str, reason: str):
        """Write AI bias for EA Scalper to consume."""
        if not self.mt5_path or not os.path.exists(self.mt5_path):
            return
            
        bias_file = os.path.join(self.mt5_path, "ai_bias.json")
        try:
            # Atomic write
            temp_bias = bias_file + ".tmp"
            with open(temp_bias, 'w') as f:
                json.dump({
                    "signal": signal.upper(), 
                    "trend": trend.upper(), 
                    "reason": reason, 
                    "updated": time.time()
                }, f)
            os.replace(temp_bias, bias_file)
        except Exception as e:
            logger.error(f"Failed to write AI bias to {bias_file}: {e}")

    def clear_queue(self):
        """Force clear any stuck command file."""
        if os.path.exists(self.command_file):
            try:
                os.remove(self.command_file)
                logger.info("Cleared stuck command file.")
            except OSError as e:
                logger.error(f"Could not clear command file: {e}")
