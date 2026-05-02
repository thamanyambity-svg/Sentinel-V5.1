from typing import Any, Dict, List, Tuple


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_status_payload(data: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return False, ["status payload must be an object"]
    if "positions" in data and not isinstance(data["positions"], list):
        errors.append("positions must be a list")
    for key in ("balance", "equity"):
        if key in data and not _is_number(data[key]):
            errors.append(f"{key} must be numeric")
    return len(errors) == 0, errors


def validate_trade_history_payload(data: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return False, ["trade_history payload must be an object"]
    trades = data.get("trades")
    if trades is None:
        errors.append("missing trades")
        return False, errors
    if not isinstance(trades, list):
        return False, ["trades must be a list"]
    for i, t in enumerate(trades):
        if not isinstance(t, dict):
            errors.append(f"trades[{i}] must be an object")
            continue
        if "pnl" in t and not _is_number(t["pnl"]):
            errors.append(f"trades[{i}].pnl must be numeric")
        if "time_open" in t and not _is_number(t["time_open"]):
            errors.append(f"trades[{i}].time_open must be numeric timestamp")
    return len(errors) == 0, errors


def validate_ml_signal_payload(data: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return False, ["ml_signal payload must be an object"]
    if "confidence" in data and not _is_number(data["confidence"]):
        errors.append("confidence must be numeric")
    if "direction" in data and not isinstance(data["direction"], str):
        errors.append("direction must be a string")
    return len(errors) == 0, errors

    if "confidence" in data and _is_number(data["confidence"]):
        c = float(data["confidence"])
        if c < 0.0 or c > 1.0:
            errors.append("confidence must be between 0.0 and 1.0")
    if "direction" in data and not isinstance(data["direction"], str):
        errors.append("direction must be a string")
    if "direction" in data and isinstance(data["direction"], str):
        if data["direction"].upper() not in ("BUY", "SELL", "CALL", "PUT", "NEUTRAL"):
            errors.append("direction must be one of BUY/SELL/CALL/PUT/NEUTRAL")
    return len(errors) == 0, errors
