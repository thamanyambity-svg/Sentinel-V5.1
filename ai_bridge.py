"""
SENTINEL V10 — ai_bridge.py
Maillon manquant : MQL5 JSON ↔ Sentinel HTTP

Flux :
  EA MQL5  →  ai_request.json   →  ce script  →  Sentinel (/evaluate)
                                       ↓
                         ai_response.json / ai_error.json  →  EA

Objectifs :
  - Validation basique du schéma de ai_request.json
  - Appel HTTP sécurisé vers Sentinel (API key, timeout, retries)
  - Healthcheck /health au démarrage puis périodique
  - Gestion propre des erreurs via ai_error.json
"""

import json
import time
import logging
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# Config centralisée
sys.path.insert(0, str(Path(__file__).parent))
from config import cfg, setup_logging  # type: ignore

setup_logging(cfg)
log = logging.getLogger("AIBridge")


# =====================================================================
#  Validation minimale du schéma de ai_request.json
# =====================================================================

REQUIRED_FIELDS = {"id", "type", "priority", "payload"}
VALID_TYPES = {
    "COMMUNICATOR_REPORT",
    "SESSION_REVIEW",
    "ML_INSIGHT",
    "NEWS_ALERT",
    "DATA_MINING_EMBED",
}
VALID_PRIORITIES = {"NORMAL", "HIGH", "CRITICAL"}


def validate_request(data: dict) -> Tuple[bool, str]:
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        return False, f"champs manquants: {sorted(missing)}"

    if data.get("type") not in VALID_TYPES:
        return False, f"type invalide: {data.get('type')}"

    if data.get("priority") not in VALID_PRIORITIES:
        return False, f"priorité invalide: {data.get('priority')}"

    payload = data.get("payload")
    if not isinstance(payload, dict):
        return False, "payload doit être un objet JSON"

    if "technical_log" not in payload or not isinstance(
        payload.get("technical_log"), str
    ):
        return False, "payload.technical_log manquant ou invalide"

    req_id = data.get("id", "")
    if not isinstance(req_id, str) or not req_id:
        return False, "id invalide"

    return True, ""


# =====================================================================
#  Client HTTP Sentinel
# =====================================================================


class SentinelClient:
    """Client HTTP léger vers sentinel_server.py (FastAPI)."""

    def __init__(self) -> None:
        self.base_url = f"http://{cfg.SENTINEL_HOST}:{cfg.SENTINEL_PORT}"
        self.api_key = cfg.SENTINEL_API_KEY
        self.timeout = cfg.BRIDGE_REQUEST_TIMEOUT_SEC
        self.max_retry = cfg.BRIDGE_MAX_RETRIES
        self._alive = False

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST JSON avec timeout + retries + backoff simple."""
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(payload).encode("utf-8")

        for attempt in range(1, self.max_retry + 1):
            try:
                req = urllib.request.Request(
                    url, data=body, headers=self._headers(), method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                log.error(
                    "HTTP %d sur %s (tentative %d/%d): %s",
                    e.code,
                    endpoint,
                    attempt,
                    self.max_retry,
                    err_body[:200],
                )
                # Erreurs client -> pas de retry
                if e.code in (400, 401, 422):
                    raise
            except urllib.error.URLError as e:
                log.warning(
                    "Connexion Sentinel impossible (tentative %d/%d): %s",
                    attempt,
                    self.max_retry,
                    e.reason,
                )
                self._alive = False
            except Exception as e:  # pragma: no cover - garde-fou
                log.error(
                    "Erreur inattendue (tentative %d/%d): %s",
                    attempt,
                    self.max_retry,
                    e,
                )

            if attempt < self.max_retry:
                time.sleep(2**attempt)  # backoff exponentiel simple

        raise ConnectionError(f"Sentinel injoignable après {self.max_retry} tentatives")

    def health_check(self) -> bool:
        """GET /health pour vérifier que Sentinel est up."""
        url = f"{self.base_url}/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            alive = data.get("status") == "ok"
            if alive and not self._alive:
                log.info(
                    "✅ Sentinel en ligne — uptime=%ss",
                    data.get("uptime_sec", 0),
                )
            self._alive = alive
            return alive
        except Exception as e:
            if self._alive:
                log.warning("❌ Sentinel est tombé: %s", e)
            self._alive = False
            return False

    def evaluate(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Construit un payload minimal pour /evaluate à partir de ai_request.json."""
        payload = request_data.get("payload", {})
        tech_log = payload.get("technical_log", "")

        parsed = _parse_technical_log(tech_log)

        sent_payload = {
            "action": parsed.get("action", "HOLD"),
            "asset": parsed.get("asset", "XAUUSD"),
            "tech_signal": parsed.get("tech_signal", 0.0),
            "imbalance": parsed.get("imbalance", 0.0),
            "rsi": parsed.get("rsi"),
            "adx": parsed.get("adx"),
            "atr": parsed.get("atr"),
        }
        return self._post("/evaluate", sent_payload)


