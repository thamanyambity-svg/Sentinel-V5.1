from datetime import datetime

_RUNTIME = {
    "started_at": datetime.utcnow(),
    "last_heartbeat": None,
    "last_execution": None
}

def mark_heartbeat():
    _RUNTIME["last_heartbeat"] = datetime.utcnow()

def mark_execution():
    _RUNTIME["last_execution"] = datetime.utcnow()

def get_runtime_state():
    return {
        "started_at": _RUNTIME["started_at"].isoformat(),
        "last_heartbeat": (
            _RUNTIME["last_heartbeat"].isoformat()
            if _RUNTIME["last_heartbeat"] else None
        ),
        "last_execution": (
            _RUNTIME["last_execution"].isoformat()
            if _RUNTIME["last_execution"] else None
        )
    }
