from dotenv import load_dotenv
import os as _os
_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_env_path = _os.path.join(_root, "bot", ".env")
if _os.path.exists(_env_path):
    load_dotenv(_env_path, override=True)
else:
    load_dotenv()  # .env à la racine du projet

import os
import sys
import ssl
import certifi

# --- PATCH SSL MAC ---
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
try:
    _create_unverified_https_context = ssl._create_unverified_context
    ssl._create_default_https_context = _create_unverified_https_context
except AttributeError:
    pass

import asyncio
import time
import logging

from bot.discord_interface.bot import TradingBot
from bot.telegram_interface.notifier import TelegramNotifier
from bot.bridge.mt5_interface import MT5Bridge
from bot.bridge.mt5_path_resolver import resolve_mt5_files_path

# Logging identique à main.py pour cohérence
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot_xm.log", mode="a"),
    ],
)
logger = logging.getLogger("BOT_XM")


async def xm_loop(bot_instance: TradingBot) -> None:
    """
    Boucle XM-only : ne touche PAS Deriv.
    - Lit le status MT5 / Sentinel
    - Envoie bilan d'ouverture + rapports périodiques sur Discord
    - Laisse l'EA Aladdin Pro V7.19 exécuter tous les trades chez XM
    """
    logger.info("🚀 XM-ONLY Monitor Loop Started")

    mt5_path, _xr = resolve_mt5_files_path(os.getenv("MT5_FILES_PATH"))
    logger.info("🌉 XM MT5 Bridge path (%s): %s", _xr, mt5_path)

    bridge = MT5Bridge(root_path=mt5_path)
    telegram = TelegramNotifier()
    asyncio.create_task(telegram.start_polling(bot_instance, broker=None))

    opening_sent = False
    last_periodic = 0.0

    while True:
        try:
            # Lecture status.json généré par l'EA (ExportFullStatus)
            raw_status = bridge.get_raw_status()
            balance = float(raw_status.get("balance", 0.0))
            positions = raw_status.get("positions", [])

            # Bilan d'ouverture (une seule fois)
            if not opening_sent and balance > 0:
                try:
                    await bot_instance.send_opening_report(balance, mt5_balance=balance)
                    await telegram.send_opening_report(balance, mt5_balance=balance)
                    logger.info("📤 Bilan d'ouverture XM envoyé (Discord + Telegram)")
                except Exception as e:
                    logger.error(f"Opening report failed: {e}")
                opening_sent = True

            # Rapport périodique toutes les 2 minutes
            now = time.time()
            if now - last_periodic >= 120 and balance > 0:
                try:
                    # PnL jour approximatif : equity - balance départ, si dispo
                    pnl_day = 0.0
                    last_metrics = bridge.get_metrics()
                    if last_metrics and "daily_pnl" in last_metrics:
                        pnl_day = float(last_metrics.get("daily_pnl", 0.0))

                    await bot_instance.send_periodic_report(
                        positions, balance, mt5_balance=balance, pnl_day=pnl_day
                    )
                    last_periodic = now
                    logger.info("📡 XM Periodic Report Sent.")
                except Exception as e:
                    logger.error(f"Periodic report failed: {e}")

        except Exception as loop_err:
            logger.error(f"XM Monitor Loop Error: {loop_err}")

        await asyncio.sleep(5)


if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")

    bot = TradingBot(xm_loop)

    if token:
        try:
            logger.info("🚀 Attempting to connect to Discord (XM-only)...")
            bot.run(token)
        except Exception as e:
            logger.error(f"⚠️ DISCORD CONNECTION FAILED: {e}")
            logger.warning("🧱 XM MODE: OFFLINE (No Discord)")
            try:
                asyncio.run(xm_loop(bot))
            except KeyboardInterrupt:
                sys.exit(0)
    else:
        logger.warning("⚠️ No Discord Token found. Running XM loop in OFFLINE MODE.")
        try:
            asyncio.run(xm_loop(bot))
        except KeyboardInterrupt:
            sys.exit(0)

