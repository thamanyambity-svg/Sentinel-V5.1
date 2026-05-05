import json
import os

def run(current_setup: dict) -> str:
    """
    Rôle : Shadow Trader
    Mission : Comparer le setup actuel aux 300+ trades passés.
    """
    
    history_path = "trade_history.json"
    if not os.path.exists(history_path):
        return "ERREUR : Historique introuvable."
        
    try:
        with open(history_path, "r") as f:
            history = json.load(f).get("trades", [])
    except:
        return "ERREUR : Lecture historique impossible."

    # Métriques actuelles
    cur_rsi = float(current_setup.get('rsi', 50))
    cur_adx = float(current_setup.get('adx', 20))
    cur_regime = int(current_setup.get('regime', 0))
    cur_type = current_setup.get('direction', 'buy').lower() # La direction envisagée par les autres agents

    # Recherche de trades "similaires"
    # Critères : Même régime et RSI à +/- 10, ADX à +/- 10
    similar_trades = [
        t for t in history
        if t.get('regime') == cur_regime
        and abs(float(t.get('rsi', 50)) - cur_rsi) <= 10
        and abs(float(t.get('adx', 20)) - cur_adx) <= 10
        and t.get('type') == cur_type
    ]

    nb_total = len(similar_trades)
    if nb_total == 0:
        return "NEUTRE : Aucun historique similaire trouvé pour ce setup."

    wins = sum(1 for t in similar_trades if float(t.get('pnl', 0)) > 0)
    wr = wins / nb_total if nb_total > 0 else 0
    
    status = "VALIDE"
    if nb_total >= 10 and wr < 0.40:
        status = "VETO"
    elif nb_total < 10:
        status = "WARNING"

    prompt = f"""
    Tu es le SHADOW TRADER du fonds BlackRock. 
    Ton rôle est de valider le trade en te basant sur les statistiques réelles de l'historique.
    
    RÉSULTATS DE LA SIMULATION :
    - Direction envisagée : {cur_type.upper()}
    - Trades similaires trouvés : {nb_total}
    - Winrate historique (WR) : {wr:.2%}
    - Statut : {status}
    
    INSTRUCTIONS :
    - Si VETO : Tu DOIS bloquer le trade car les stats historiques sont contre nous.
    - Si WARNING : Recommande la prudence car l'échantillon est trop faible (< 10 trades).
    - Si VALIDE : Donne ton feu vert pondéré par le WR.
    
    RÉPONDRE UNIQUEMENT EN FRANÇAIS (2 lignes max).
    FORMAT : [STATUT] : (ton analyse statistique courte avec WR)
    """
    
    return prompt
