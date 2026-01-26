from bot.data.ohlc_client import OHLCClient
import asyncio
import json

async def debug():
    client = OHLCClient()
    try:
        print("Fetching EURUSD...")
        # Use the logic from our updated client manually to be sure
        data = await client.get_candles("EURUSD") # Should trigger the forex routing
        
        print("\n--- RAW KEYS ---")
        if isinstance(data, dict):
            print(f"Top Level Keys: {list(data.keys())}")
            if 'data' in data:
                print(f"Data Keys: {list(data['data'].keys())}")
                # Print a sample
                print(f"Sample Data: {data['data']}")
            else:
                print("No 'data' key found.")
                print(data)
        else:
            print(f"Type: {type(data)}")
            print(data)
            
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(debug())
