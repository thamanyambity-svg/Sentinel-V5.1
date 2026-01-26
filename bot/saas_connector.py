import requests
import json
import threading
import logging
import os
from datetime import datetime

logger = logging.getLogger("SAAS_CONNECTOR")

# CONFIGURATION (Should ideally move to .env)
SAAS_URL = os.getenv("SAAS_WEBHOOK_URL", "https://ton-projet-antigravity.onrender.com/api/webhooks/sentinel")
API_SECRET = os.getenv("SENTINEL_API_SECRET", "une_phrase_super_secrete_123")

class SaasConnector:
    """
    Handles communication between the local trading bot and the Next.js SaaS.
    Ensures zero-latency impact using background threading.
    """
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_SECRET}"
        }
        logger.info(f"🌐 SaaS Connector Initialized (URL: {SAAS_URL})")

    def _send_async(self, payload):
        """Background thread worker to send the HTTP POST request"""
        try:
            response = requests.post(SAAS_URL, json=payload, headers=self.headers, timeout=10)
            if response.status_code == 200:
                logger.info(f"✅ [SaaS] Trade {payload.get('ticket')} synchronized successfully.")
            else:
                logger.warning(f"⚠️ [SaaS] Synchronization failed ({response.status_code}): {response.text}")
        except Exception as e:
            # We fail silently to ensure trading is never blocked by network issues
            logger.error(f"❌ [SaaS] Connection error: {e}")

    def report_trade(self, trade_data):
        """
        Public method to report a closed trade.
        Expected keys in trade_data: ticket, symbol, type, open_price, close_price, profit, duration
        """
        try:
            # Add timestamp to payload
            trade_data["timestamp"] = datetime.utcnow().isoformat()
            
            # Launch in a background thread to prevent latency
            t = threading.Thread(target=self._send_async, args=(trade_data,))
            t.daemon = True # Thread terminates when main program exit
            t.start()
            
        except Exception as e:
            logger.error(f"Failed to launch SaaS sync thread: {e}")

# Global instance
saas_connector = SaasConnector()
