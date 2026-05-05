from agents.base import call_llm

def run(account_data: dict, phase1_reports: dict) -> str:
    balance = account_data.get('balance', 'N/A')
    drawdown = account_data.get('drawdown', 0)
    positions = account_data.get('positions_count', 0)
    trading_enabled = account_data.get('trading_enabled', False)

    # Règles de risque codées en dur — INVIOLABLES
    hard_veto = None
    if float(drawdown) >= 5.0:
        hard_veto = f"Drawdown critique à {drawdown}% (seuil: 5%)"
    elif int(positions) >= 3:
        hard_veto = f"Trop de positions ouvertes: {positions} (max: 3)"
    elif not trading_enabled:
        hard_veto = "Trading automatique désactivé sur MT5"

    if hard_veto:
        return f"STATUT: VETO\nRAISON: {hard_veto}\nACTION: Aucun nouveau trade autorisé."

    prompt = f"""Tu es le Risk Manager d'un fonds institutionnel. Réponds en FRANÇAIS.

Balance: {balance}$ | Drawdown: {drawdown}% | Positions: {positions}
Les règles de risque sont respectées (drawdown < 5%, positions < 3).

Réponds UNIQUEMENT avec ce format (3 lignes max) :
STATUT: [AUTORISÉ / VETO]
NIVEAU RISQUE: [FAIBLE / MOYEN / ÉLEVÉ]
CONDITION: [1 condition ou limite à respecter pour le prochain trade]"""
    return call_llm(prompt, tier=3)
