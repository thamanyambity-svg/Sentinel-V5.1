"""
watchdog.py — P4: surveillance EA (V7.19) + Python
- EA: heartbeat.txt OU fraîcheur de status.json (champ updated + mtime)
- Python: python_heartbeat.txt (écrit par bot.main / main_v719 toutes les 5s)

Usage:
  python3 watchdog.py

Lancer depuis la racine du projet : ./scripts/launch_stack.sh
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / "bot" / ".env")

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from bot.bridge.mt5_path_resolver import resolve_mt5_files_path

_raw_mt5 = os.getenv("MT5_FILES_PATH") or ""
MT5_FILES_PATH, _wd_mt5_reason = resolve_mt5_files_path(_raw_mt5 if _raw_mt5.strip() else None)
MT5_FILES_PATH = MT5_FILES_PATH.rstrip("/")

EA_HEARTBEAT = os.path.join(MT5_FILES_PATH, "heartbeat.txt")
STATUS_JSON = os.path.join(MT5_FILES_PATH, "status.json")
PY_HEARTBEAT = os.path.join(MT5_FILES_PATH, "python_heartbeat.txt")

EA_TIMEOUT = int(os.getenv("EA_HEARTBEAT_TIMEOUT_SEC", "90"))
PY_TIMEOUT = int(os.getenv("PY_HEARTBEAT_TIMEOUT_SEC", "35"))
CHECK_INTERVAL = int(os.getenv("WATCHDOG_CHECK_INTERVAL_SEC", "15"))

BOT_LAUNCH = os.getenv("WATCHDOG_BOT_LAUNCH", "main_v719").strip()
if BOT_LAUNCH == "main_v5":
    BOT_CMD = [sys.executable, str(_ROOT / "bot" / "main_v5.py")]
else:
    BOT_CMD = [sys.executable, "-m", "bot.main_v719"]

AUTO_RESTART = os.getenv("WATCHDOG_AUTO_RESTART", "0").strip().lower() in ("1", "true", "yes")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("WATCHDOG")


def file_age(path: str) -> float:
    try:
        if not os.path.isfile(path):
            return -1.0
        return time.time() - os.path.getmtime(path)
    except OSError:
        return -1.0


def ea_last_seen_age_sec() -> float:
    candidates = []
    ah = file_age(EA_HEARTBEAT)
    if ah >= 0:
        candidates.append(ah)
    if os.path.isfile(STATUS_JSON):
        candidates.append(file_age(STATUS_JSON))
        try:
            with open(STATUS_JSON, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            u = data.get("updated")
            if u is None:
                u = data.get("ts")
            if isinstance(u, (int, float)) and u > 0:
                ts = float(u)
                if ts > 1e12:
                    ts /= 1000.0
                candidates.append(max(0.0, time.time() - ts))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    if not candidates:
        return -1.0
    return min(candidates)


async def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials missing — alert suppressed.")
        return
    try:
        import ssl
        import aiohttp
        import certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        async with aiohttp.ClientSession(connector=connector) as session:
            await session.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )
        logger.info("Telegram alert sent.")
    except Exception as e:
        logger.error("Telegram send failed: %s", e)


def restart_bot():
    logger.warning("Restarting Python bot: %s (cwd=%s)", BOT_CMD, _ROOT)
    try:
        subprocess.Popen(
            BOT_CMD,
            cwd=str(_ROOT),
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Bot restart launched.")
    except Exception as e:
        logger.error("Restart failed: %s", e)


async def run_watchdog():
    ea_alert_sent = False
    py_alert_sent = False

    logger.info("Dual-level Watchdog — MT5 path (%s): %s", _wd_mt5_reason, MT5_FILES_PATH)
    logger.info("  EA signal: heartbeat.txt OR status.json (V7.19) | timeout=%ds", EA_TIMEOUT)
    logger.info("  PY file: %s | timeout=%ds", os.path.basename(PY_HEARTBEAT), PY_TIMEOUT)
    logger.info("  Bot command: %s | auto-restart=%s", BOT_CMD, AUTO_RESTART)

    while True:
        ea_age = ea_last_seen_age_sec()
        py_age = file_age(PY_HEARTBEAT)

        if ea_age < 0 or ea_age > EA_TIMEOUT:
            status = "introuvable (pas de status.json / heartbeat)" if ea_age < 0 else f"silencieux depuis *{int(ea_age)}s*"
            msg = (
                f"⚠️ *WATCHDOG — EA*: {status}\n"
                f"Dossier: `{MT5_FILES_PATH}`\n"
                "Vérifiez MT5, EA Aladdin V7.19 sur le graphique, AutoTrading."
            )
            logger.critical("EA heartbeat issue — best_age=%.0fs", ea_age)
            if not ea_alert_sent:
                await send_telegram(msg)
                ea_alert_sent = True
        else:
            if ea_alert_sent:
                await send_telegram("✅ *WATCHDOG*: EA répond à nouveau (status.json / heartbeat).")
                ea_alert_sent = False
            logger.debug("EA OK — vu il y a %.0fs", ea_age)

        if py_age < 0 or py_age > PY_TIMEOUT:
            status = "introuvable" if py_age < 0 else f"silencieux depuis *{int(py_age)}s*"
            msg = (
                f"⚠️ *WATCHDOG — PYTHON*: `python_heartbeat.txt` {status}.\n"
                "Le bot `bot.main` / `main_v719` ne tourne pas ou ne peut pas écrire dans MT5_FILES_PATH."
            )
            logger.critical("Python heartbeat issue — age=%.0fs", py_age)
            if not py_alert_sent:
                await send_telegram(msg)
                py_alert_sent = True
            if AUTO_RESTART:
                restart_bot()
        else:
            if py_alert_sent:
                await send_telegram("✅ *WATCHDOG*: Python heartbeat rétabli.")
                py_alert_sent = False
            logger.debug("Python OK — %.0fs ago", py_age)

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_watchdog())
