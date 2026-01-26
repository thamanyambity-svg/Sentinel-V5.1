import os
import sys
import time
import json
import logging
import argparse
import random

# Add current directory to path to ensure imports work
sys.path.append(os.getcwd())

try:
    from bot.broker.mt5_bridge.bridge import MT5Bridge
except ImportError:
    # Fallback if run directly or path issues
    print("⚠️ Could not import 'bot.broker.mt5_bridge.bridge'. Using simplified local class.")
    class MT5Bridge:
        def __init__(self, mt5_files_path):
            self.mt5_path = mt5_files_path
            self.cmd_dir = os.path.join(self.mt5_path, "Command")
            if not os.path.exists(self.cmd_dir): os.makedirs(self.cmd_dir, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("stress_test.log")
    ]
)
logger = logging.getLogger("STRESS_TEST")

class BurstBridge(MT5Bridge):
    def __init__(self, mt5_files_path):
        super().__init__(mt5_files_path)

    def send_order_unique(self, action, symbol, volume, sl=None, tp=None, magic=123456, unique_id=None):
        command = {
            "id": unique_id if unique_id else int(time.time() * 1000000),
            "action": action.upper(),
            "symbol": symbol,
            "volume": float(volume),
            "magic": int(magic),
            "timestamp": time.time()
        }
        if sl: command["sl"] = float(sl)
        if tp: command["tp"] = float(tp)
        
        # Unique filename using timestamp and microsecond to allow sorting/uniqueness
        # MQL5 FileFindFirst order is not guaranteed, but unique names prevent overwrites.
        filename = f"cmd_{command['id']}.json"
        
        try:
            temp_path = os.path.join(self.cmd_dir, f"temp_{command['id']}.json")
            final_path = os.path.join(self.cmd_dir, filename)
            
            with open(temp_path, 'w') as f:
                json.dump(command, f)
                f.flush()
                # os.fsync(f.fileno()) # Slows down burst significantly, disable for maximum stress
                
            os.replace(temp_path, final_path)
            return True
        except Exception as e:
            logger.error(f"Failed to write: {e}")
            return False

def run_burst_test(bridge, count, symbol):
    logger.info(f"🚀 STARTING BURST TEST: {count} orders on {symbol}")
    logger.info(f"📂 Command Dir: {bridge.cmd_dir}")
    
    # 0. Clean start
    existing = [f for f in os.listdir(bridge.cmd_dir) if f.endswith('.json')]
    if existing:
        logger.warning(f"⚠️ Found {len(existing)} existing files. Clearing...")
        for f in existing:
            try: os.remove(os.path.join(bridge.cmd_dir, f))
            except: pass
            
    # 1. Burst Write
    start_time = time.time()
    sent_count = 0
    
    for i in range(count):
        # Use BUY_LIMIT far below price to avoid instant fill/loss, just want to test execution logic
        # OR use STATUS commands if we just want to test JSON parsing without trading (safer)
        # But User asked for stress test... let's mix.
        
        action = "STATUS" if i % 5 == 0 else "BUY_LIMIT"
        volume = 0.01
        
        # Note: If Sentinel expects floats in string format, Python's json dump is standard.
        # Sentinel V4.4 regex parser handles standard JSON.
        
        success = bridge.send_order_unique(
            action=action,
            symbol=symbol,
            volume=volume,
            magic=999999,
            unique_id=int(time.time() * 1000000) + i,
            sl=0.0,
            tp=0.0
        )
        if success:
            sent_count += 1
        
        # Tiny sleep to ensure unique timestamps if relying on system clock resolution? 
        # We manually added +i to ID, so filenames are unique.
        
    write_duration = time.time() - start_time
    logger.info(f"✅ BURST COMPLETE: Sent {sent_count}/{count} commands in {write_duration:.4f}s ({sent_count/write_duration:.1f} cmds/s)")
    
    # 2. Monitor Processing
    logger.info("⏳ Waiting for Sentinel to process commands...")
    
    start_wait = time.time()
    last_remaining = -1
    
    while True:
        try:
            files = [f for f in os.listdir(bridge.cmd_dir) if f.endswith('.json') and not f.startswith('temp')]
            remaining = len(files)
        except FileNotFoundError:
            # Can happen if dir is locked or deleted? Unlikely.
            remaining = 0
            
        if remaining != last_remaining:
            logger.info(f"   Remaining: {remaining} files...")
            last_remaining = remaining
            
        if remaining == 0:
            break
            
        time.sleep(0.2)
        
        if time.time() - start_wait > 60:
            logger.error("❌ TIMEOUT: Sentinel did not process all files in 60s")
            logger.error(f"Stuck files: {files[:5]}...")
            break
            
    total_duration = time.time() - start_time
    processing_time = total_duration - write_duration
    
    logger.info(f"🏁 TEST FINISHED. Total Duration: {total_duration:.2f}s")
    logger.info(f"⏱️ Processing Time: {processing_time:.2f}s (~{sent_count/processing_time if processing_time>0 else 0:.1f} cmds/s)")
    
    return sent_count, total_duration

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentinel Stress Test")
    parser.add_argument("--path", default="/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files", help="MT5 Files Path")
    parser.add_argument("--count", type=int, default=20, help="Number of commands")
    parser.add_argument("--symbol", default="Crash 1000 Index", help="Symbol to trade")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.path):
        logger.error(f"Path does not exist: {args.path}")
        print("💡 Use --path to specify your MT5 MQL5/Files directory.")
        exit(1)
        
    bridge = BurstBridge(args.path)
    run_burst_test(bridge, args.count, args.symbol)
