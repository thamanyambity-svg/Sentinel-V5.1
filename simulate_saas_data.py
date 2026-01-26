import requests
import random
import time

# Simulation de trades pour tester le dashboard Antigravity
URL = "http://localhost:3000/api/webhooks/sentinel"
SECRET = "une_phrase_super_secrete_123"

def send_mock_trade(ticket, symbol, profit):
    payload = {
        "ticket": ticket,
        "symbol": symbol,
        "type": random.choice(["BUY", "SELL"]),
        "open_price": 1.0500 + random.uniform(-0.01, 0.01),
        "close_price": 1.0550 + random.uniform(-0.01, 0.01),
        "profit": profit,
        "duration": random.randint(60, 3600)
    }
    
    headers = {"Authorization": f"Bearer {SECRET}"}
    
    try:
        r = requests.post(URL, json=payload, headers=headers)
        if r.status_code == 200:
            print(f"✅ Mock Trade {ticket} sent ({symbol}: {profit}$)")
        else:
            print(f"❌ Error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    print("🚀 Début de la simulation de trades...")
    assets = ["EURUSD", "GOLD", "GBPUSD", "Nvidia", "Apple"]
    
    # On génère 10 trades pour créer une courbe
    for i in range(10):
        t = 2026000 + i
        s = random.choice(assets)
        p = round(random.uniform(-20, 50), 2) # Profit entre -20 et +50
        send_mock_trade(t, s, p)
        time.sleep(0.5) # Petite pause entre les envois

    print("\n✅ Simulation terminée. Allez vérifier votre Dashboard ! 📈")
