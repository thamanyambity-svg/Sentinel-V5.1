from datetime import datetime

_last_heartbeat = None
_last_execution = None


def heartbeat():
    global _last_heartbeat
    _last_heartbeat = datetime.utcnow()


def mark_execution():
    global _last_execution
    _last_execution = datetime.utcnow()


def get_heartbeat():
    return _last_heartbeat


def get_last_execution():
    return _last_execution
