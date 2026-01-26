import asyncio
import os
import logging
from dotenv import load_dotenv
import certifi

# Load Env
load_dotenv(os.path.join(os.path.dirname(__file__), 'bot/.env'))

# SSL Patch
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AUTH_TEST")

from bot.broker.deriv.client import DerivClient

async def test_auth():
    logger.info("TEST: Connecting to Deriv API...")
    client = DerivClient()
    try:
        connected = await client.connect()
        if not connected:
            logger.error("❌ Connection Failed.")
            return

        logger.info("✅ Connected. Fetching Balance...")
        balance = await client.get_balance()
        
        if balance:
            logger.info(f"💰 Balance: {balance}")
        else:
            logger.error("❌ Failed to fetch balance.")
            
    except Exception as e:
        logger.error(f"❌ Exception: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_auth())
