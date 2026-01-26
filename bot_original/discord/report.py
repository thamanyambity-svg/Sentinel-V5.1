import json
import urllib.request


def send_post_trade(webhook: str, report: dict):
    color = 0x2ecc71 if report["pnl"] >= 0 else 0xe74c3c

    embed = {
        "title": "📊 Trade exécuté",
        "color": color,
        "fields": [
            {"name": "Asset", "value": report["asset"], "inline": True},
            {"name": "Side", "value": report["side"], "inline": True},
            {"name": "PnL", "value": str(report["pnl"]), "inline": True},
            {
                "name": "Stats",
                "value": (
                    f"Win rate: {report['stats']['win_rate']}%\n"
                    f"Expectancy: {report['stats']['expectancy']}\n"
                    f"Trades: {report['stats']['samples']}"
                ),
                "inline": False
            }
        ]
    }

    payload = {
        "embeds": [embed]
    }

    req = urllib.request.Request(
        webhook,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    urllib.request.urlopen(req)
