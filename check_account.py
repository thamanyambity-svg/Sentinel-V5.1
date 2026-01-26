
import asyncio
import os
from dotenv import load_dotenv
import ssl
import certifi
import websockets
import json

# Load env
load_dotenv(os.path.join(os.getcwd(), 'bot/.env'))

# SSL Patch
os.environ['SSL_CERT_FILE'] = certifi.where()
ssl_context = ssl.create_default_context(cafile=certifi.where())

API_TOKEN = os.getenv("DERIV_API_TOKEN")
APP_ID = os.getenv("DERIV_APP_ID", "1089")

async def check_account():
    uri = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    print(f"🔌 Connecting to Deriv (App ID: {APP_ID})...")
    
    async with websockets.connect(uri, ssl=ssl_context) as websocket:
        # 1. Authorize
        await websocket.send(json.dumps({"authorize": API_TOKEN}))
        auth_response = await websocket.recv()
        auth_data = json.loads(auth_response)
        
        if "error" in auth_data:
            print(f"❌ Auth Failed: {auth_data['error']['message']}")
            return

        acct = auth_data['authorize']
        print(f"\n✅ AUTHENTICATED AS:")
        print(f"   👤 Login ID:  {acct['loginid']}")
        print(f"   📧 Email:     {acct['email']}")
        print(f"   💰 Balance:   {acct['balance']} {acct['currency']}")
        print(f"   🏢 Real/Demo: {'DEMO (Virtual)' if int(acct['is_virtual']) else 'REAL (Live)'}")
        
        # 2. Check all accounts linked to this token owner (optional, but useful)
        # Usually just authorize is enough to see the current scope.

if __name__ == "__main__":
    if not API_TOKEN:
        print("❌ No API TOKEN found in .env")
    else:
        asyncio.run(check_account())
