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
from datetime import datetime, timedelta
from collections import defaultdict

BASE     = Path(__file__).parent
MT5_PATH = os.environ.get("MT5_PATH", os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"))

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

    # N2 — ML
    "n2_retrain_hours":    12,    # Ré-entraînement toutes les N heures
    "n2_min_trades":       30,    # Trades minimum pour entraîner
    "n2_test_split":       0.2,   # 20% pour validation

    # N3 — Mémoire épisodique
    "n3_max_episodes":     200,   # Taille de la mémoire
    "n3_similarity_thr":   0.75,  # Seuil de similarité (0-1)
    "n3_influence_range":  0.20,  # Influence max sur la confiance (±20%)
    "n3_decay_days":       30,    # Les souvenirs s'estompent après N jours
}

# ═══════════════════════════════════════════════════════════════
#  UTILITAIRES
# ═══════════════════════════════════════════════════════════════
def find(f):
    for p in [BASE / f, Path(MT5_PATH) / f]:
        if p.exists(): return p
    return None

def rj(f):
    p = find(f)
    if not p: return None
    try: return json.loads(p.read_text(encoding='utf-8'))
    except: return None

def wj(f, data):
    for dest in [BASE / f, Path(MT5_PATH) / f]:
        try: dest.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except: pass

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

    try:
        import numpy as np
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder
        from sklearn.metrics import accuracy_score

        # ── Features
        FEATURES = ["rsi", "adx", "atr", "spread", "hour",
                    "ema_distance", "confluence", "bb_position", "mfe", "mae"]
        SESSION_MAP = {"ASIA": 0, "LONDON": 1, "NEW_YORK": 2, "OFF": 3}
        SYM_MAP     = {"XAUUSD": 0, "GOLD": 0, "EURUSD": 1, "USDJPY": 2,
                       "US500": 3, "US30": 3, "NGAS": 4}

        X, y = [], []
        for t in trades:
            pnl = float(t.get("pnl", 0))
            row = [
                float(t.get("rsi",         50)),
                float(t.get("adx",         20)),
                float(t.get("atr",          0)),
                float(t.get("spread",      30)),
                float(t.get("hour",        12)),
                float(t.get("ema_distance", 0)),
                float(t.get("confluence",   1)),
                float(t.get("bb_position",  1)),
                float(t.get("mfe",          0)),
                float(t.get("mae",          0)),
                SESSION_MAP.get(t.get("session", "OFF"), 3),
                SYM_MAP.get(t.get("symbol", "?"), 5),
                1 if t.get("type") == "buy" else 0,
                float(t.get("day_of_week",  2)),
            ]
            X.append(row)
            y.append(1 if pnl > 0 else 0)

        X = np.array(X)
        y = np.array(y)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=CFG["n2_test_split"], random_state=42, stratify=y
        )

        # Essayer XGBoost d'abord, sinon RandomForest
        try:
            import xgboost as xgb
            model = xgb.XGBClassifier(
                n_estimators=100, max_depth=4, learning_rate=0.1,
                use_label_encoder=False, eval_metric='logloss',
                random_state=42, verbosity=0
            )
        except ImportError:
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)

        model.fit(X_train, y_train)
        acc = accuracy_score(y_test, model.predict(X_test))

        # Sauvegarder le modèle
        import joblib
        model_path = BASE / "model_adaptive.pkl"
        joblib.dump(model, model_path)

        state["n2_accuracy"]    = round(float(acc), 3)
        state["n2_trained_on"]  = len(trades)
        state["last_retrain"]   = int(time.time())

        return state, f"Modèle entraîné — acc={acc*100:.1f}% sur {len(X_test)} trades test"

    except ImportError as e:
        return state, f"ML libs non disponibles ({e}) — N1/N3 actifs"
    except Exception as e:
        return state, f"Erreur entraînement: {e}"

