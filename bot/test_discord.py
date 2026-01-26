import os
import sys

# Hack path
sys.path.append(os.getcwd())

from bot.config import runtime
from bot.discord_interface.notifier import send_signal

def test_discord():
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook or "your/webhook" in webhook:
        print("❌ Webhook non configuré dans bot/.env")
        return

    data = {
        "asset": "TEST_V75",
        "decision": "APPROVE",
        "confidence": "TEST",
        "risk_allowed": True,
        "risk_reason": "Test Manuel",
        "score": 100,
        "market_details": ["Ceci est un test", "Notification manuelle"],
        "win_rate": 50,
        "expectancy": 0.5,
        "samples": 10,
        "trades_today": 0,
        "losing_streak": 0,
        "daily_dd": 0
    }
    
    print(f"Envoi tentative vers : {webhook} ...")
    try:
        send_signal(webhook, data)
        print("✅ Notification envoyée ! Vérifie ton Discord.")
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    test_discord()
