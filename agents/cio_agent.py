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

    consensus = all_reports.get('consensus_stats', 'N/A')
    shadow = all_reports.get('shadow', 'N/A')[:200]
    meta = all_reports.get('meta_arbitre', 'N/A')[:200]

    prompt = f"""Tu es le CIO (Chief Investment Officer) de BlackRock. 
    Ton équipe a voté avec des POIDS DE RÉPUTATION (V7.0).
    
    CONSENSUS PONDÉRÉ : {consensus}
    SHADOW TRADER (Stats) : {shadow}
    MÉTA-ARBITRE : {meta}
    
    RAPPORTS DÉTAILLÉS :
    MACRO: {macro}
    TECHNIQUE: {quant}
    RISK MANAGER: {risk}
    
    CONSIGNE : Si le consensus est < au seuil, tu DOIS rester en ATTENTE.
    Prends en compte le Shadow Trader (Backtest réel).

Réponds UNIQUEMENT avec ce format (exactement 3 lignes) :
DÉCISION: [ACHAT / VENTE / ATTENTE]
JUSTIFICATION: [1 phrase max expliquant pourquoi]
CONFIANCE: [FAIBLE / MOYEN / ÉLEVÉ]"""
    return call_llm(prompt, tier=3)
