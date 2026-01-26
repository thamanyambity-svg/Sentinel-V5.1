"""
Logger système : events + audit
Écriture disque simple, robuste, sans dépendances
"""
from pathlib import Path
import json
import time

LOG_DIR = Path("logs")
EVENT_LOG = LOG_DIR / "events.log"
AUDIT_LOG = LOG_DIR / "audit.log"

LOG_DIR.mkdir(exist_ok=True)

def _write(path: Path, payload: dict):
    payload["ts"] = time.time()
    with path.open("a") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

def log_event(event: str, **data):
    _write(EVENT_LOG, {
        "type": "event",
        "event": event,
        **data,
    })

def log_audit(action: str, **data):
    _write(AUDIT_LOG, {
        "type": "audit",
        "action": action,
        **data,
    })
