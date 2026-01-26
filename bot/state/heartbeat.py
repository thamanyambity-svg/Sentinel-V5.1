from datetime import datetime, timezone

_last_heartbeat = None
_last_execution = None


def heartbeat():
    global _last_heartbeat
    _last_heartbeat = datetime.now(timezone.utc)


def mark_execution():
    global _last_execution
    _last_execution = datetime.now(timezone.utc)


def get_heartbeat():
    return _last_heartbeat


def get_last_execution():
    return _last_execution
