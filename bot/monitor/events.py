import json
import time
from pathlib import Path

LOG_FILE = Path("runtime/events.log")


def log_event(event: str, payload: dict | None = None):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "ts": time.time(),
        "event": event,
        "payload": payload or {},
    }

    with LOG_FILE.open("a") as f:
        f.write(json.dumps(record) + "\n")
