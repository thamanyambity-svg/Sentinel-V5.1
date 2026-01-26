
import asyncio
import os
import sys

# Mocking parts of the system to test without real connections
sys.path.append(os.getcwd())

from bot.broker.deriv.mapper import map_trade
from bot.broker.deriv.broker import DerivBroker

async def verify_logic():
    print("--- 🛡️ AUDIT DE SÉCURITÉ PAYLOAD ---")
    
    test_trade = {
        "asset": "1HZ10V",
        "side": "BUY",
        "amount": 1.0, # Attempting to hack 1.0
        "duration": "1m",
        "quality_score": 95,
        "ml_confidence": 0.85
    }
    
    # 1. Test Mapper
    payload = map_trade(test_trade)
    print(f"Mapper Result (Amount Request 1.0): {payload['amount']} (Expected 0.35)")
    
    if payload['amount'] != 0.35:
        print("❌ FAILED: Mapper did not force 0.35")
    else:
        print("✅ PASSED: Mapper forced 0.35")
        
    print(f"Contract Type: {payload['contract_type']} (Expected VANILLALONGCALL)")
    if payload['contract_type'] == "VANILLALONGCALL":
        print("✅ PASSED: Contract is VANILLA")
    else:
        print("❌ FAILED: Contract is NOT VANILLA")

    # 2. Test Broker Hard-Lock
    # We'll check the internal execute logic simulation
    broker = DerivBroker()
    # In broker.py line 154 we added a hard lock: stake=0.35
    # Let's verify our manual edit in broker.py was correct
    with open("bot/broker/deriv/broker.py", "r") as f:
        content = f.read()
        if "stake=0.35" in content and "volume=0.35" in content:
            print("✅ PASSED: Broker.py Hard-Locked to 0.35")
        else:
            print("❌ FAILED: Broker.py is NOT Hard-Locked")

    # 3. Verify side mapping
    test_sell = {"asset": "1HZ10V", "side": "SELL"}
    payload_sell = map_trade(test_sell)
    print(f"Sell Mapping: {payload_sell['contract_type']} (Expected VANILLALONGPUT)")
    if payload_sell['contract_type'] == "VANILLALONGPUT":
        print("✅ PASSED: Sell mapped to VANILLALONGPUT")
    else:
        print("❌ FAILED: Sell mapping incorrect")

if __name__ == "__main__":
    asyncio.run(verify_logic())
