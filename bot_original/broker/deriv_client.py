from bot.journal.audit import audit


class DerivClient:
    """
    Client Deriv SANDBOX.
    Simule une API Deriv sans aucun appel réseau.
    """

    def __init__(self):
        self.connected = False

    def connect(self):
        self.connected = True
        audit("DERIV_CLIENT_CONNECTED")
        return True

    def ping(self):
        if not self.connected:
            raise RuntimeError("Deriv client not connected")
        return {"status": "OK"}

    def get_balance(self):
        if not self.connected:
            raise RuntimeError("Deriv client not connected")
        return {
            "currency": "USD",
            "balance": 10000.0
        }

    def execute(self, asset, side, amount=None):
        if not self.connected:
            raise RuntimeError("Deriv client not connected")

        result = {
            "status": "EXECUTED",
            "asset": asset,
            "side": side,
            "amount": amount,
            "pnl": 0.0,
            "broker": "DERIV_SANDBOX"
        }

        audit("DERIV_SANDBOX_EXECUTION", context=result)
        return result
