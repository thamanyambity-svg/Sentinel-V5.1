import json
import os
import datetime

# Configuration des chemins
BASE_DIR = "/Users/macbookpro/Downloads/bot_project"
TRADE_HISTORY = os.path.join(BASE_DIR, "trade_history.json")
BRAIN_CONFIG = os.path.join(BASE_DIR, "bot_brain_config.json")

def analyze_and_learn():
    print(f"[{datetime.datetime.now()}] Démarrage du cycle d'apprentissage adaptatif...")
    
    if not os.path.exists(TRADE_HISTORY):
        print("Aucun historique de trade trouvé.")
        return

    with open(TRADE_HISTORY, 'r') as f:
        history = json.load(f)

    trades = history.get("trades", [])
    if not trades:
        print("Historique vide.")
        return

    # 1. Analyse des pertes du jour
    today = datetime.datetime.now().date()
    daily_losses = []
    
    for t in trades:
        # Conversion du timestamp (format MT5 est secondes depuis 1970)
        t_date = datetime.datetime.fromtimestamp(t.get("time_open", 0)).date()
        if t_date == today and float(t.get("pnl", 0)) < 0:
            daily_losses.append(t)

    print(f"Analyse de {len(daily_losses)} pertes aujourd'hui.")

    # 2. Logique d'apprentissage : Si perte avec IA < 70%, on durcit les règles
    adjustment_made = False
    new_config = {
        "min_ia_confidence": 0.75,
        "adx_threshold": 30,
        "rsi_extreme_buy": 30,
        "rsi_extreme_sell": 70,
        "last_update": str(datetime.datetime.now())
    }

    if len(daily_losses) > 3:
        print("⚠️ Alerte : Trop de pertes détectées. Durcissement des règles en cours...")
        new_config["min_ia_confidence"] = 0.85 # On exige 85% d'accord IA
        new_config["adx_threshold"] = 35      # On exige une tendance encore plus forte
        adjustment_made = True

    # 3. Sauvegarde de la nouvelle "Intelligence" pour le bot MQL5
    with open(BRAIN_CONFIG, 'w') as f:
        json.dump(new_config, f, indent=4)
    
    if adjustment_made:
        print(f"✅ Apprentissage terminé. Nouvelles règles appliquées : IA Min {new_config['min_ia_confidence']*100}%")
    else:
        print("✅ Performance stable. Maintien des réglages actuels.")

if __name__ == "__main__":
    analyze_and_learn()
