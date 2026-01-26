class BaseBroker:
    name = "BASE"

    def execute(self, trade: dict, shadow: bool = False) -> dict:
        """
        Execute a trade.

        shadow=True :
          - aucune exécution réelle
          - aucun effet externe
          - utilisé pour dry-run / audit / simulation
        """
        raise NotImplementedError
