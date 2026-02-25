import asyncio
import json
import ssl
import websockets

import os
from dotenv import load_dotenv

import logging
import sys
from datetime import datetime

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_operations.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("DERIV_TOKEN")
APP_ID = os.getenv("DERIV_APP_ID")

async def check_with_retry(func, max_retries=3):
    """Exécute une fonction avec logique de retry exponentielle"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentative {attempt + 1}/{max_retries}")
            await func()
            logger.info("✅ Check réussi")
            return True
            
        except ConnectionError as e:
            logger.error(f"❌ Erreur de connexion: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.warning(f"⏳ Attente de {wait_time}s avant retry...")
                await asyncio.sleep(wait_time)
            else:
                logger.critical("🚨 Échec après toutes les tentatives")
                raise
        except Exception as e:
            logger.error(f"❌ Erreur inattendue: {e}")
            if attempt < max_retries - 1:
                 await asyncio.sleep(1)
            else:
                 raise

# Renaming main to check for consistency with Retry Logic
async def check():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    uri = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    
    logger.info(f"Connecting to Deriv...")
    async with websockets.connect(uri, ssl=ssl_context) as ws:
        # Auth
        await ws.send(json.dumps({"authorize": TOKEN}))
        auth = json.loads(await ws.recv())
        if "error" in auth:
            print(f"❌ Auth Error: {auth['error']['message']}")
            return

        print(f"✅ Authenticated as {auth['authorize']['email']}")
        
        # Balance
        await ws.send(json.dumps({"balance": 1}))
        bal = json.loads(await ws.recv())
        print(f"💰 Current Balance: {bal['balance']['balance']} {bal['balance']['currency']}")
        
        # Portfolio (Open Positions)
        await ws.send(json.dumps({"portfolio": 1}))
        port = json.loads(await ws.recv())
        
        if "portfolio" in port and "contracts" in port["portfolio"]:
            positions = port["portfolio"]["contracts"]
            print(f"📦 Open Positions: {len(positions)}")
            for p in positions:
                print(f" - {p['contract_id']} | {p['contract_type']} | Buy: {p['buy_price']} | Payout: {p['payout']}")
        else:
            print("📦 No Open Positions.")

        # Profit Table (Last 5 trades)
        print("\n📜 Last 5 Trades:")
        await ws.send(json.dumps({"profit_table": 1, "description": 1, "limit": 5}))
        pt = json.loads(await ws.recv())
        if "profit_table" in pt and "transactions" in pt["profit_table"]:
            for t in pt["profit_table"]["transactions"]:
                # print(f" - {t}") # Debug full object
                buy = float(t.get('buy_price', 0))
                sell = float(t.get('sell_price', 0))
                pnl = sell - buy
                time_code = t.get('purchase_time', t.get('transaction_time', 'N/A'))
                print(f" - {time_code} | {t.get('shortcode', 'N/A')} | Buy: {buy} | Sell: {sell} | PnL: {pnl}")

async def main_wrapper():
    await check_with_retry(check)

if __name__ == "__main__":
    asyncio.run(main_wrapper())
