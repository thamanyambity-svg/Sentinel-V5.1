import asyncio
import logging
import sys

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')

try:
    from bot.ai_agents.orchestrator import AIOrchestrator
except ImportError:
    # Fix path if run from root
    import sys
    import os
    sys.path.append(os.getcwd())
    from bot.ai_agents.orchestrator import AIOrchestrator

async def test_ml_integration():
    print("🧪 Testing ML Integration in Orchestrator...")
    
    orch = AIOrchestrator()
    
    # Dummy Context
    market_data = {"regime": "RANGE_CALM", "price": 1000.0}
    account_state = {"equity": 5000.0, "dd_global": 0.0}
    
    # Dummy Signal
    signal = {
        "asset": "R_100", 
        "side": "BUY", 
        "score": 0.8,
        "raw_data": {"rsi": 30, "atr": 1.5} # Should trigger high probability win? Or unknown
    }
    
    print("📤 Sending Signal...")
    approved, reason, details = await orch.evaluate_signal(signal, market_data, account_state)
    
    print(f"📥 Result: Approved={approved} | Reason={reason}")
    print(f"🧠 ML Confidence in Signal: {signal.get('ml_confidence', 'N/A')}")
    
    if 'ml_confidence' in signal:
        print("✅ SUCCESS: ML Score injected.")
    else:
        print("❌ FAILURE: ML Score missing.")

if __name__ == "__main__":
    asyncio.run(test_ml_integration())
