import requests
import os
import time
from dotenv import load_dotenv

load_dotenv("bot/.env")
api_key = os.getenv("MASSIVE_API_KEY")

def test_polygon_candles():
    ticker = "C:EURUSD"
    multiplier = 1
    timespan = "minute"
    
    # Last 100 minutes
    to_ts = int(time.time() * 1000)
    from_ts = to_ts - (100 * 60 * 1000)
    
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_ts}/{to_ts}?apiKey={api_key}"
    
    print(f"📡 Requesting Polygon candles for {ticker}...")
    resp = requests.get(url)
    data = resp.json()
    
    if "results" in data:
        print(f"✅ Success! Received {len(data['results'])} candles.")
        print(f"Latest close: {data['results'][-1]['c']}")
    else:
        print(f"❌ Failed. Resp: {data}")

if __name__ == "__main__":
    test_polygon_candles()
