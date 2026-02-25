import sys
import os
import time

# Ensure we can import from bot package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.bridge.mt5_interface_v2 import MT5Bridge

def force_trade():
    print("🚀 Forcing Manual Trade...")
    
    # Initialize Bridge using existing configuration
    try:
        bridge = MT5Bridge()
        
        # Define Test Order
        symbol = "EURUSD"
        side = "BUY"
        volume = 0.5
        
        print(f"🔹 Sending Order: {side} {volume} {symbol}")
        
        success = bridge.send_order(symbol, side, volume)
        
        if success:
            print("✅ Order Command Written Successfully.")
            print("Check MT5 Terminal or Dashboard for execution.")
        else:
            print("❌ Failed to write order command.")
            
    except Exception as e:
        print(f"🔥 Error: {e}")

if __name__ == "__main__":
    force_trade()
