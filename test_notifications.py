import os
import asyncio
from dotenv import load_dotenv
import logging

# Ensure logs show up
logging.basicConfig(level=logging.INFO)

# Load env vars
load_dotenv('bot/.env')

from bot.telegram_interface.notifier import TelegramNotifier
from bot.discord_interface.discord_api_notifier import DiscordAPINotifier

async def main():
    print("Testing Discord & Telegram APIs...")
    tele = TelegramNotifier()
    disc = DiscordAPINotifier()
    
    print(f"Telegram Token Loaded: {'YES' if tele.token else 'NO'}")
    print(f"Discord Token Loaded: {'YES' if disc.token else 'NO'}")

    print("\nSending Test to Telegram...")
    await tele.send_message("🛠️ *TEST* - Message de test Sentinel V5. Si vous voyez ça, Telegram fonctionne.")
    
    print("\nSending Test to Discord...")
    await disc.send_message("🛠️ **TEST** - Message de test Sentinel V5. Si vous voyez ça, Discord fonctionne.", title="TEST SENTINEL", color=0x3498db)
    
    print("\nDone. Check your apps.")

if __name__ == "__main__":
    asyncio.run(main())
