
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from bot.ai_agents.quant_predictor import QuantPredictor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SAFETY_TEST")

def test_oracle_safety():
    logger.info("🛡️ TEST: Oracle vs Empty Buffer")
    
    predictor = QuantPredictor()
    
    # 1. Test with EMPTY list
    try:
        logger.info("👉 Testing with 0 candles...")
        res = predictor.predict("R_100", [])
        if res is None:
            logger.info("✅ PASS: Result is None (Safe)")
        else:
            logger.error(f"❌ FAIL: Returned {res}")
    except Exception as e:
        logger.error(f"❌ CRASH: {e}")

    # 2. Test with 1 candle (User's specific worry)
    try:
        logger.info("👉 Testing with 1 candle...")
        fake_candles = [{"close": 100.0}]
        res = predictor.predict("R_100", fake_candles)
        if res is None:
            logger.info("✅ PASS: Result is None (Safe)")
        else:
            logger.error(f"❌ FAIL: Returned {res}")
    except Exception as e:
        logger.error(f"❌ CRASH: {e}")

    # 3. Test with 59 candles (Boundary)
    try:
        logger.info("👉 Testing with 59 candles (Need 60)...")
        fake_candles = [{"close": 100.0 + i} for i in range(59)]
        res = predictor.predict("R_100", fake_candles)
        if res is None:
            logger.info("✅ PASS: Result is None (Safe)")
        else:
            logger.error(f"❌ FAIL: Returned {res}")
    except Exception as e:
        logger.error(f"❌ CRASH: {e}")

if __name__ == "__main__":
    test_oracle_safety()
