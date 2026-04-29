import json, os, time
from pathlib import Path

class MT5Context:
    """
    Gère le contexte du compte MT5 (Deriv Demo/Real, XM, etc.)
    Permet au bot de s'adapter automatiquement au changement de compte.
    """
    def __init__(self, status_file):
        self.status_file = Path(status_file)
        self.last_account = None
        self.last_server = None
        self.current_context = {}
        self.refresh()

    def refresh(self):
        if not self.status_file.exists():
            return None
        
        try:
            with open(self.status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            acc = str(data.get("account", ""))
            srv = data.get("server", "")
            
            # Détection du changement de compte
            if acc != self.last_account or srv != self.last_server:
                self.on_account_switch(acc, srv)
            
            self.last_account = acc
            self.last_server = srv
            
            # Calcul du type de compte
            is_demo = "demo" in srv.lower()
            broker = "DERIV" if "deriv" in srv.lower() else "XM" if "xm" in srv.lower() else "UNKNOWN"
            
            self.current_context = {
                "account": acc,
                "server": srv,
                "broker": broker,
                "mode": "DEMO" if is_demo else "REAL",
                "is_real": not is_demo,
                "timestamp": time.time()
            }
            return self.current_context
        except Exception as e:
            print(f"Error reading status for context: {e}")
            return None

    def on_account_switch(self, new_acc, new_srv):
        msg = f"🔄 ACCOUNT SWITCH DETECTED: {new_acc} on {new_srv}"
        print(f"\n{'='*40}\n{msg}\n{'='*40}\n")
        
        # Log de l'événement pour l'audit Antigravity
        log_path = Path(__file__).parent / "logs" / "antigravity_bridge.log"
        log_path.parent.mkdir(exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a") as f:
            f.write(f"[{ts}] CONTEXT | account_changed | to={new_acc} | srv={new_srv}\n")

    def get_risk_multiplier(self):
        """Exemple de logique automatisée : risque réduit en réel"""
        if self.current_context.get("mode") == "REAL":
            return 0.5 # 50% du risque habituel pour la sécurité
        return 1.0

# Singleton pour usage global
def get_current_mt5_context(mt5_path):
    status_p = Path(mt5_path) / "status.json"
    return MT5Context(status_p)
