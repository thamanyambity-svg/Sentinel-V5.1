from agents.base import call_llm

def run(all_reports: dict) -> str:
    risk = all_reports.get('risk', '')

    # Si le Risk Manager a émis un VETO, le CIO doit le respecter immédiatement
    if 'VETO' in risk.upper():
        return f"DÉCISION: ATTENTE\nJUSTIFICATION: Veto du Risk Manager — {risk}\nCONFIANCE: N/A (Veto actif)"

    macro = all_reports.get('macro', 'N/A')[:250]
    quant = all_reports.get('quant', 'N/A')[:250]
    loss = all_reports.get('loss', 'N/A')[:200]
    accountant = all_reports.get('accountant', 'N/A')[:200]
    devil = all_reports.get('devil', 'N/A')[:200]
    errors = all_reports.get('errors', 'N/A')[:200]

    prompt = f"""Tu es le CIO (Chief Investment Officer) d'un fonds institutionnel. Réponds en FRANÇAIS.

Voici les rapports de ton équipe :
MACRO: {macro}
TECHNIQUE: {quant}
PERTES: {loss}
COMPTABLE: {accountant}
AVOCAT DU DIABLE: {devil}
ERREURS: {errors}
RISK MANAGER: {risk}

Réponds UNIQUEMENT avec ce format (exactement 3 lignes) :
DÉCISION: [ACHAT / VENTE / ATTENTE]
JUSTIFICATION: [1 phrase max expliquant pourquoi]
CONFIANCE: [FAIBLE / MOYEN / ÉLEVÉ]"""
    return call_llm(prompt)