# ═══════════════════════════════════════════════════════════════
#  NIVEAU 3 — MÉMOIRE ÉPISODIQUE
#  "La dernière fois que j'ai fait ça, j'ai perdu/gagné"
# ═══════════════════════════════════════════════════════════════
def compute_context_fingerprint(trade):
    """
    Crée une empreinte du contexte d'un trade pour la comparaison.
    Bucketise les valeurs continues pour trouver des similitudes.
    """
    rsi    = float(trade.get("rsi",    50))
    adx    = float(trade.get("adx",    20))
    hour   = int(trade.get("hour",     12))
    sym    = trade.get("symbol",   "?")
    sess   = trade.get("session",  "OFF")
    typ    = trade.get("type",     "buy")
    spread = float(trade.get("spread", 30))

    return {
        "rsi_bucket":  "high" if rsi > 60 else ("low" if rsi < 40 else "mid"),
        "adx_bucket":  "strong" if adx > 30 else ("weak" if adx < 20 else "mod"),
        "hour_bucket": f"{(hour // 3) * 3}h",
        "symbol":      sym,
        "session":     sess,
        "direction":   typ,
        "spread_ok":   spread < 80,
    }

def context_similarity(fp1, fp2):
    """Score de similarité entre deux empreintes contextuelles (0 à 1)."""
    keys    = ["rsi_bucket", "adx_bucket", "hour_bucket", "symbol", "session", "direction", "spread_ok"]
    weights = [0.20,         0.15,          0.15,          0.20,     0.15,      0.10,        0.05]
    score   = sum(w for k, w in zip(keys, weights) if fp1.get(k) == fp2.get(k))
    return round(score, 3)

def update_episodic_memory(trades, episodes):
    """
    Met à jour la mémoire épisodique avec les trades récents.
    Prioritise les pertes importantes et les erreurs répétées.
    """
    if not trades: return episodes

    # Convertir les épisodes existants en dict pour lookup rapide
    ep_ids = {ep["id"] for ep in episodes}

    for trade in trades[-50:]:  # Derniers 50 trades
        trade_id = str(trade.get("ticket", "")) + str(trade.get("time_open", ""))
        ep_id    = hashlib.md5(trade_id.encode()).hexdigest()[:8]

        if ep_id in ep_ids: continue  # Déjà en mémoire

        pnl = float(trade.get("pnl", 0))
        fp  = compute_context_fingerprint(trade)

        # Calculer l'intensité du souvenir
        # Les grosses pertes ET les gros gains sont mémorisés plus fortement
        intensity = min(abs(pnl) / 20.0, 1.0)  # Normalise sur $20

        episode = {
            "id":         ep_id,
            "ts":         int(trade.get("time_open", time.time())),
            "symbol":     trade.get("symbol", "?"),
            "type":       trade.get("type", "?"),
            "pnl":        pnl,
            "outcome":    "win" if pnl > 0 else "loss",
            "intensity":  round(intensity, 3),
            "fingerprint": fp,
            "lesson":     _extract_lesson(trade, pnl, fp),
        }
        episodes.append(episode)
        ep_ids.add(ep_id)

    # Trier par intensité + récence, garder les N max
    now = time.time()
    for ep in episodes:
        age_days  = (now - ep["ts"]) / 86400
        ep["relevance"] = ep["intensity"] * math.exp(-age_days / CFG["n3_decay_days"])

    episodes.sort(key=lambda e: e["relevance"], reverse=True)
    return episodes[:CFG["n3_max_episodes"]]

def _extract_lesson(trade, pnl, fp):
    """Formule une leçon lisible depuis un trade."""
    outcome = "gagné" if pnl > 0 else "perdu"
    sym     = trade.get("symbol", "?")
    sess    = trade.get("session", "?")
    rsi     = float(trade.get("rsi", 50))
    adx     = float(trade.get("adx", 20))

    parts = [f"{outcome} ${abs(pnl):.2f} sur {sym} en {sess}"]

    if pnl < 0:
        # Identifier la probable cause de la perte
        if fp["rsi_bucket"] == "high" and trade.get("type") == "buy":
            parts.append("RSI survente au moment du BUY")
        if fp["adx_bucket"] == "weak":
            parts.append("ADX faible = tendance molle")
        if fp["hour_bucket"] in ["0h", "18h", "21h"]:
            parts.append("heure habituellement non rentable")
        if not fp["spread_ok"]:
            parts.append("spread élevé")
    else:
        # Renforcer les bonnes conditions
        if fp["adx_bucket"] == "strong":
            parts.append("forte tendance confirmée")
        if sess in ["LONDON", "NEW_YORK"]:
            parts.append("bonne session")

    return " | ".join(parts)

