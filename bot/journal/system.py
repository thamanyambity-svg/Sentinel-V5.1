from datetime import datetime, timezone

_SYSTEM_LOG = []


def log_event(event: str, data=None):
    _SYSTEM_LOG.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "data": data
    })


def last_events(n=5):
    return _SYSTEM_LOG[-n:]
