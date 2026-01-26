import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
TRADES_FILE = os.path.join(BASE_DIR, "trade_log.json")


def _ensure_file():
    if not os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "w") as f:
            json.dump([], f)


def log_trade(asset: str, side: str, pnl: float):
    """
    Enregistre un trade exécuté
    """
    _ensure_file()

    with open(TRADES_FILE, "r") as f:
        trades = json.load(f)

    trades.append({
        "timestamp": datetime.utcnow().isoformat(),
        "asset": asset,
        "side": side,
        "pnl": pnl
    })

    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)


def load_trades():
    """
    Charge l’historique des trades
    """
    _ensure_file()
    with open(TRADES_FILE, "r") as f:
        return json.load(f)


def reset_trades():
    """
    🔥 RESET COMPLET DU JOURNAL (H23)
    """
    with open(TRADES_FILE, "w") as f:
        json.dump([], f)
