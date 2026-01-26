from datetime import datetime, time, timezone

# Plages UTC autorisées
ALLOWED_WINDOWS = [
    (time(6, 0), time(20, 0)),  # 06:00–20:00 UTC
]

def is_time_allowed(now=None):
    now = now or datetime.now(timezone.utc).time()
    for start, end in ALLOWED_WINDOWS:
        if start <= now <= end:
            return True
    return False
