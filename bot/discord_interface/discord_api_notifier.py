
import os
import aiohttp
import logging
import asyncio
from datetime import datetime
import ssl
import certifi

# Fix SSL context for macOS
ssl_context = ssl.create_default_context(cafile=certifi.where())

logger = logging.getLogger("DISCORD_API")

class DiscordAPINotifier:
    """
    Direct REST API client for Discord notifications (No bot client needed).
    Uses Bot Token and Channel ID from .env.
    """
    def __init__(self):
        self.token = os.getenv("DISCORD_BOT_TOKEN")
        self.channel_id = os.getenv("DISCORD_CHANNEL_ID")
        self.base_url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages"
        self.headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }

    async def send_message(self, content: str, title: str = None, color: int = 0x3498db):
        if not self.token or not self.channel_id:
            logger.warning("Discord credentials missing. Skipping notification.")
            return

        payload = {"content": content}
        
        # If we want a nice embed
        if title:
            payload = {
                "embeds": [{
                    "title": title,
                    "description": content,
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }

        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                async with session.post(self.base_url, json=payload, headers=self.headers) as response:
                    if response.status not in [200, 201]:
                        logger.error(f"Discord API Error: {await response.text()}")
                    else:
                        logger.info("📡 Notification sent to Discord")
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
