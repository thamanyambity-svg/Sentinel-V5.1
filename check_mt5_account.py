#!/usr/bin/env python3
"""Check MT5 real account details via Deriv API"""
import asyncio, os, json, ssl, certifi, websockets
from dotenv import load_dotenv

load_dotenv(os.path.join(os.getcwd(), 'bot/.env'))
ssl_ctx = ssl.create_default_context(cafile=certifi.where())
TOKEN = os.getenv("DERIV_API_TOKEN")
APP_ID = os.getenv("DERIV_APP_ID", "1089")

async def check_mt5():
    uri = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    print(f"🔌 Connecting to Deriv API...")
    async with websockets.connect(uri, ssl=ssl_ctx) as ws:
        # 1. Authorize
        await ws.send(json.dumps({"authorize": TOKEN}))
        auth = json.loads(await ws.recv())
        if "error" in auth:
            print(f"❌ Auth error: {auth['error']['message']}")
            return

        acct = auth["authorize"]
        print(f"✅ Deriv CR: {acct['loginid']} | Balance: {acct['balance']} {acct['currency']}")
        print(f"\n📋 All linked accounts:")
        for a in acct.get("account_list", []):
            tag = "🟡 Demo" if a.get("is_virtual") else "🟢 Real"
            print(f"   {tag} | {a['loginid']} | {a.get('account_type','?')} | {a.get('currency','?')}")

        # 2. MT5 login list
        await ws.send(json.dumps({"mt5_login_list": 1}))
        mt5_resp = json.loads(await ws.recv())
        if "error" in mt5_resp:
            print(f"\n❌ MT5 list error: {mt5_resp['error']['message']}")
        else:
            mt5_list = mt5_resp.get("mt5_login_list", [])
            print(f"\n🏦 MT5 Accounts ({len(mt5_list)}):")
            for m in mt5_list:
                print(f"   ─────────────────────────────────")
                print(f"   Login:    {m.get('login','?')}")
                print(f"   Name:     {m.get('name','?')}")
                print(f"   Balance:  {m.get('balance','?')} {m.get('currency','?')}")
                print(f"   Server:   {m.get('server','?')}")
                print(f"   Type:     {m.get('account_type','?')} / {m.get('market_type','?')}")
                print(f"   Leverage: 1:{m.get('leverage','?')}")
                print(f"   Group:    {m.get('group','?')}")

        # 3. MT5 account 101573422 details
        await ws.send(json.dumps({"mt5_get_settings": 1, "login": "101573422"}))
        resp = json.loads(await ws.recv())
        if "error" in resp:
            print(f"\n⚠️  MT5 101573422 settings: {resp['error']['message']}")
        else:
            s = resp.get("mt5_get_settings", {})
            print(f"\n📊 MT5 101573422 (Std) Details:")
            print(f"   Balance:  {s.get('balance','?')} {s.get('currency','?')}")
            print(f"   Leverage: 1:{s.get('leverage','?')}")
            print(f"   Server:   {s.get('server','?')}")
            print(f"   Group:    {s.get('group','?')}")

if __name__ == "__main__":
    asyncio.run(check_mt5())
