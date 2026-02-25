import os
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

class ProductionSecurityManager:
    def __init__(self):
        # Configure Security Logger
        self.logger = logging.getLogger("PROD_SECURITY")
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s | SECURITY | %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # Load Whitelist
        self.whitelist_ips = os.getenv("WHITELIST_IPS", "").strip().split(",")
        # Clean up empty strings if var is empty
        self.whitelist_ips = [ip.strip() for ip in self.whitelist_ips if ip.strip()]

        # Encryption Key (simulated or real env var)
        self.encryption_key = os.getenv("ENCRYPTION_KEY", "default-dev-key-CHANGE-ME").encode()
    
    def validate_ip(self, client_ip: str) -> bool:
        """Valide que l'IP est dans la whitelist. Si whitelist vide, tout passe (mode dev)."""
        if not self.whitelist_ips:
            return True
        return client_ip in self.whitelist_ips
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Chiffre les données sensibles (HMAC-SHA256 pour signature/vérification)."""
        # Note: Ceci est une signature (hashing), pas un chiffrement réversible (AES).
        # Pour du chiffrement réversible, utiliser 'cryptography.fernet'.
        # Ici on suit la spec user hmac.
        return hmac.new(self.encryption_key, data.encode(), hashlib.sha256).hexdigest()
    
    def audit_log(self, action: str, user: str, details: Dict[str, Any]):
        """Log toutes les actions sensibles."""
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user": user,
            "details": details,
            "ip": details.get('client_ip', 'N/A')
        }
        self.logger.info(f"AUDIT_EVENT: {json.dumps(audit_entry)}")
    
    def validate_trade_command(self, command: Dict[str, Any]) -> bool:
        """Valide que la commande de trading est sûre et bien formée."""
        required_fields = ['symbol', 'direction', 'volume']
        
        # Check presence
        if not all(field in command for field in required_fields):
            self.logger.warning(f"Invalid command structure: {command}")
            return False
        
        # Validate Volume (Risk Check)
        try:
            vol = float(command['volume'])
            if vol <= 0 or vol > 10.0: # Hard limit 10 lots/contracts for safety
                self.logger.warning(f"Volume out of bounds: {vol}")
                return False
        except ValueError:
            return False
            
        # Validate Direction
        if command['direction'].upper() not in ['BUY', 'SELL', 'CALL', 'PUT']:
             self.logger.warning(f"Invalid direction: {command['direction']}")
             return False

        return True

if __name__ == "__main__":
    # Test
    sec = ProductionSecurityManager()
    print(f"IP 1.1.1.1 allowed? {sec.validate_ip('1.1.1.1')}")
    
    sig = sec.encrypt_sensitive_data("my-secret-password")
    print(f"Signature: {sig}")
    
    sec.audit_log("LOGIN", "admin", {"client_ip": "192.168.1.5", "status": "failed"})
    
    valid_cmd = {"symbol": "EURUSD", "direction": "BUY", "volume": 1.0}
    bad_cmd = {"symbol": "EURUSD", "direction": "FLY", "volume": 100.0}
    
    print(f"Cmd valid? {sec.validate_trade_command(valid_cmd)}")
    print(f"Cmd valid? {sec.validate_trade_command(bad_cmd)}")
