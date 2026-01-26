from datetime import datetime

_SYSTEM_LOG = []


def log_event(event: str, data=None):
    _SYSTEM_LOG.append({
        "ts": datetime.utcnow().isoformat(),
        "event": event,
        "data": data
    })


def last_events(n=5):
    return _SYSTEM_LOG[-n:]
