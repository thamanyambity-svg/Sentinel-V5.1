import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv("bot/.env")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

async def send_balance():
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f'Logged in as {client.user}')
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="💰 REMINDER : SOLDE ACTUEL",
                description="**$5.79**",
                color=0xFFD700 # Gold
            )
            embed.set_footer(text="Système Alpha Sentinel | Mode: Sniper (90/100)")
            await channel.send(embed=embed)
            print("✅ Notification Sent.")
        else:
            print("❌ Channel not found.")
        await client.close()

    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(send_balance())
