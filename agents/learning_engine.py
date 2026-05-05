import json
import os
import sys
import time

# Fix for imports when running as a standalone script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents import meta_arbitre_agent

MEMORY_FILE = "swarm_memory.json"
HISTORY_FILE = "trade_history.json"
SCORES_FILE = "agent_scores.json"

def run_learning():
    """
    Scanne les votes archivés et les compare aux résultats réels.
    Met à jour les scores de réputation.
    """
    if not os.path.exists(MEMORY_FILE) or not os.path.exists(HISTORY_FILE):
        print("⚠️ Fichiers de mémoire ou d'historique manquants.")
        return

    # Charger les scores actuels
    try:
        with open(SCORES_FILE, "r") as f:
            scores = json.load(f)
    except:
        scores = {}

    # Charger la mémoire (JSONL)
    pending_votes = []
    with open(MEMORY_FILE, "r") as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("status") == "OPEN":
                pending_votes.append(entry)

    if not pending_votes:
        print("✅ Aucun vote en attente d'apprentissage.")
        return

    # Charger l'historique
    with open(HISTORY_FILE, "r") as f:
        history = json.load(f).get("trades", [])

    updated_any = False
    new_memory_lines = []

    # Pour chaque vote en attente
    for vote_entry in pending_votes:
        # Trouver le trade correspondant dans l'historique (par timestamp approximatif)
        # On cherche un trade qui s'est ouvert APRÈS le vote (dans les 5 mins)
        match = None
        vote_ts = float(vote_entry['timestamp'])
        
        for trade in history:
            trade_ts = float(trade.get('time_open', 0))
            diff = trade_ts - vote_ts
            if 0 <= diff <= 300: # 5 mins window
                match = trade
                break
        
        if match:
            pnl = float(match.get('pnl', 0))
            print(f"🎯 Match trouvé ! Diff: {diff:.1f}s | PnL: {pnl}")
            
            # Mettre à jour chaque agent
            for agent_name, vote in vote_entry['votes'].items():
                new_score = meta_arbitre_agent.update_agent_score(
                    agent_name, vote, pnl, scores
                )
                scores[agent_name] = new_score
            
            vote_entry["status"] = "PROCESSED"
            vote_entry["result_pnl"] = pnl
            updated_any = True
        else:
            print(f"❌ Pas de match pour vote {vote_ts}. Dernier trade_ts vu: {trade_ts}")
        
        new_memory_lines.append(json.dumps(vote_entry))

    if updated_any:
        # Sauvegarder les nouveaux scores
        with open(SCORES_FILE, "w") as f:
            json.dump(scores, f, indent=4)
        
        # Réécrire la mémoire avec les statuts mis à jour
        with open(MEMORY_FILE, "w") as f:
            for line in new_memory_lines:
                f.write(line + "\n")
        
        print("🚀 RÉPUTATIONS MISES À JOUR AVEC SUCCÈS.")
    else:
        print("⏳ En attente de clôture des trades correspondants...")

def run_learning_daemon():
    """
    Boucle infinie toutes les 5 minutes (300s)
    """
    print("🚀 LEARNING ENGINE V7.0 — Démarrage de la boucle (5 min)...")
    while True:
        run_learning()
        time.sleep(300)

if __name__ == "__main__":
    run_learning_daemon()
