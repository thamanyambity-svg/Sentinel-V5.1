import json
import time
from pathlib import Path

DECISIONS_FILE = Path("bot/journal/decisions_log.json")

def _init():
    if not DECISIONS_FILE.exists():
        DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DECISIONS_FILE, "w") as f:
            json.dump([], f)

def log_decision(action, payload):
    _init()
    with open(DECISIONS_FILE, "r") as f:
        data = json.load(f)

    data.append({
        "timestamp": int(time.time()),
        "action": action,
        "payload": payload
    })

    with open(DECISIONS_FILE, "w") as f:
        json.dump(data, f, indent=2)
