import asyncio
import os
import json
from dotenv import load_dotenv
# Add current dir to path to find bot module
import sys
sys.path.append(os.getcwd())

from bot.broker.deriv.client import DerivClient

# Load env but force manual reading if needed
load_dotenv("bot/.env")

async def fetch_history():
    print("🕵️ Connecting to Deriv API for Forensic Audit...")
    client = DerivClient()
    try:
        await client.connect()
        print("✅ Connected. Fetching Statement...")

        # Request Statement (last 10 transactions)
        req = {
            "statement": 1,
            "description": 1,
            "limit": 10
        }
        resp = await client.send(req)

        if "error" in resp:
            print(f"❌ API Error: {resp['error']['message']}")
            return

        transactions = resp.get("statement", {}).get("transactions", [])
        
        print(f"\n📊 --- OFFICIAL LEDGER (Last {len(transactions)} tx) ---")
        # Sort by time just in case (though API usually returns desc)
        # Actually API returns chronological? We'll print as is.
        for tx in transactions:
            # tx keys: 'action_type', 'amount', 'balance_after', 'contract_id', 'longcode', 'transaction_time'
            time_str = tx.get("transaction_time", "N/A") 
            # Convert timestamp if possible (requires datetime)
            import datetime
            try:
                dt = datetime.datetime.fromtimestamp(int(time_str))
                final_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                final_time = time_str

            action = tx.get("action_type", "UNKNOWN")
            amount = tx.get("amount", 0.0)
            balance = tx.get("balance_after", 0.0)
            desc = tx.get("longcode", "No Description")
            
            print(f"[{final_time}] {action.upper()} | {amount}$ | Bal: {balance}$ | {desc}")
            
    except Exception as e:
        print(f"❌ Crash: {e}")
    finally:
        await client.close()
        print("🔌 Disconnected.")

if __name__ == "__main__":
    asyncio.run(fetch_history())
