import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from statistics import mean, stdev

MEMORY_FILE = Path("/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/trade_history.json")
MIN_TRADES_FOR_SIGNAL = 15      # Minimum pour avoir un signal fiable
DECAY_HALF_LIFE_DAYS  = 90      # Les trades vieux de 90j valent 0.5x
CONFIDENCE_FLOOR      = 0.05    # Plancher : jamais 0% (exploration)
CONFIDENCE_CEIL       = 0.92    # Plafond : jamais 100% (humilité)


# ─────────────────────────────────────────────
# CHARGEMENT ET PONDÉRATION DE LA MÉMOIRE
# ─────────────────────────────────────────────

def load_memory() -> list[dict]:
    if not MEMORY_FILE.exists():
        return []
    with open(MEMORY_FILE, "r") as f:
        data = json.load(f)
        # Handle cases where data is wrapped in a dict with a "trades" key or is a direct list
        return data.get("trades", []) if isinstance(data, dict) else data

def decay_weight(trade: dict, reference_date: datetime = None) -> float:
    """
    Memory decay : un trade récent pèse 1.0, 
    un trade vieux de DECAY_HALF_LIFE_DAYS pèse 0.5
    """
    if reference_date is None:
        reference_date = datetime.now()
    
    # On utilise l'heure d'entrée si disponible, sinon poids neutre
    try:
        # Some versions use time_open (timestamp), others duration to infer. Fallback to today if not present
        trade_date = datetime.now()  # Simplification pour ce mockup (TODO: parser l'heure d'ouverture MQL5 si on la rajoute dans le JSON brut, ou juste se baser sur la date d'export/fichier)
        age_days = (reference_date - trade_date).days
        weight = math.exp(-math.log(2) * max(0, age_days) / DECAY_HALF_LIFE_DAYS)
        return max(0.1, weight)   # Jamais sous 0.1 — on n'oublie pas totalement
    except Exception:
        return 0.5


# ─────────────────────────────────────────────
# SIMILARITÉ ENTRE CONDITIONS
# ─────────────────────────────────────────────

def similarity_score(trade: dict, conditions: dict) -> float:
    """
    Score 0-1 de similarité entre un trade mémorisé
    et les conditions actuelles du marché.
    """
    score = 0.0
    weights_total = 0.0

    def check(field, tolerance, weight):
        nonlocal score, weights_total
        if field in trade and field in conditions:
            diff = abs(trade[field] - conditions[field])
            if diff <= tolerance:
                score += weight * (1 - diff / tolerance)
            weights_total += weight

    # RSI : tolérance ±8 points
    check("rsi",        8.0,  2.0)
    # ADX : tolérance ±10 points  
    check("adx",       10.0,  1.5)
    # ATR relatif : tolérance ±20%
    if "atr" in trade and "atr" in conditions and conditions["atr"] > 0:
        atr_ratio = abs(trade["atr"] - conditions["atr"]) / conditions["atr"]
        if atr_ratio < 0.2:
            score += 1.5 * (1 - atr_ratio / 0.2)
        weights_total += 1.5
    # Session exacte
    if trade.get("session") == conditions.get("session"):
        score += 2.0
    weights_total += 2.0
    # Régime exact
    if trade.get("regime") == conditions.get("regime"):
        score += 2.0
    weights_total += 2.0
    # BB Position exacte (0/1/2)
    if trade.get("bb_position") == conditions.get("bb_position"):
        score += 2.5
    weights_total += 2.5
    # Jour de semaine
    if trade.get("day_of_week") == conditions.get("day_of_week"):
        score += 0.5
    weights_total += 0.5

    return score / weights_total if weights_total > 0 else 0.0


# ─────────────────────────────────────────────
# ANALYSE PRINCIPALE
# ─────────────────────────────────────────────

