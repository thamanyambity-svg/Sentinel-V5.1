import asyncio
import os
from dotenv import load_dotenv
from bot.broker.deriv.client import DerivClient

load_dotenv("bot/.env")

async def test_candles():
    client = DerivClient()
    await client.connect()
    
    assets = ["1HZ10V", "frxEURUSD", "frxXAUUSD", "stkNVDA", "stkTSLA"]
    
    for asset in assets:
        print(f"📡 Fetching candles for {asset}...")
        req = {
            "ticks_history": asset,
            "adjust_start_time": 1,
            "count": 5,
            "end": "latest",
            "style": "candles",
            "granularity": 60
        }
        res = await client.send(req)
        if "candles" in res:
            print(f"✅ {asset}: Success! {len(res['candles'])} candles received.")
        else:
            print(f"❌ {asset}: Failed. Resp: {res.get('error', {}).get('message', 'No error message')}")
            
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_candles())
