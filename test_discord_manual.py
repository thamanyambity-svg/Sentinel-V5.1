
import os
import asyncio
import aiohttp
from dotenv import load_dotenv

# Load from bot/.env as the bot does
env_path = os.path.join(os.getcwd(), "bot", ".env")
load_dotenv(env_path)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

async def test_discord():
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
    payload = {"content": "⚠️ **TEST SENTINEL** - Vérification des notifications Discord."}
    
    print(f"Testing with Token starting with: {TOKEN[:20]}...")
    print(f"Channel ID: {CHANNEL_ID}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                print(f"Status: {resp.status}")
                print(f"Response: {await resp.text()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_discord())