def analyze_conditions(
    conditions: dict,
    direction: str,           # "buy" ou "sell"
    symbol: str,
    min_similarity: float = 0.55
) -> dict:
    """
    Analyse la mémoire et retourne une recommandation
    avec score de confiance et explication.
    """
    memory = load_memory()
    
    # Filtrer par symbole et direction
    relevant = [
        t for t in memory 
        if t.get("symbol") == symbol 
        and t.get("type") == direction
    ]
    
    if len(relevant) < 5:
        return {
            "enter": True,
            "confidence": 0.50,
            "reason": f"Mémoire insuffisante ({len(relevant)} trades) — décision neutre",
            "sample_size": len(relevant),
            "warning": "COLD_START"
        }
    
    # Trouver les trades similaires avec leur poids temporel
    similar = []
    for trade in relevant:
        sim = similarity_score(trade, conditions)
        if sim >= min_similarity:
            weight = decay_weight(trade)
            similar.append({
                "trade": trade,
                "similarity": sim,
                "weight": weight,
                "is_win": trade.get("pnl", 0) > 0
            })
    
    if len(similar) < MIN_TRADES_FOR_SIGNAL:
        return {
            "enter": True,
            "confidence": 0.50,
            "reason": f"Pas assez de trades similaires ({len(similar)}/{MIN_TRADES_FOR_SIGNAL}) — décision neutre",
            "sample_size": len(similar),
            "warning": "INSUFFICIENT_SIMILAR"
        }
    
    # ── Calcul du win rate pondéré ──
    weighted_wins   = sum(s["weight"] for s in similar if s["is_win"])
    weighted_total  = sum(s["weight"] for s in similar)
    win_rate        = weighted_wins / weighted_total if weighted_total > 0 else 0.5

    # ── Espérance mathématique pondérée ──
    pnls = [s["trade"].get("pnl", 0) * s["weight"] for s in similar]
    avg_pnl = sum(pnls) / weighted_total if weighted_total > 0 else 0.0

    # ── Analyse MFE/MAE : le trade respirait-il bien ? ──
    mfe_values = [s["trade"].get("mfe", 0) for s in similar if s["trade"].get("mfe") is not None]
    mae_values = [s["trade"].get("mae", 0) for s in similar if s["trade"].get("mae") is not None]
    
    mfe_analysis = ""
    if mfe_values and mae_values:
        avg_mfe = mean(mfe_values)
        avg_mae = mean(mae_values)
        mfe_mae_ratio = avg_mfe / avg_mae if avg_mae > 0 else 1.0
        mfe_analysis = f"MFE moy: ${avg_mfe:.2f} | MAE moy: ${avg_mae:.2f} | Ratio: {mfe_mae_ratio:.2f}"
    
    # ── Score de confiance final ──
    # 60% win rate + 40% espérance normalisée
    pnl_score = min(1.0, max(0.0, (avg_pnl + 10) / 20))  # normalise entre -$10 et +$10
    raw_confidence = (win_rate * 0.6) + (pnl_score * 0.4)
    
    # Appliquer plancher et plafond
    confidence = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEIL, raw_confidence))
    
    # Décision d'entrée
    should_enter = confidence >= 0.55
    
    return {
        "enter": should_enter,
        "confidence": round(confidence, 3),
        "win_rate": round(win_rate, 3),
        "avg_pnl": round(avg_pnl, 2),
        "sample_size": len(similar),
        "mfe_mae": mfe_analysis,
        "reason": build_reason(conditions, win_rate, avg_pnl, len(similar), should_enter),
        "warning": check_warnings(conditions, similar)
    }


# ─────────────────────────────────────────────
# ANALYSE DES PERTES (apprentissage actif)
# ─────────────────────────────────────────────

LOSS_LOG_FILE = Path("/Users/macbookpro/Downloads/bot_project/loss_analysis.json")

def analyze_loss(trade: dict) -> dict:
    """
    Classifie la cause probable d'une perte
    pour enrichir la mémoire qualitative.
    """
    pnl  = trade.get("pnl", 0)
    mfe  = trade.get("mfe", 0)
    mae  = trade.get("mae", 0)
    dur  = trade.get("duration", 0)      # en secondes

    cause = "UNKNOWN"
    detail = ""

    if mfe < 0.50 and mae > 3.0:
        cause  = "IMMEDIATE_REVERSAL"
        detail = "Le prix est allé contre nous dès l'entrée — signal probablement faux"

    elif mfe > abs(pnl) * 2 and pnl < 0:
        cause  = "GAVE_BACK_PROFIT"
        detail = f"Le trade était gagnant (MFE ${mfe:.2f}) mais a rendu les gains — TP trop loin ou trailing trop lâche"

    elif trade.get("spread", 0) > 20 and abs(pnl) < 5:
        cause  = "SPREAD_EROSION"
        detail = "Spread élevé à l'entrée — coût de transaction trop important pour ce mouvement"

    elif trade.get("session") == "OFF":
        cause  = "OFF_SESSION"
        detail = "Trade pris hors session — liquidité faible, mouvement peu fiable"

    elif trade.get("bb_position") in [0, 2]:
        cause  = "BB_EXTREME_ENTRY"
        detail = "Entrée en extension de Bollinger — prix déjà en zone de retournement"

    elif dur < 120:
        cause  = "STOP_TOO_TIGHT"
        detail = f"Trade fermé en {dur}s — stop probablement trop serré pour l'ATR"

    # Logger l'analyse
    entry = {
        "ticket":    trade.get("ticket"),
        "symbol":    trade.get("symbol"),
        "direction": trade.get("type"),
        "pnl":       pnl,
        "cause":     cause,
        "detail":    detail,
        "timestamp": datetime.now().isoformat()
    }
    
    existing = []
    if LOSS_LOG_FILE.exists():
        with open(LOSS_LOG_FILE) as f:
            try:
                existing = json.load(f)
            except:
                pass
    existing.append(entry)
    with open(LOSS_LOG_FILE, "w") as f:
        json.dump(existing, f, indent=2)
    
    return entry