def _parse_technical_log(log_text: str) -> Dict[str, Any]:
    """
    Parse le log généré par _BuildContextLog() + extra dans MQL5.
    Format générique: 'key: value | key: value | ...'
    """
    result: Dict[str, Any] = {
        "action": "HOLD",
        "asset": "XAUUSD",
        "tech_signal": 0.0,
        "imbalance": 0.0,
        "rsi": None,
        "adx": None,
        "atr": None,
    }

    if not log_text:
        return result

    parts = [p.strip() for p in log_text.split("|") if ":" in p]
    for part in parts:
        key, _, val = part.partition(":")
        key = key.strip().lower()
        val = val.strip()
        try:
            if key.startswith("sym"):
                result["asset"] = val.upper()
            elif "dir" in key:
                if "buy" in val.upper():
                    result["action"] = "BUY"
                    result["tech_signal"] = 1.0
                elif "sell" in val.upper():
                    result["action"] = "SELL"
                    result["tech_signal"] = -1.0
            elif "rsi" in key:
                result["rsi"] = float(val.replace("%", ""))
            elif "adx" in key:
                result["adx"] = float(val)
            elif "atr" in key:
                result["atr"] = float(val)
            elif "pnl" in key:
                pnl = float(val.replace("$", "").strip())
                # normalisation simple du PnL en imbalance [-1,1]
                result["imbalance"] = max(-1.0, min(1.0, pnl / 100.0))
        except ValueError:
            continue

    return result


# =====================================================================
#  Gestion des fichiers ai_request / ai_response / ai_error
# =====================================================================


