import json
from datetime import datetime

AUDIT_FILE = "bot/journal/audit.log"


def audit(event, actor="system", context=None):
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "event": event,
        "actor": actor,
        "context": context or {}
    }

    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
