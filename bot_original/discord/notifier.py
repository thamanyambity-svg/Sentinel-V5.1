import requests
from datetime import datetime

def send_signal(webhook_url, data):
    decision = data["decision"]
    confidence = data["confidence"]

    color = {
        "APPROVE": 0x00ff00,
        "REJECT": 0xff0000
    }.get(decision, 0xffff00)

    embed = {
        "title": f"📊 SIGNAL ANALYSÉ — {data['asset']}",
        "color": color,
        "fields": [
            {
                "name": "🟢 Autorisation trading",
                "value": "OUI" if data["risk_allowed"] else "NON",
                "inline": True
            },
            {
                "name": "🛑 Raison risque",
                "value": data["risk_reason"],
                "inline": True
            },
            {
                "name": "📈 Score marché",
                "value": f"{data['score']} / 100",
                "inline": False
            },
            {
                "name": "📌 Détails marché",
                "value": "\n".join(f"• {r}" for r in data["market_details"]),
                "inline": False
            },
            {
                "name": "📊 Statistiques (30j)",
                "value": (
                    f"Win rate : {data['win_rate']} %\n"
                    f"Expectancy : {data['expectancy']}\n"
                    f"Trades : {data['samples']}"
                ),
                "inline": False
            },
            {
                "name": "⚠️ Risque actuel",
                "value": (
                    f"Trades today : {data['trades_today']}\n"
                    f"Série pertes : {data['losing_streak']}\n"
                    f"DD journalier : {data['daily_dd']}"
                ),
                "inline": False
            },
            {
                "name": "🧠 DÉCISION BOT",
                "value": f"{'✅ SIGNAL VALIDÉ' if decision == 'APPROVE' else '❌ SIGNAL REJETÉ'}\n"
                         f"Confiance : {confidence}",
                "inline": False
            }
        ],
        "footer": {
            "text": f"Bot Assistante • {datetime.utcnow().isoformat()} UTC"
        }
    }

    payload = {
        "embeds": [embed]
    }

    requests.post(webhook_url, json=payload)
