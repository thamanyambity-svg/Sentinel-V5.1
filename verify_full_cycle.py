import time
import json
import os
from bot.bridge.mt5_interface import MT5Bridge

def pretty_print(msg):
    print(f"🧪 [VERIFY] {msg}")

def run_test():
    bridge = MT5Bridge()
    symbol = "1HZ10V" # Volatility 10 (1s) Index
    
    pretty_print("--- STARTING END-TO-END VERIFICATION (Sentinel v4.6) ---")
    
    # 1. Send BUY Order
    pretty_print(f"1. Sending BUY Order for {symbol}...")
    if bridge.send_order(symbol, "BUY", volume=0.50):
        pretty_print("✅ Buy Command Sent.")
    else:
        pretty_print("❌ Failed to send Buy Command.")
        return

    # 2. Wait for Execution (Poll status.json)
    pretty_print("2. Waiting for execution confirmation (max 10s)...")
    ticket = None
    for i in range(10):
        time.sleep(1)
        positions = bridge.get_portfolio()
        for p in positions:
            # Check if it's our symbol (and maybe recent, but for now just any matching)
            # The symbol name in bridge is "Volatility 10 (1s) Index", mapped from "1HZ10V"
            if "Volatility 10 (1s)" in p.get('symbol', ''):
                ticket = p.get('ticket')
                pretty_print(f"✅ Position FOUND! Ticket: {ticket}, Profit: {p.get('profit')}")
                break
        if ticket: break
    
    if not ticket:
        pretty_print("❌ Timeout: No position found in status.json. Is the bot running?")
        # Try to read status.json content for debug
        status = bridge.get_raw_status()
        print(f"DEBUG: Status Content: {status}")
        return

    # 3. Send CLOSE Order
    pretty_print(f"3. Closing Ticket {ticket}...")
    time.sleep(2) # Let it run for a bit
    if bridge.close_position(ticket):
        pretty_print("✅ Close Command Sent.")
    else:
        pretty_print("❌ Failed to send Close Command.")
        return

    # 4. Confirm Closure
    pretty_print("4. Waiting for closure confirmation...")
    closed = False
    for i in range(10):
        time.sleep(1)
        positions = bridge.get_portfolio()
        found = False
        for p in positions:
            if p.get('ticket') == ticket:
                found = True
                break
        if not found:
            closed = True
            pretty_print(f"✅ Ticket {ticket} is GONE from portfolio. Trade Closed.")
            break
    
    if not closed:
        pretty_print("⚠️ Ticket still present after 10s.")
    else:
        pretty_print("🎉 SUCCESS: Full Cycle (Buy -> Detect -> Close) works perfectly!")

if __name__ == "__main__":
    run_test()
