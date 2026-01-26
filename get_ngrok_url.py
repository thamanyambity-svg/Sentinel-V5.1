from pyngrok import ngrok
import time

print("🔍 Inspecting Ngrok Tunnels...")

# Connect to the ngrok process
tunnels = ngrok.get_tunnels()

if not tunnels:
    print("⚠️ No tunnels found via API. Trying to create one temporarily to see if it works...")
    try:
        url = ngrok.connect(8080).public_url
        print(f"\n✅ SUCCESS! URL GENERATED: {url}/webhook")
        print("\n(You can use this URL for TradingView)")
        # Keep it alive for user to see
        # time.sleep(10) 
    except Exception as e:
        print(f"❌ Failed to create tunnel: {e}")
else:
    print(f"\n✅ FOUND ACTIVE TUNNELS: {len(tunnels)}")
    for t in tunnels:
        print(f"🔗 URL: {t.public_url}/webhook")

print("\n------------------------------------------------")
