#!/usr/bin/env python3
"""
SENTINEL V4.7 - DISCORD REPORTING ENGINE
Version: 2.0.0 | Format: Institutional Trading Reports
"""

import json
import requests
import os
import sys
import time
import statistics
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path to allow 'bot' imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(project_root)

# Load Environment from bot/.env
env_path = os.path.join(project_root, 'bot', '.env')
load_dotenv(dotenv_path=env_path)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

from bot.bridge.mt5_interface import COMMAND_PATH # Import global path

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("reporter.log"), logging.StreamHandler()]
)
logger = logging.getLogger("REPORTER")

# Path Configuration
MT5_FILES_ROOT = Path(COMMAND_PATH).parent

class InstitutionalDiscordReporter:
    """Générateur de rapports Discord aux normes institutionnelles"""
    
    def __init__(self, watch_dir: Path):
        self.watch_dir = watch_dir
        self.archive_dir = watch_dir / "Archived_Reports"
        self.archive_dir.mkdir(exist_ok=True)
        
        logger.info(f"🚀 Reporter Initialized. Watching: {self.watch_dir}")
        logger.info(f"📂 Archive Dir: {self.archive_dir}")
        
    def send_trade_report(self, report_data: dict) -> bool:
        """Envoie un rapport de trade professionnel à Discord"""
        
        trade = report_data.get('trade', {})
        # Note: Sentinel v4.7 generated a basic JSON.
        reason = trade.get("reason", "UNKNOWN")
        ticket = trade.get("ticket", "N/A")
        symbol = trade.get("symbol", "N/A")
        balance = trade.get("balance_after", 0.0)
        net_profit = trade.get("net_profit", 0.0)
        
        # Color Logic
        color = 0x2ecc71 if float(net_profit) >= 0 else 0xe74c3c
        
        embed = {
            "title": f"📊 TRADE CLOSED - {symbol}",
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": f"Sentinel V4.7 • Ticket #{ticket}"},
            "fields": [
                {"name": "🆔 Ticket", "value": str(ticket), "inline": True},
                {"name": "💱 Symbol", "value": symbol, "inline": True},
                {"name": "🏁 Reason", "value": reason, "inline": True},
                {"name": "💰 Net PnL", "value": f"${float(net_profit):+.2f}", "inline": True},
                {"name": "🏦 Balance After", "value": f"${float(balance):.2f}", "inline": True}
            ]
        }
        
        # Payload Construction
        payload = {
            "embeds": [embed]
        }
        
        # SENDING LOGIC (Webhook vs Bot Token)
        try:
            if DISCORD_WEBHOOK_URL:
                # Webhook Mode
                payload["username"] = "Sentinel Reporter"
                response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
                return response.status_code in [200, 204]
                
            elif DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID:
                # Bot Token Mode
                url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
                headers = {
                    "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
                    "Content-Type": "application/json"
                }
                response = requests.post(url, headers=headers, json=payload, timeout=10)
                
                if response.status_code not in [200, 201]:
                    logger.error(f"❌ Discord API Error: {response.status_code} - {response.text}")
                    return False
                return True
            else:
                logger.error("❌ No Discord Configuration Found (Webhook or Token+Channel)")
                return False
                
        except Exception as e:
            logger.error(f"❌ Discord Send Error: {e}")
            return False

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL and not (DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID):
        logger.critical("❌ Missing Discord Config in .env")
        logger.critical("   Need either: DISCORD_WEBHOOK_URL OR (DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID)")
        exit(1)
        
    reporter = InstitutionalDiscordReporter(MT5_FILES_ROOT)
    
    logger.info("👀 Watching for 'trade_report_*.json'...")
    
    while True:
        try:
            for report_file in reporter.watch_dir.glob("trade_report_*.json"):
                try:
                    logger.info(f"🔎 Found Report: {report_file.name}")
                    
                    with open(report_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if reporter.send_trade_report(data):
                        logger.info("✅ Sent to Discord.")
                        target = reporter.archive_dir / report_file.name
                        if target.exists(): target.unlink()
                        report_file.rename(target)
                    else:
                        logger.warning("⚠️ Failed to send (Check Logs). Retrying later.")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing {report_file.name}: {e}")
            
            time.sleep(2)
            
        except KeyboardInterrupt:
            logger.info("🛑 Stopping Reporter.")
            break
        except Exception as e:
            logger.error(f"❌ Loop Error: {e}")
            time.sleep(5)
