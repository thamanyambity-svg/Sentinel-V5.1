<<<<<<< ours
import json, os, time, math, hashlib, datetime
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# Chemins
BASE = Path(__file__).parent
MT5_FILES_PATH = os.environ.get("MT5_PATH", os.path.expanduser("~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"))
TRADE_HISTORY = os.path.join(MT5_FILES_PATH, "trade_history.json")
LEARNING_STATE = os.path.join(BASE, "learning_state.json")
BRAIN_CONFIG = os.path.join(BASE, "bot_brain_config.json")
LOG_FILE = os.path.join(BASE, "logs/learning.log")
=======
"""
adaptive_learning_engine.py — Moteur d'apprentissage adaptatif Aladdin Pro V7.22

3 niveaux d'apprentissage :
  N1 — Règles adaptatives  : poids des signaux ajustés par WR récent
  N2 — ML supervisé        : XGBoost re-entraîné chaque nuit
  N3 — Mémoire épisodique  : "la dernière fois que j'ai fait ça..."

Écrit : learning_state.json  → lu par dashboard + bot via ml_signal.json
"""

import json, os, time, math, hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

BASE     = Path(__file__).parent
MT5_PATH = os.environ.get("MT5_PATH", os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"))
LEARNING_LOG = BASE / "logs" / "learning.log"

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════
CFG = {
    # N1 — Règles adaptatives
    "n1_window_trades":    20,    # Fenêtre glissante (derniers N trades)
    "n1_wr_threshold":     0.45,  # En dessous → signal pénalisé
    "n1_weight_decay":     0.85,  # Facteur de décroissance temporelle
    "n1_min_weight":       0.30,  # Poids minimum (jamais à 0)
    "n1_max_weight":       1.50,  # Poids maximum
    "n1_penalty":          0.10,  # Réduction par perte consécutive
>>>>>>> theirs

# Configuration Elite V7.25
LEARNING_SCHEDULE_MODE = os.environ.get("LEARNING_SCHEDULE_MODE", "daemon")

def rj(f):
<<<<<<< ours
    p = os.path.join(MT5_FILES_PATH, f)
    if not os.path.exists(p): p = os.path.join(BASE, f)
    if not os.path.exists(p): return None
=======
    p = find(f)
    if not p: return None
    try: return json.loads(p.read_text(encoding='utf-8'))
    except: return None

def wj(f, data):
    for dest in [BASE / f, Path(MT5_PATH) / f]:
        try: dest.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except: pass

def append_learning_log(message):
    try:
        LEARNING_LOG.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with open(LEARNING_LOG, "a", encoding="utf-8") as h:
            h.write(f"[{ts}] {message}\n")
    except:
        pass

def load_trades():
    d = rj("trade_history.json")
    return d.get("trades", []) if d else []

def load_state():
    d = rj("learning_state.json")
    if d: return d
    return {
        "version":   "v1.0",
        "last_update": 0,
        "last_retrain": 0,
        "n1_weights": {},
        "n2_accuracy": None,
        "n2_trained_on": 0,
        "n3_episodes": [],
        "stats": {},
        "insights": [],
    }

# ═══════════════════════════════════════════════════════════════
#  NIVEAU 1 — RÈGLES ADAPTATIVES
#  Ajuste les poids des signaux selon le WR récent par contexte
# ═══════════════════════════════════════════════════════════════
def compute_n1_weights(trades):
    """
    Pour chaque combinaison (symbole, session, signal), calcule le WR
    sur la fenêtre glissante et ajuste le poids du signal.

    Retourne : dict de poids par contexte
    """
    if not trades: return {}

    recent = trades[-CFG["n1_window_trades"]:]
    weights = {}

    # Groupes d'analyse
    groups = defaultdict(list)
    for t in recent:
        sym     = t.get("symbol", "?")
        session = t.get("session", "OFF")
        hour    = int(t.get("hour", 12))
        pnl     = float(t.get("pnl", 0))

        # Bucket horaire (par tranche de 3h)
        hour_bucket = f"{(hour // 3) * 3}h"

        # Clés de groupement
        for key in [
            f"sym:{sym}",
            f"session:{session}",
            f"hour:{hour_bucket}",
            f"sym:{sym}|session:{session}",
            f"sym:{sym}|hour:{hour_bucket}",
        ]:
            groups[key].append(pnl)

    for key, pnls in groups.items():
        if len(pnls) < 3: continue  # Pas assez de données

        wins  = sum(1 for p in pnls if p > 0)
        total = len(pnls)
        wr    = wins / total
        avg   = sum(pnls) / total

        # Calcul du poids adaptatif
        # WR 50% → poids neutre 1.0
        # WR 70% → poids 1.4
        # WR 30% → poids 0.6
        raw_weight = 0.5 + wr * 1.0
        weight     = max(CFG["n1_min_weight"], min(CFG["n1_max_weight"], raw_weight))

        # Bonus si série de gains récente
        last_5 = pnls[-5:]
        consec_wins = 0
        for p in reversed(last_5):
            if p > 0: consec_wins += 1
            else: break
        if consec_wins >= 3: weight = min(weight * 1.15, CFG["n1_max_weight"])

        # Malus si série de pertes récente
        consec_losses = 0
        for p in reversed(last_5):
            if p <= 0: consec_losses += 1
            else: break
        if consec_losses >= 2:
            weight -= CFG["n1_penalty"] * consec_losses
            weight  = max(weight, CFG["n1_min_weight"])

        weights[key] = {
            "weight":   round(weight, 3),
            "wr":       round(wr * 100, 1),
            "avg_pnl":  round(avg, 2),
            "n":        total,
            "consec_wins":   consec_wins,
            "consec_losses": consec_losses,
        }

    return weights

# ═══════════════════════════════════════════════════════════════
#  NIVEAU 2 — ML SUPERVISÉ
#  Re-entraîne XGBoost avec les nouveaux trades
# ═══════════════════════════════════════════════════════════════
def retrain_ml(trades, state):
    """
    Tente de re-entraîner le modèle XGBoost si assez de trades.
    Fallback gracieux si sklearn/xgboost non installé.
    """
    if len(trades) < CFG["n2_min_trades"]:
        return state, f"Pas assez de trades ({len(trades)}/{CFG['n2_min_trades']})"

>>>>>>> theirs
    try:
        with open(p, 'r', encoding='utf-8') as h: return json.load(h)
    except: return None

def append_learning_log(message):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")
    print(f"[{ts}] {message}")

def run_learning_cycle():
    append_learning_log("Lancement du cycle d'apprentissage V7.25...")
    history = rj("trade_history.json")
    if not history or "trades" not in history:
        append_learning_log("Erreur: Historique introuvable.")
        return {"status": "error"}

    trades = history["trades"]
    if not trades:
        append_learning_log("Aucun trade à analyser.")
        return {"status": "no_data"}

    # Analyse simplifiée pour la V7.25
    pnls = [float(t.get("pnl", 0)) for t in trades[-100:]]
    wr = (len([p for p in pnls if p > 0]) / len(pnls)) * 100 if pnls else 0
    
    # Stratégie adaptative
    new_confidence = 0.75
    if wr < 50:
        new_confidence = 0.85
        append_learning_log(f"WR faible ({wr:.1f}%). Durcissement Sniper à 85%.")
    else:
        append_learning_log(f"WR stable ({wr:.1f}%). Maintien Sniper à 75%.")

    # Sauvegarde de la config pour le bot MQL5
    brain_cfg = {
        "min_ia_confidence": new_confidence,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "win_rate": round(wr, 2)
    }
    
    with open(BRAIN_CONFIG, 'w') as f:
        json.dump(brain_cfg, f, indent=4)
        
    return {"status": "success", "stats": {"win_rate": round(wr, 2), "total_pnl": round(sum(pnls), 2)}}

if __name__ == "__main__":
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
    if LEARNING_SCHEDULE_MODE == "daemon":
        append_learning_log("Midnight Engine démarré (Mode Daemon 00:01)")
        while True:
            now = datetime.now()
            # On cherche 00:01
            if now.hour == 0 and now.minute == 1:
                try:
                    res = run_learning_cycle()
                    append_learning_log(f"Cycle terminé: {res.get('status')}")
                except Exception as e:
                    append_learning_log(f"Erreur cycle: {str(e)}")
                time.sleep(65) # Dormir pour sortir de la minute 00:01
            time.sleep(30)
    else:
        run_learning_cycle()
=======
=======
>>>>>>> theirs
=======
>>>>>>> theirs
    mode = os.environ.get("LEARNING_SCHEDULE_MODE", "once").strip().lower()
    if mode == "daemon":
        print("🕛 Midnight Engine démarré (mode daemon, exécution quotidienne à 00:01 UTC)")
        append_learning_log("Midnight Engine started in daemon mode")
        while True:
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=0, minute=1, second=0, microsecond=0)
            if now >= next_run:
                next_run = next_run + timedelta(days=1)
            # Sleep par tranches pour rester réactif (supervision/process manager)
            while True:
                now = datetime.now(timezone.utc)
                remaining = int((next_run - now).total_seconds())
                if remaining <= 0:
                    break
                time.sleep(min(60, remaining))
            append_learning_log("Starting scheduled 00:01 learning cycle")
            try:
                state = run_learning_cycle()
                wr = state.get("stats", {}).get("win_rate", 0)
                pnl = state.get("stats", {}).get("total_pnl", 0)
                append_learning_log(f"Scheduled cycle completed: WR={wr}% PnL={pnl}")
            except Exception as e:
                append_learning_log(f"Scheduled cycle failed: {e}")
    else:
        state = run_learning_cycle()
        wr = state.get("stats", {}).get("win_rate", 0)
        pnl = state.get("stats", {}).get("total_pnl", 0)
        append_learning_log(f"Manual cycle completed: WR={wr}% PnL={pnl}")
<<<<<<< ours
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
