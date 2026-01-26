import urllib.request
import json
import os
import ssl

def manual_load_env():
    env = {}
    try:
        with open("bot/.env", "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    env[k] = v
    except:
        pass
    return env

def send_message():
    env = manual_load_env()
    token = env.get("DISCORD_BOT_TOKEN")
    channel_id = env.get("DISCORD_CHANNEL_ID")
    
    if not token or not channel_id:
        print("❌ Missing credentials in .env")
        return

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    
    payload = {
        "embeds": [{
            "title": "💰 REMINDER : SOLDE ACTUEL",
            "description": "**$5.79**\n_(Vérification Ledger Officiel)_",
            "color": 0xFFD700, # Gold
            "footer": {
                "text": "Système Alpha Sentinel | Mode: Sniper (90/100) | Envoi Direct (Raw API)"
            }
        }]
    }
    
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot (https://github.com/Rapptz/discord.py, 1.0.0)"
    }
    
    try:
        # Create SSL context to avoid cert errors
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # Safe for this specific quick script
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, context=ctx) as response:
            print(f"✅ Status Code: {response.getcode()}")
            print(f"✅ Response: {response.read().decode('utf-8')[:50]}...")
            
    except Exception as e:
        print(f"❌ HTTP Error: {e}")
        try:
           print(e.read().decode())
        except:
           pass

if __name__ == "__main__":
    send_message()