def query_memory(context_fp, episodes, direction):
    """
    Interroge la mémoire : dans un contexte similaire, le bot a-t-il gagné ou perdu ?
    Retourne un facteur d'ajustement de confiance (-0.20 à +0.20)
    """
    if not episodes: return 0.0, []

    relevant = []
    for ep in episodes:
        sim = context_similarity(context_fp, ep["fingerprint"])
        if sim >= CFG["n3_similarity_thr"]:
            relevant.append((sim, ep))

    if not relevant: return 0.0, []

    # Pondération par similarité × intensité × récence
    win_score  = 0.0
    loss_score = 0.0
    memories   = []

    for sim, ep in relevant:
        if ep.get("direction", ep.get("fingerprint", {}).get("direction", "")) != direction: continue
        weight = sim * ep.get("relevance", ep["intensity"])
        if ep["outcome"] == "win":
            win_score  += weight
        else:
            loss_score += weight
        memories.append({
            "lesson":  ep["lesson"],
            "outcome": ep["outcome"],
            "pnl":     ep["pnl"],
            "sim":     round(sim, 2),
        })

    total = win_score + loss_score
    if total < 0.01: return 0.0, memories

    # Ratio net wins : +1.0 = tous gagnants, -1.0 = tous perdants
    ratio     = (win_score - loss_score) / total
    influence = ratio * CFG["n3_influence_range"]

    return round(influence, 3), memories[:5]

# ═══════════════════════════════════════════════════════════════
#  INSIGHTS AUTOMATIQUES
#  Génère des observations lisibles pour le dashboard
# ═══════════════════════════════════════════════════════════════
def generate_insights(trades, weights):
    """Génère 3-5 insights actionnables depuis les données."""
    insights = []
    if not trades: return insights

    recent_20 = trades[-20:]

    # 1. Meilleure et pire heure
    by_hour = defaultdict(list)
    for t in trades[-100:]:
        by_hour[int(t.get("hour", 12))].append(float(t.get("pnl", 0)))

    if by_hour:
        best_h  = max(by_hour, key=lambda h: sum(by_hour[h]) / len(by_hour[h]))
        worst_h = min(by_hour, key=lambda h: sum(by_hour[h]) / len(by_hour[h]))
        best_wr  = sum(1 for p in by_hour[best_h]  if p > 0) / len(by_hour[best_h])  * 100
        worst_wr = sum(1 for p in by_hour[worst_h] if p > 0) / len(by_hour[worst_h]) * 100
        insights.append({
            "type":    "timing",
            "icon":    "clock",
            "title":   f"Meilleure heure : {best_h:02d}h UTC",
            "detail":  f"WR {best_wr:.0f}% sur {len(by_hour[best_h])} trades — Pire : {worst_h:02d}h ({worst_wr:.0f}%)",
            "action":  f"Favoriser les trades à {best_h:02d}h, éviter {worst_h:02d}h",
        })

    # 2. Symbole le plus rentable
    by_sym = defaultdict(list)
    for t in trades[-100:]:
        by_sym[t.get("symbol", "?")].append(float(t.get("pnl", 0)))

    if by_sym:
        best_sym = max(by_sym, key=lambda s: sum(by_sym[s]))
        sym_pnl  = sum(by_sym[best_sym])
        sym_wr   = sum(1 for p in by_sym[best_sym] if p > 0) / len(by_sym[best_sym]) * 100
        insights.append({
            "type":   "symbol",
            "icon":   "star",
            "title":  f"Champion : {best_sym}",
            "detail": f"PnL ${sym_pnl:.2f} | WR {sym_wr:.0f}% sur {len(by_sym[best_sym])} trades",
            "action": f"Augmenter légèrement la confiance sur {best_sym}",
        })

    # 3. Pattern perdant récurrent
    loss_contexts = []
    for t in recent_20:
        if float(t.get("pnl", 0)) < 0:
            fp = compute_context_fingerprint(t)
            loss_contexts.append(fp)

    if len(loss_contexts) >= 3:
        # Trouver le contexte le plus fréquent dans les pertes
        hour_losses = defaultdict(int)
        for fp in loss_contexts:
            hour_losses[fp["hour_bucket"]] += 1
        worst_hour = max(hour_losses, key=hour_losses.get)
        if hour_losses[worst_hour] >= 2:
            insights.append({
                "type":   "warning",
                "icon":   "alert",
                "title":  f"Schéma de perte détecté à {worst_hour}",
                "detail": f"{hour_losses[worst_hour]} pertes sur les 20 derniers trades à cette heure",
                "action": f"Envisager de bloquer {worst_hour} dans IsGlobalTradingAllowed()",
            })

    # 4. Momentum de performance
    if len(recent_20) >= 10:
        first_half  = recent_20[:10]
        second_half = recent_20[10:]
        wr1 = sum(1 for t in first_half  if float(t.get("pnl",0)) > 0) / 10 * 100
        wr2 = sum(1 for t in second_half if float(t.get("pnl",0)) > 0) / 10 * 100
        trend = "amélioration" if wr2 > wr1 else "dégradation"
        emoji = "↑" if wr2 > wr1 else "↓"
        insights.append({
            "type":   "trend",
            "icon":   "trend",
            "title":  f"{emoji} Tendance {trend} de performance",
            "detail": f"WR : {wr1:.0f}% → {wr2:.0f}% sur les 20 derniers trades",
            "action": "Continue" if wr2 > wr1 else "Réduire les lots ou faire une pause",
        })

    # 5. Qualité ADX
    trades_low_adx  = [t for t in recent_20 if float(t.get("adx", 20)) < 20]
    losses_low_adx  = [t for t in trades_low_adx if float(t.get("pnl", 0)) < 0]
    if len(trades_low_adx) >= 3 and len(losses_low_adx) / len(trades_low_adx) > 0.6:
        insights.append({
            "type":   "filter",
            "icon":   "filter",
            "title":  "ADX faible = pertes fréquentes",
            "detail": f"{len(losses_low_adx)}/{len(trades_low_adx)} trades avec ADX<20 sont perdants",
            "action": "Augmenter ADX_MinStrength de 20 à 25 dans le bot MQL5",
        })

    return insights[:5]

