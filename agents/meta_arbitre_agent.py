import json
import os

SCORES_FILE = "agent_scores.json"

def run(current_scores: dict) -> str:
    """
    Rôle : Meta-Arbitre
    Mission : Présenter l'état de réputation des agents au CIO.
    """
    
    top_agents = sorted(current_scores.items(), key=lambda x: x[1], reverse=True)[:3]
    bottom_agents = sorted(current_scores.items(), key=lambda x: x[1])[:3]
    
    top_text = ", ".join([f"{k} ({v:.2f})" for k, v in top_agents if v > 0])
    bottom_text = ", ".join([f"{k} ({v:.2f})" for k, v in bottom_agents if v > 0])

    prompt = f"""
    Tu es le META-ARBITRE du fonds BlackRock. 
    Ton rôle est de surveiller la performance individuelle des agents du Swarm.
    
    ÉTAT DES RÉPUTATIONS (Confiance) :
    - Top Performance : {top_text}
    - Surveillance requise : {bottom_text}
    
    INSTRUCTIONS :
    1. Informe le CIO sur les agents dont la voix doit être privilégiée.
    2. Alerte sur ceux qui sont en "Drawdown de pertinence".
    
    RÉPONDRE UNIQUEMENT EN FRANÇAIS (2 lignes max).
    FORMAT : [MÉTA-ANALYSE] : (ton avis sur la fiabilité actuelle de l'essaim)
    """
    
    return prompt

def update_agent_score(agent_name, agent_said, trade_result, current_scores):
    """
    Formule V7.0 : Convergence vers le poids initial (cible)
    MIN: 0.3 | MAX: 2.5
    """
    alpha = 0.1
    MIN_SCORE = 0.3
    MAX_SCORE = 2.5
    
    # Cibles par défaut (Poids initiaux)
    targets = {
        "shadow": 2.0,
        "risk": 1.5,
        "macro": 1.0,
        "quant": 1.0,
        "regime": 1.0,
        "sentiment": 1.0
    }
    target = targets.get(agent_name, 1.0)
    
    # Déterminer si l'agent avait raison
    correct = False
    if agent_said == "BUY" and trade_result > 0: correct = True
    elif agent_said == "SELL" and trade_result > 0: correct = True
    elif agent_said == "WAIT" and trade_result < -5.0: # A évité une perte
        correct = True
    
    old_score = current_scores.get(agent_name, target)
    
    if correct:
        # On tend vers la cible idéale (100% de confiance)
        new_score = old_score * (1 - alpha) + target * alpha
    else:
        # On descend vers le floor (0% de confiance)
        new_score = old_score * (1 - alpha) + MIN_SCORE * alpha
        
    return max(MIN_SCORE, min(MAX_SCORE, new_score))
