import json
import logging
import hashlib
import uuid
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
    
logger = logging.getLogger("AUDIT")

AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "../journal/ai_audit.jsonl")

def log_event(
    event_type: str,
    symbol: str,
    payload: Dict[str, Any],
    timeframe: str = "M1"
):
    """
    Logs a structured event to the audit trail (Institutional Schema)
    
    Args:
        event_type: MARKET | SIGNAL | DECISION | TRADE | RISK | SYSTEM
        symbol: Trading symbol (e.g., R_100)
        payload: Event-specific data
        timeframe: Chart timeframe
    """
    event_entry = {
        "event_id": str(uuid.uuid4()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "timeframe": timeframe,
        "event_type": event_type,
        "payload": payload
    }
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
        
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(event_entry) + "\n")
        
        # Verbose logging for critical events
        if event_type in ("DECISION", "TRADE", "RISK"):
            logger.info(f"[AUDIT][{event_type}] {symbol} - {json.dumps(payload)}")
            
    except Exception as e:
        logger.error(f"[AUDIT] Failed to log event {event_type}: {e}")

def log_decision(
    signal_id: str,
    symbol: str,
    regime: str,
    agent_votes: Dict[str, Any],
    final_decision: str,
    blocked_by: str,
    equity: float,
    dd_global: float
):
    """Legacy wrapper for signal decisions, maps to structured schema"""
    payload = {
        "signal_id": signal_id,
        "regime": regime,
        "agent_votes": agent_votes,
        "final_decision": final_decision,
        "blocked_by": blocked_by,
        "equity": equity,
        "dd_global": dd_global
    }
    log_event("DECISION", symbol, payload)

def generate_signal_id(symbol: str, timestamp: str, price: float) -> str:
    """Generate deterministic signal ID"""
    data = f"{symbol}_{timestamp}_{price}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def get_recent_events(limit: int = 100, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve recent events, optionally filtered by type"""
    events = []
    if not os.path.exists(AUDIT_LOG_PATH):
        return []
        
    try:
        with open(AUDIT_LOG_PATH, "r") as f:
            lines = f.readlines()
            for line in reversed(lines):
                if len(events) >= limit:
                    break
                entry = json.loads(line)
                if event_type and entry.get("event_type") != event_type:
                    continue
                events.append(entry)
        return events
    except Exception as e:
        logger.error(f"[AUDIT] Failed to read logs: {e}")
        return []
