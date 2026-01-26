import discord
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv('bot/.env')

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')

print(f"DEBUG: Token present: {bool(TOKEN)}")
print(f"DEBUG: Channel ID: {CHANNEL_ID}")

class TestClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        try:
            channel = self.get_channel(int(CHANNEL_ID))
            if channel:
                print(f"Found channel: {channel.name}")
                await channel.send("✅ Test de connexion Discord réussi ! Le bot est capable d'envoyer des messages.")
                print("Message envoyé avec succès.")
            else:
                print(f"❌ Impossible de trouver le salon avec l'ID {CHANNEL_ID}")
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi du message : {e}")
        
        await self.close()

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERREUR: Pas de token Discord trouvé dans bot/.env")
    else:
        intents = discord.Intents.default()
        client = TestClient(intents=intents)
        try:
            client.run(TOKEN)
        except Exception as e:
            print(f"❌ Erreur de connexion : {e}")
