from agents.base import call_llm
import sys
import os

def run(system_metrics, active_trades, running_pids):
    """
    Rôle : Quality Assurance & Anti-Zombie Controller
    Mission : Surveiller la santé technique et l'intégrité des opérations.
    """
    
    prompt = f"""
    Tu es le GUARDIAN QA (Quality Control) du fonds BlackRock. 
    Ton rôle est de détecter les "Zombies" : processus inactifs, trades orphelins, ou fuites de ressources.
    
    DONNÉES TECHNIQUES :
    - Métriques Système : {system_metrics}
    - Trades Actifs : {active_trades}
    - Processus Détectés : {running_pids}
    
    INSTRUCTIONS :
    1. Analyse si un trade semble "orphelin" (pas de StopLoss ou pas d'activité récente).
    2. Vérifie si le nombre de processus Python est cohérent.
    3. Évalue la charge système pour éviter les lags de décision.
    
    RÉPONDRE UNIQUEMENT EN FRANÇAIS.
    FORMAT DE RÉPONSE (3 lignes max) :
    ÉTAT DU SYSTÈME : [SAIN / ALERTE / CRITIQUE]
    AUDIT ZOMBIE : (ton analyse des processus et trades)
    RECOMMANDATION QA : (action corrective pour la hiérarchie)
    """
    
    return call_llm(prompt, tier=1)

if __name__ == "__main__":
    print(get_guardian_report("CPU: 12%, RAM: 1.2GB", "3 positions", "8 PIDs"))