# ═══════════════════════════════════════════════════════════════
#  MOTEUR PRINCIPAL
# ═══════════════════════════════════════════════════════════════
def run_learning_cycle():
    print(f"\n{'═'*55}")
    print(f"  Aladdin Learning Engine — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'═'*55}")

    trades = load_trades()
    state  = load_state()
    logs   = []

    if not trades:
        print("  ⚠ Aucun trade en mémoire — attente de données MT5")
        return

    print(f"  Trades chargés : {len(trades)}")

    # ── N1 : Poids adaptatifs ──────────────────────────────────
    print("\n  [N1] Calcul des poids adaptatifs...")
    weights = compute_n1_weights(trades)
    state["n1_weights"] = weights
    logs.append(f"N1: {len(weights)} contextes pondérés")

    # Afficher les alertes N1
    for key, w in sorted(weights.items(), key=lambda x: x[1]["weight"]):
        if w["weight"] < 0.60:
            print(f"    ⚠ POIDS FAIBLE  [{key}] WR={w['wr']}% → x{w['weight']}")
        elif w["weight"] > 1.30:
            print(f"    ✓ POIDS ÉLEVÉ   [{key}] WR={w['wr']}% → x{w['weight']}")

    # ── N2 : Re-entraînement ML ───────────────────────────────
    hours_since = (time.time() - state.get("last_retrain", 0)) / 3600
    if hours_since >= CFG["n2_retrain_hours"] or state.get("n2_accuracy") is None:
        print(f"\n  [N2] Re-entraînement ML ({len(trades)} trades)...")
        state, msg = retrain_ml(trades, state)
        print(f"    → {msg}")
        logs.append(f"N2: {msg}")
    else:
        next_h = CFG["n2_retrain_hours"] - hours_since
        print(f"\n  [N2] Prochain re-entraînement dans {next_h:.1f}h")
        if state.get("n2_accuracy"):
            print(f"    Accuracy actuelle : {state['n2_accuracy']*100:.1f}%")

    # ── N3 : Mémoire épisodique ───────────────────────────────
    print(f"\n  [N3] Mise à jour mémoire épisodique...")
    episodes = state.get("n3_episodes", [])
    episodes = update_episodic_memory(trades, episodes)
    state["n3_episodes"] = episodes
    losses_mem = sum(1 for e in episodes if e["outcome"] == "loss")
    wins_mem   = sum(1 for e in episodes if e["outcome"] == "win")
    print(f"    {len(episodes)} épisodes en mémoire ({wins_mem} gains, {losses_mem} pertes)")
    logs.append(f"N3: {len(episodes)} épisodes")

    # Top 3 leçons importantes
    important = sorted(episodes, key=lambda e: e.get("relevance", 0), reverse=True)[:3]
    for ep in important:
        icon = "✓" if ep["outcome"] == "win" else "✗"
        print(f"    {icon} {ep['lesson']}")

    # ── Insights ─────────────────────────────────────────────
    print(f"\n  [INSIGHTS] Génération des insights...")
    insights = generate_insights(trades, weights)
    state["insights"] = insights
    for ins in insights:
        print(f"    → {ins['title']} : {ins['action']}")

    # ── Stats globales ────────────────────────────────────────
    pnls   = [float(t.get("pnl", 0)) for t in trades]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    state["stats"] = {
        "total_trades":   len(trades),
        "win_rate":       round(len(wins) / len(pnls) * 100, 1) if pnls else 0,
        "total_pnl":      round(sum(pnls), 2),
        "profit_factor":  round(abs(sum(wins)) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else 0,
        "avg_win":        round(sum(wins)   / len(wins)   if wins   else 0, 2),
        "avg_loss":       round(sum(losses) / len(losses) if losses else 0, 2),
        "best_trade":     round(max(pnls), 2) if pnls else 0,
        "worst_trade":    round(min(pnls), 2) if pnls else 0,
    }

    # ── Sauvegarde état ───────────────────────────────────────
    state["last_update"] = int(time.time())
    state["logs"]        = logs
    wj("learning_state.json", state)

    print(f"\n{'═'*55}")
    print(f"  ✓ Cycle terminé — learning_state.json écrit")
    print(f"  WR global : {state['stats']['win_rate']}% | PnL : ${state['stats']['total_pnl']}")
    print(f"{'═'*55}\n")

    return state


def get_trade_confidence_adjustment(symbol, session, direction, hour, rsi, adx):
    """
    API rapide : retourne l'ajustement de confiance recommandé pour un trade potentiel.
    Combine N1 (poids) + N3 (mémoire) → facteur entre 0.5 et 1.5

    Utilisé par le scheduler avant d'envoyer un signal via action_plan.json
    """
    state = load_state()
    if not state: return 1.0, [], []

    # N1 — Poids adaptatifs
    hour_bucket = f"{(hour // 3) * 3}h"
    n1_weight = 1.0
    applied_weights = []
    for key in [f"sym:{symbol}", f"session:{session}", f"hour:{hour_bucket}",
                f"sym:{symbol}|session:{session}", f"sym:{symbol}|hour:{hour_bucket}"]:
        w = state["n1_weights"].get(key, {})
        if w:
            n1_weight *= w["weight"]
            applied_weights.append(f"{key}→x{w['weight']} (WR{w['wr']}%)")

    n1_weight = max(0.3, min(1.5, n1_weight ** 0.3))  # Racine pour atténuer la multiplication

    # N3 — Mémoire épisodique
    fp = {
        "rsi_bucket":  "high" if rsi > 60 else ("low" if rsi < 40 else "mid"),
        "adx_bucket":  "strong" if adx > 30 else ("weak" if adx < 20 else "mod"),
        "hour_bucket": hour_bucket,
        "symbol":      symbol,
        "session":     session,
        "direction":   direction,
        "spread_ok":   True,
    }
    n3_adjust, memories = query_memory(fp, state.get("n3_episodes", []), direction)

    final = max(0.3, min(1.5, n1_weight + n3_adjust))
    return round(final, 3), applied_weights, memories


if __name__ == "__main__":
    run_learning_cycle()