class FileInterface:
    """Gestion des fichiers dans le répertoire MT5/Files."""

    def __init__(self) -> None:
        self.mt5_dir = Path(cfg.MT5_FILES_PATH)
        self.request_path = self.mt5_dir / cfg.AI_REQUEST_FILE
        self.response_path = self.mt5_dir / cfg.AI_RESPONSE_FILE
        self.error_path = self.mt5_dir / cfg.AI_ERROR_FILE
        self._last_id: Optional[str] = None

    def has_pending_request(self) -> bool:
        return self.request_path.exists() and self.request_path.stat().st_size > 8

    def read_request(self) -> Optional[Dict[str, Any]]:
        try:
            raw = self.request_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            log.error("ai_request.json invalide: %s", e)
            self.write_error("JSON_PARSE_ERROR", str(e))
            self._safe_delete(self.request_path)
            return None
        except Exception as e:
            log.error("Lecture ai_request.json: %s", e)
            return None

        req_id = str(data.get("id", ""))
        if req_id and req_id == self._last_id:
            # déjà traité
            return None
        self._last_id = req_id
        return data

    def write_response(self, text: str, req_id: str = "") -> None:
        payload = {
            "request_id": req_id,
            "result": text,
            "ts": datetime.now().isoformat(),
        }
        try:
            tmp = self.response_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            if self.response_path.exists():
                self.response_path.unlink()
            tmp.rename(self.response_path)
        except Exception as e:  # pragma: no cover
            log.error("Écriture ai_response.json: %s", e)

    def write_error(self, code: str, message: str, req_id: str = "") -> None:
        payload = {
            "error_code": code,
            "message": message[:500],
            "request_id": req_id,
            "ts": datetime.now().isoformat(),
        }
        try:
            self.error_path.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            log.warning("ai_error.json écrit: [%s] %s", code, message[:120])
        except Exception as e:  # pragma: no cover
            log.error("Écriture ai_error.json: %s", e)

    def cleanup_request(self) -> None:
        self._safe_delete(self.request_path)

    def cleanup_error(self) -> None:
        self._safe_delete(self.error_path)

    def _safe_delete(self, path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            log.warning("Suppression %s: %s", path.name, e)

    @staticmethod
    def format_response_text(sentinel_result: Dict[str, Any]) -> str:
        """Texte unique renvoyé à l'EA (affiché via Print)."""
        decision = sentinel_result.get("decision", "HOLD")
        lot_mult = float(sentinel_result.get("lot_multiplier", 1.0))
        prob = float(sentinel_result.get("probability", 0.5))
        reasoning = sentinel_result.get("reasoning", "")
        return (
            f"IA: {decision} | LotMult: {lot_mult:.2f} | "
            f"Prob: {prob:.2f} | {reasoning[:120]}"
        )


# =====================================================================
#  Boucle principale
# =====================================================================


class AIBridge:
    def __init__(self) -> None:
        self.client = SentinelClient()
        self.files = FileInterface()
        self._running = False
        self._processed = 0
        self._errors = 0
        self._last_healthcheck = 0.0
        self._health_interval = 30.0

    def _healthcheck_periodic(self) -> None:
        now = time.time()
        if now - self._last_healthcheck >= self._health_interval:
            self.client.health_check()
            self._last_healthcheck = now

    def _tick(self) -> None:
        self._healthcheck_periodic()
        if not self.files.has_pending_request():
            return

        req = self.files.read_request()
        if req is None:
            return

        req_id = str(req.get("id", ""))
        log.info("Requête AI reçue id=%s type=%s", req_id, req.get("type"))

        valid, err = validate_request(req)
        if not valid:
            log.warning("Requête invalide: %s", err)
            self.files.write_error("SCHEMA_INVALID", err, req_id)
            self.files.cleanup_request()
            self._errors += 1
            return

        if not self.client._alive:
            # Sentinel down : on n'attend pas, on renvoie une erreur bridge
            msg = "sentinel_server injoignable — vérifiez qu'il tourne"
            self.files.write_error("SENTINEL_DOWN", msg, req_id)
            self.files.cleanup_request()
            self._errors += 1
            return

        try:
            result = self.client.evaluate(req)
            text = self.files.format_response_text(result)
            self.files.write_response(text, req_id)
            self.files.cleanup_error()
            self.files.cleanup_request()
            self._processed += 1
            log.info("Réponse envoyée id=%s: %s", req_id, text)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            code = e.code
            if code == 401:
                code_str = "AUTH_FAILED"
                msg = "API key invalide — vérifiez SENTINEL_API_KEY"
            elif code == 422:
                code_str = "PAYLOAD_INVALID"
                msg = f"Payload rejeté par Sentinel: {body}"
            else:
                code_str = f"HTTP_{code}"
                msg = body
            log.error("Erreur HTTP %d: %s", code, msg)
            self.files.write_error(code_str, msg, req_id)
            self.files.cleanup_request()
            self._errors += 1
        except ConnectionError as e:
            log.error("Connexion Sentinel perdue: %s", e)
            self.files.write_error("CONNECTION_ERROR", str(e), req_id)
            self.files.cleanup_request()
            self._errors += 1
        except Exception as e:  # pragma: no cover
            log.error("Erreur inattendue: %s", e, exc_info=True)
            self.files.write_error("INTERNAL_ERROR", str(e), req_id)
            self.files.cleanup_request()
            self._errors += 1

    def start(self, once: bool = False) -> None:
        log.info(
            "AI Bridge démarré — poll=%.1fs timeout=%ds",
            cfg.BRIDGE_POLL_INTERVAL_SEC,
            cfg.BRIDGE_REQUEST_TIMEOUT_SEC,
        )
        # Healthcheck initial (bloquant mais court)
        self.client.health_check()
        self._running = True
        try:
            while self._running:
                self._tick()
                if once:
                    break
                time.sleep(cfg.BRIDGE_POLL_INTERVAL_SEC)
        except KeyboardInterrupt:
            log.info("AI Bridge arrêté (Ctrl+C)")
        finally:
            self._running = False

    def status(self) -> str:
        return (
            f"AIBridge — traités={self._processed} erreurs={self._errors} "
            f"sentinel={'OK' if self.client._alive else 'KO'}"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sentinel V10 — AI Bridge")
    parser.add_argument(
        "--once", action="store_true", help="Traiter une seule requête puis quitter"
    )
    parser.add_argument(
        "--status", action="store_true", help="Tester la connexion à Sentinel"
    )
    args = parser.parse_args()

    bridge = AIBridge()

    if args.status:
        alive = bridge.client.health_check()
        print(
            f"Sentinel {'EN LIGNE' if alive else 'HORS LIGNE'} sur "
            f"http://{cfg.SENTINEL_HOST}:{cfg.SENTINEL_PORT}"
        )
        sys.exit(0 if alive else 1)

    bridge.start(once=args.once)