# ─────────────────────────────────────────────
# RAPPORT HEBDOMADAIRE
# ─────────────────────────────────────────────

def weekly_report() -> str:
    memory = load_memory()
    if not memory:
        return "Aucune donnée disponible."
    
    # Approximation of recent trades if timestamps are missing, assuming appending logic
    recent = memory[-50:] if len(memory) > 50 else memory
    
    if not recent:
        return "Aucun trade récent."
    
    wins   = [t for t in recent if t.get("pnl", 0) > 0]
    losses = [t for t in recent if t.get("pnl", 0) <= 0]
    
    report = f"""
╔══════════════════════════════════════╗
║     RAPPORT ADAPTATIF — SEMAINE      ║
╚══════════════════════════════════════╝
Trades     : {len(recent)} ({len(wins)}W / {len(losses)}L)
Win Rate   : {len(wins)/len(recent)*100:.1f}% if len(recent) > 0 else 0.0%
PnL Total  : ${sum(t.get('pnl', 0) for t in recent):.2f}
PnL Moyen  : ${mean(t.get('pnl', 0) for t in recent):.2f} if len(recent) > 0 else 0.0
"""
    # MFE/MAE si disponible
    mfe_data = [t.get("mfe") for t in recent if t.get("mfe") is not None]
    mae_data = [t.get("mae") for t in recent if t.get("mae") is not None]
    if mfe_data:
        report += f"MFE Moyen  : ${mean(mfe_data):.2f}\n"
        report += f"MAE Moyen  : ${mean(mae_data):.2f}\n"
    
    return report


# ─────────────────────────────────────────────
# HELPERS INTERNES
# ─────────────────────────────────────────────

def build_reason(conditions, win_rate, avg_pnl, n, decision) -> str:
    action = "ENTRÉE VALIDÉE" if decision else "ENTRÉE BLOQUÉE"
    session = conditions.get("session", "?")
    bb_map  = {0: "sous bande basse", 1: "dans les bandes", 2: "au-dessus bande haute"}
    bb_pos  = bb_map.get(conditions.get("bb_position", 1), "?")
    return (f"[{action}] {n} trades similaires en session {session}, "
            f"prix {bb_pos}. WR={win_rate*100:.0f}%, PnL moy=${avg_pnl:.2f}")

def check_warnings(conditions, similar) -> Optional[str]:
    if conditions.get("bb_position") in [0, 2]:
        return "BB_EXTREME — entrée en zone de retournement"
    if conditions.get("session") == "OFF":
        return "OFF_SESSION — liquidité réduite"
    if conditions.get("spread", 0) > 25:
        return f"HIGH_SPREAD — {conditions.get('spread', 0)} points"
    return None


# ─────────────────────────────────────────────
# POINT D'ENTRÉE CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if "--report" in sys.argv:
        print(weekly_report())
    
    elif "--analyze-losses" in sys.argv:
        memory = load_memory()
        losses = [t for t in memory if t.get("pnl", 0) < 0]
        print(f"Analyse de {len(losses)} pertes...")
        for trade in losses[-20:]:   # 20 dernières pertes
            result = analyze_loss(trade)
            print(f"  #{result['ticket']} → {result['cause']}: {result['detail']}")
    
    else:
        # Test avec conditions fictives
        test_conditions = {
            "symbol": "XAUUSD",
            "rsi": 28.0,
            "adx": 52.0,
            "atr": 5.1,
            "session": "OFF",
            "regime": 0,
            "bb_position": 0,
            "spread": 16,
            "day_of_week": 3
        }
        result = analyze_conditions(test_conditions, "buy", "XAUUSD")
        print(json.dumps(result, indent=2, ensure_ascii=False))
