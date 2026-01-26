import datetime
import json

ERROR_LOG = "bot/journal/errors.log"

def log_error(source: str, error: Exception, context: dict | None = None):
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "source": source,
        "error": str(error),
        "context": context or {}
    }
    with open(ERROR_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
