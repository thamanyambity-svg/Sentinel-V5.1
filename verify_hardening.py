import os
import time
import logging
from bot.state.active_trades import save_state, load_state, add_active_trade, _ACTIVE_TRADES
from bot.core.monitor import ResourceMonitor
from bot.core.logger import get_logger

def verify_hardening():
    print("🛡️  Starting Technical Hardening Verification...\n")

    # 1. Verify Unified Logging
    print("🔹 [1/3] Testing Unified Logger...")
    logger = get_logger("TEST_HARDENING")
    log_file = os.path.expanduser("~/bot/logs/bot.log")
    
    # Write some logs
    logger.info("Test Info Log for Hardening Verification")
    logger.warning("Test Warning Log")
    
    if os.path.exists(log_file):
        print(f"   ✅ Log file exists at: {log_file}")
        # Check if our log made it
        with open(log_file, 'r') as f:
            content = f.read()
            if "Test Info Log" in content:
                 print("   ✅ Log entry confirmed in generated file.")
            else:
                 print("   ❌ Log entry NOT found in file.")
    else:
        print(f"   ❌ Log file NOT found at: {log_file}")

    # 2. Verify Atomic State Writes
    print("\n🔹 [2/3] Testing Atomic State Writes...")
    try:
        # Save current state
        original_len = len(_ACTIVE_TRADES)
        
        # Add a test trade
        test_id = "test_hardening_123"
        add_active_trade(test_id, "TEST_USD", 50.0, "1m")
        
        # Check if file exists
        if os.path.exists("bot_state.json"):
            print("   ✅ bot_state.json exists.")
            
            # Verify content
            load_state()
            if test_id in _ACTIVE_TRADES:
                print("   ✅ Atomic Write check: Trade persisted correctly.")
            else:
                 print("   ❌ Atomic Write check: Trade NOT found.")
        else:
             print("   ❌ bot_state.json NOT found.")
             
    except Exception as e:
        print(f"   ❌ Error testing atomic writes: {e}")

    # 3. Verify Resource Monitoring
    print("\n🔹 [3/3] Testing Resource Monitor...")
    monitor = ResourceMonitor()
    try:
        checks = monitor.comprehensive_health_check()
        print(f"   ✅ Monitor Output: {checks}")
        if checks['cpu_ok'] and checks['memory_ok']:
            print("   ✅ System Health: OK")
        else:
            print("   ⚠️ System Health: WARNING")
    except Exception as e:
        print(f"   ❌ Monitor Failed: {e}")

    print("\n✅ Verification Complete.")

if __name__ == "__main__":
    verify_hardening()
