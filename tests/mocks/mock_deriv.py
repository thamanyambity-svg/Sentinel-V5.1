class MockDerivBroker:
    def execute(self, trade, shadow=False):
        if shadow:
            return {"status": "SHADOW"}
        return {
            "status": "EXECUTED",
            "pnl": 1.23,
        }
