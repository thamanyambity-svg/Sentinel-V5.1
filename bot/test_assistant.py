import os
import sys

# Hack path
sys.path.append(os.getcwd())

from bot.config import runtime
from bot.discord_interface.notifier import send_signal, send_report

def test_assistant():
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("Set webhook first")
        return

    print("1. Envoi d'un SIGNAL TEST (Assistant)...")
    signal_data = {
        "asset": "TEST_V75_PRO",
        "decision": "APPROVE",
        "confidence": "HIGH",
        "risk_allowed": True,
        "risk_reason": "Assistant Mode",
        "score": 92,
        "market_details": ["RSI: 12.5 (Oversold)", "Trend: Bullish"],
        "probability": "88%",
        "stake_advice": "$75",  # Feature clé
    }
    send_signal(webhook, signal_data)
    print("✅ Signal envoyé.")

    print("2. Envoi d'un RAPPORT P&L TEST...")
    pnl_data = {
        "pnl": 45.50,
        "new_balance": 1045.50,
        "percent_change": 4.5
    }
    send_report(webhook, pnl_data)
    print("✅ Rapport envoyé.")

if __name__ == "__main__":
    test_assistant()
