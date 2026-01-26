import requests
from datetime import datetime, timezone

def send_signal(webhook_url, data):
    decision = data.get("decision", "NEUTRAL")
    confidence = data.get("confidence", "MEDIUM")

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
                "value": "OUI" if data.get("risk_allowed") else "NON",
                "inline": True
            },
            {
                "name": "🎯 Probabilité",
                "value": str(data.get("probability", "N/A")),
                "inline": True
            },
            {
                "name": "💰 Conseil Mise",
                "value": str(data.get("stake_advice", "N/A")),
                "inline": True
            },
            {
                "name": "🛑 Raison risque",
                "value": data.get("risk_reason", "N/A"),
                "inline": False
            },
            {
                "name": "📈 Score marché",
                "value": f"{data.get('score', 0)} / 100",
                "inline": False
            },
            {
                "name": "📌 Détails marché",
                "value": "\n".join(f"• {r}" for r in data.get("market_details", [])),
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
            "text": f"Assistant Boursier • {datetime.now(timezone.utc).isoformat()} UTC"
        }
    }

    payload = {
        "embeds": [embed]
    }

    try:
        requests.post(webhook_url, json=payload)
    except Exception as e:
        print(f"Error sending Discord signal: {e}")

def send_report(webhook_url, data):
    """
    Envoie un rapport de P&L (Gain/Perte)
    """
    pnl = data["pnl"]
    is_profit = pnl >= 0
    color = 0x00ff00 if is_profit else 0xff0000
    emoji = "🤑" if is_profit else "💸"
    title = "GAIN RÉALISÉ !" if is_profit else "PERTE ENREGISTRÉE"

    embed = {
        "title": f"{emoji} RAPPORT DE TRADE — {title}",
        "color": color,
        "fields": [
            {
                "name": "Montant P&L",
                "value": f"{'+' if is_profit else ''}{pnl:.2f} USD",
                "inline": True
            },
            {
                "name": "Nouveau Solde",
                "value": f"{data['new_balance']} USD",
                "inline": True
            },
            {
                "name": "Variation Solde",
                "value": f"{data['percent_change']:.2f}%",
                "inline": False
            }
        ],
        "footer": {
            "text": f"Suivi de Compte • {datetime.now(timezone.utc).isoformat()} UTC"
        }
    }

    payload = {"embeds": [embed]}
    try:
        requests.post(webhook_url, json=payload)
    except Exception as e:
        print(f"Error sending Discord report: {e}")
