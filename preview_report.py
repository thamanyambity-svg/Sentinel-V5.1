
import os
import ssl
import certifi

# --- PATCH DE SÉCURITÉ SSL POUR MAC (DOIT ÊTRE EN PREMIER) ---
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
try:
    _create_unverified_https_context = ssl._create_unverified_context
    ssl._create_default_https_context = _create_unverified_https_context
except AttributeError:
    pass

import discord
import asyncio
from dotenv import load_dotenv
from datetime import datetime

# Load Env
load_dotenv("bot/.env")
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

class PreviewClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        channel = self.get_channel(CHANNEL_ID)
        
        # --- SAMPLE DATA ---
        report_data = {
            "trade_id": "PREVIEW-999",
            "asset": "Volatility 10 (1s) Index",
            "duration": "1m 30s",
            "stake": 0.35, # requested stake
            "pnl": 0.29,   # Typical scalp profit
            "entry_balance": 100.00,
            "new_balance": 100.29,
            "result": "WIN"
        }
        
        pnl = report_data.get("pnl", 0.0)
        is_win = pnl > 0
        
        # --- EXACT LOGIC FROM BOT (Updated) ---
        embed = discord.Embed(
            title="💰 RÉSULTAT DU TRADE (PREVIEW)", 
            color=0x00ff00 if is_win else 0xff0000,
            timestamp=datetime.now()
        )
        embed.add_field(name="🆔 ID", value=report_data.get("trade_id", "N/A"), inline=True)
        embed.add_field(name="💼 Marché", value=f"**{report_data.get('asset', 'UNK')}**", inline=True)
        embed.add_field(name="⏱️ Durée", value=f"{report_data.get('duration', 'N/A')}", inline=True)

        embed.add_field(name="💰 Mise", value=f"**{report_data.get('stake', 0.0):.2f}$**", inline=True)
        embed.add_field(name="📉 P/L", value=f"**{pnl:+.2f}$**", inline=True)
        embed.add_field(name="📊 Résultat", value=f"**{'WIN' if is_win else 'LOSS'}**", inline=True)

        embed.add_field(name="🏦 Solde Avant", value=f"{report_data.get('entry_balance', 0):.2f}$", inline=True)
        embed.add_field(name="🏦 Solde Après", value=f"**{report_data.get('new_balance', 0):.2f}$**", inline=True)
        
        if is_win:
            embed.set_thumbnail(url="https://img.icons8.com/color/96/check-circle--v1.png")
            embed.set_footer(text="✅ SUCCÈS - Stratégie Validée")
        else:
            embed.set_thumbnail(url="https://img.icons8.com/color/96/cancel--v1.png")
            embed.set_footer(text="❌ ÉCHEC - Stop Loss Touché")
            
        await channel.send(embed=embed)
        print("Preview sent successfully!")
        await self.close()

if __name__ == "__main__":
    intents = discord.Intents.default()
    client = PreviewClient(intents=intents)
    client.run(TOKEN)
