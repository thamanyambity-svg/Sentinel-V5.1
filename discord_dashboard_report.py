
import os
import json
import asyncio
import pandas as pd
from datetime import datetime
from pathlib import Path
from bot.discord_interface.discord_api_notifier import DiscordAPINotifier

# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════

MT5_DIR = Path("/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files")

FILES = {
    "status":  MT5_DIR / "status.json",
    "bb_entry": MT5_DIR / "aladdin_bb_entry.csv",
    "bb_exit":  MT5_DIR / "aladdin_bb_exit.csv",
    "bb_live":  MT5_DIR / "aladdin_bb_evolution.csv",
}

async def send_dashboard_report():
    notifier = DiscordAPINotifier()
    
    # 1. Lire status.json
    status_data = {}
    if FILES["status"].exists():
        try:
            with open(FILES["status"], "r") as f:
                status_data = json.load(f)
        except Exception as e:
            print(f"Error reading status: {e}")

    balance = status_data.get("balance", 0.0)
    equity = status_data.get("equity", 0.0)
    trading = "✅ ACTIF" if status_data.get("trading") else "🔴 DÉSACTIVÉ"
    positions = status_data.get("positions", [])
    pnl_open = sum(p.get("pnl", 0) for p in positions)

    # 2. Lire les dernières entrées Black Box
    last_entries = ""
    if FILES["bb_entry"].exists():
        try:
            df = pd.read_csv(FILES["bb_entry"])
            if not df.empty:
                last = df.tail(3)
                for _, row in last.iterrows():
                    last_entries += f"• **{row['Symbol']}** ({row['Type']}) @ {row['Entry']} | Conf: {row['Conf']}\n"
        except Exception:
            last_entries = "N/A"

    # 3. Lire les dernières sorties Black Box
    last_exits = ""
    if FILES["bb_exit"].exists():
        try:
            df = pd.read_csv(FILES["bb_exit"])
            if not df.empty:
                last = df.tail(3)
                for _, row in last.iterrows():
                    res = "🟢" if row['Profit'] >= 0 else "🔴"
                    last_exits += f"{res} **{row['Symbol']}**: {row['Profit']}$ ({row['Reason']})\n"
        except Exception:
            last_exits = "N/A"

    # 4. Construire l'embed
    color = 0x2ecc71 if pnl_open >= 0 else 0xe74c3c
    
    report_content = (
        f"💰 **SOLDE COMPTE**\n"
        f"💵 Balance : `{balance:,.2f}$` | Equity : `{equity:,.2f}$`\n"
        f"📊 PnL Ouvert : **{pnl_open:+.2f}$**\n"
        f"🤖 Bot Status : {trading}\n\n"
        
        f"📥 **DERNIÈRES ENTRÉES**\n"
        f"{last_entries if last_entries else '_Aucune entrée récente_'}\n"
        
        f"📤 **DERNIÈRES SORTIES**\n"
        f"{last_exits if last_exits else '_Aucune sortie récente_'}\n"
    )

    await notifier.send_message(
        content=report_content,
        title="🚀 ALADDIN PRO V7 — RAPPORT LIVE",
        color=color
    )
    print("✅ Rapport envoyé à Discord.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    # Prioriser le .env dans le dossier bot/
    env_path = Path("/Users/macbookpro/Downloads/bot_project/bot/.env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
    asyncio.run(send_dashboard_report())
