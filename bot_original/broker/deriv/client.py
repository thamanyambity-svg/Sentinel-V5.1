"""
Client websocket Deriv avec health + error guard
"""
import json
import websocket

from bot.config.secrets import get_deriv_api_key
from bot.broker.deriv.health import (
    mark_connected,
    mark_disconnected,
    heartbeat,
)
from bot.broker.deriv.error_guard import (
    record_deriv_error,
    reset_deriv_errors,
    deriv_error_limit_reached,
)

DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1089"


class DerivClient:
    def __init__(self):
        self.ws = None
        self.connected = False


    def connect(self):
        try:
            self.ws = websocket.create_connection(
                DERIV_WS_URL,
                timeout=5
            )

            api_key = get_deriv_api_key()
            if not api_key:
                raise RuntimeError("DERIV_API_KEY_MISSING")

            self.ws.send(json.dumps({"authorize": api_key}))

            response = None
            for _ in range(3):
                try:
                    raw = self.ws.recv()
                    response = json.loads(raw)
                    break
                except websocket.WebSocketTimeoutException:
                    continue

            if not response:
                raise RuntimeError("DERIV_NO_AUTH_RESPONSE")

            if response.get("error"):
                raise RuntimeError(f"DERIV_AUTH_FAILED: {response}")

            mark_connected()
            self.connected = True

        except Exception:
            mark_disconnected()
            self.connected = False
            raise

    def send(self, payload: dict) -> dict:
        if not self.connected:
            raise RuntimeError("DERIV_NOT_CONNECTED")

        try:
            self.ws.send(json.dumps(payload))
            response = json.loads(self.ws.recv())

            if response.get("error"):
                record_deriv_error()
                return response

            reset_deriv_errors()
            heartbeat()
            return response

        except Exception:
            record_deriv_error()
            mark_disconnected()
            self.connected = False
            raise

    def close(self):
        if self.ws:
            try:
                self.ws.close()
            finally:
                mark_disconnected()
                self.connected = False
