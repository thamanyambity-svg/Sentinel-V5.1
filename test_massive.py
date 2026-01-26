import requests
import os
import json

# MASSIVE API CONFIG
# Note: Massive acquired Polygon.io, base URL might still be polygon.io or massive.com
MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY", "")

def test_massive_connection():
    if not MASSIVE_API_KEY:
        print("❌ ERROR: MASSIVE_API_KEY not found in environment.")
        return

    # Using Aggregates/Previous Close (Available on many free tiers)
    url = f"https://api.polygon.io/v2/aggs/ticker/C:EURUSD/prev?adjusted=true&apiKey={MASSIVE_API_KEY}"
    
    print(f"📡 Testing Massive API connection (EURUSD)...")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            if results and isinstance(results, list):
                price = results[0].get('c')
                print(f"✅ SUCCESS! EURUSD Previous Close: {price}")
            else:
                print(f"⚠️ Authenticated but no results found (Might need delayed data access).")
                print(json.dumps(data, indent=2))
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")

if __name__ == "__main__":
    test_massive_connection()
