#!/usr/bin/env python3
"""
antigravity_openai_bridge.py — Version V6.00
═══════════════════════════════════════════════════════════════════════
Pont MQL5 ↔ OpenAI pour Aladdin Pro V6.00

Architecture des agents :
  COMMUNICATOR_REPORT  — Rapport stratégique (NORMAL / HIGH / CRITICAL)
  DATA_MINING_EMBED    — Embedding vectoriel d'un setup de trading
  SESSION_REVIEW       — Analyse de fin de session (PF, WR, tendances)
  ML_INSIGHT           — Interprétation des signaux ML (SHAP / proba)
  NEWS_ALERT           — Analyse d'impact des news économiques

Flux :
  MQL5 → ai_request.json → [ce script] → OpenAI → ai_response.json

Déclencheurs événementiels (depuis logging_module.mq5) :
  NORMAL    — Rapport de routine (toutes les 5 min si activité)
  HIGH      — Trade fermé en perte immédiate
  CRITICAL  — 3+ pertes consécutives / DD limite atteint
═══════════════════════════════════════════════════════════════════════
"""

import os
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from mt5_context import get_current_mt5_context

# ── Chemin MT5 Common Files (utilisé aussi pour gold_analysis.json) ──
MT5_COMMON_PATH = os.environ.get(
    "MT5_PATH",
    os.path.expanduser(
        "~/Library/Application Support/net.metaquotes.wine.metatrader5"
        "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
    ),
)

from dotenv import load_dotenv
from openai import OpenAI

# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BRIDGE] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("antigravity_bridge.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("OpenAIBridge")

# Chargement .env (priorité au .env local, fallback bot/.env)
load_dotenv(dotenv_path=Path(__file__).parent / "bot" / ".env")
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MT5_FILES_PATH = os.getenv(
    "MT5_FILES_PATH",
    "/Users/macbookpro/Library/Application Support/"
    "net.metaquotes.wine.metatrader5/drive_c/Program Files/"
    "MetaTrader 5/MQL5/Files",
)

GPT_MODEL_FAST   = "gpt-4o-mini"    # Rapide + économique → rapports
GPT_MODEL_STRONG = "gpt-4o"         # Fort → analyse critique uniquement
EMBED_MODEL      = "text-embedding-3-small"

POLL_INTERVAL    = 2.0   # secondes entre chaque check du fichier requête
MAX_TOKENS_MAP   = {"NORMAL": 300, "HIGH": 400, "CRITICAL": 500}
TEMP_MAP         = {"NORMAL": 0.3,  "HIGH": 0.2,  "CRITICAL": 0.15}


# ══════════════════════════════════════════════════════════════════
#  CHEMINS
# ══════════════════════════════════════════════════════════════════

MT5_DIR       = Path(MT5_FILES_PATH)
REQUEST_FILE  = MT5_DIR / "ai_request.json"
RESPONSE_FILE = MT5_DIR / "ai_response.json"


# ══════════════════════════════════════════════════════════════════
#  CLIENT OPENAI
# ══════════════════════════════════════════════════════════════════

def _make_client() -> Optional[OpenAI]:
    if not OPENAI_API_KEY:
        log.error("OPENAI_API_KEY manquante — vérifier le fichier .env")
        return None
    try:
        return OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        log.error("Impossible d'initialiser OpenAI: %s", e)
        return None

client: Optional[OpenAI] = _make_client()


# ══════════════════════════════════════════════════════════════════
#  LECTURE JSON COMPATIBLE MQL5 (ANSI / Latin-1)
# ══════════════════════════════════════════════════════════════════

def safe_read_json(filepath: Path) -> Optional[Dict]:
    """
    MQL5 écrit en ANSI (Latin-1). On lit en binaire et decode en Latin-1.
    Fallback UTF-8 si Latin-1 échoue.
    """
    try:
        raw = filepath.read_bytes()
        for enc in ["latin-1", "utf-8", "cp1252"]:
            try:
                return json.loads(raw.decode(enc))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        log.error("Impossible de décoder %s", filepath)
        return None
    except Exception as e:
        log.error("Lecture impossible: %s", e)
        return None


# ══════════════════════════════════════════════════════════════════
#  CONTEXTE SYSTÈME PAR AGENT ET PRIORITÉ
# ══════════════════════════════════════════════════════════════════

SYSTEM_PROMPTS = {

    "COMMUNICATOR_REPORT": {
        "NORMAL": """Tu es l'Agent Communicateur du système Aladdin Pro V6 (bot institutionnel XM, XAUUSD/Forex/Indices).
Traduis ce log technique en rapport stratégique en français, 3-5 lignes.
FORMAT OBLIGATOIRE:
🔹 SYNTHÈSE: [état général du bot en 1 ligne]
⚠️ ALERTES: [points d'attention ou AUCUNE]
✅ RECOMMANDATION: [action concrète suggérée]""",

        "HIGH": """Tu es l'Agent Analyste du système Aladdin Pro V6 (bot XM).
Un trade vient d'être fermé en PERTE. Analyse rapidement:
1. La perte était-elle prévisible? (spread élevé? mauvais RSI/ADX?)
2. Début d'une série ou incident isolé?
3. Recommandation très concrète pour les prochains trades.
Sois direct, en 4-6 lignes, en français.""",

        "CRITICAL": """Tu es l'Agent SENTINELLE CRITIQUE du système Aladdin Pro V6.
ALERTE ROUGE: série de pertes critiques ou drawdown limite détecté.
Ta mission URGENTE:
1. Identifier la cause probable (régime de marché changé? paramètres inadaptés?)
2. Évaluer si le bot doit être stoppé immédiatement
3. Donner les actions correctives précises (ex: stopper le bot, augmenter ADX_Min, attendre session NY)
Sois DIRECT et URGENT. Maximum 6 lignes. Pas de formules de politesse.""",
    },

    "SESSION_REVIEW": {
        "NORMAL": """Tu es l'Agent Analyste Performance du système Aladdin Pro V6.
Analyse les métriques de session et produis un bilan concis en français:
📊 PERFORMANCE: [PF, WR, drawdown]
🕐 MEILLEURE HEURE: [si disponible]
🔧 AJUSTEMENT: [paramètre à modifier si nécessaire]
Maximum 5 lignes.""",

        "HIGH": """Tu es l'Agent Bilan du système Aladdin Pro V6.
La session s'est terminée avec des métriques préoccupantes.
Analyse les données et donne un diagnostic en français (5-7 lignes):
- Cause probable de la sous-performance
- Paramètre le plus problématique
- Action corrective pour la prochaine session""",

        "CRITICAL": """Tu es l'Agent SENTINELLE du système Aladdin Pro V6.
Session catastrophique détectée. Analyse d'urgence requise.
Identifie: cause racine, régime de marché actuel, actions immédiates.
RÉPONSE COURTE ET DIRECTE, 4-5 lignes maximum.""",
    },

    "ML_INSIGHT": {
        "NORMAL": """Tu es l'Agent ML Interpreter du système Aladdin Pro V6.
Un signal XGBoost vient d'être généré. Explique en français (3-4 lignes):
- Ce que signifie cette proba pour ce trade
- Les features dominantes qui ont orienté le signal
- Si le contexte de marché confirme le signal ML""",

        "HIGH": """Tu es l'Agent ML Analyste du système Aladdin Pro V6.
Signal ML avec confiance borderline. Analyse:
- Faut-il faire confiance au modèle dans ce contexte?
- Quels indicateurs techniques confirment ou infirment?
- Décision recommandée (trader / passer)""",

        "CRITICAL": """Tu es l'Agent ML CRITIQUE du système Aladdin Pro V6.
Le modèle ML et les règles classiques divergent fortement.
Analyse le conflit et donne une recommandation tranchée en 3 lignes.""",
    },

    "NEWS_ALERT": {
        "NORMAL": """Tu es l'Agent Calendrier du système Aladdin Pro V6.
Une news économique importante approche. Résume en 2-3 lignes:
- Impact attendu sur les paires concernées
- Recommandation: trader avant/après ou éviter complètement""",

        "HIGH": """Tu es l'Agent News du système Aladdin Pro V6.
News haute importance imminente (NFP/FOMC/CPI). Analyse rapide:
- Impact historique de cet indicateur sur XAUUSD/USD
- Scénario le plus probable post-publication
- Position du bot recommandée (flat / réduit / normal)""",

        "CRITICAL": """Tu es l'Agent ALERTE NEWS du système Aladdin Pro V6.
EVENT TIER-1 IMMINENT (NFP/FOMC/ECB). Alerte maximale:
1. Le bot DOIT-IL être mis en pause? OUI/NON
2. Durée recommandée de la pause
3. Instruments les plus exposés
RÉPONSE EN 3 LIGNES MAXIMUM.""",
    },

    "DATA_MINING_EMBED": {
        "NORMAL": "Génère un résumé compact de ce setup de trading pour embedding vectoriel.",
        "HIGH":   "Génère un résumé compact de ce setup de trading pour embedding vectoriel.",
        "CRITICAL": "Génère un résumé compact de ce setup de trading pour embedding vectoriel.",
    },
}


# ══════════════════════════════════════════════════════════════════
#  AGENTS
# ══════════════════════════════════════════════════════════════════

def agent_report(technical_log: str, agent_type: str, priority: str) -> str:
    """Appelle GPT avec le bon prompt système selon l'agent et la priorité."""
    if client is None:
        return "[ERREUR] Client OpenAI non initialisé — vérifier OPENAI_API_KEY"

    prompts = SYSTEM_PROMPTS.get(agent_type, SYSTEM_PROMPTS["COMMUNICATOR_REPORT"])
    system  = prompts.get(priority, prompts.get("NORMAL", ""))
    model   = GPT_MODEL_STRONG if priority == "CRITICAL" else GPT_MODEL_FAST

    # Enrichissement du contexte avec les fichiers de status V6.00
    context = _read_status_context()
    user_content = f"LOG TECHNIQUE:\n{technical_log}"
    if context:
        user_content += f"\n\nCONTEXTE MT5 (status.json):\n{context}"

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system",  "content": system},
                {"role": "user",    "content": user_content},
            ],
            max_tokens=MAX_TOKENS_MAP.get(priority, 300),
            temperature=TEMP_MAP.get(priority, 0.3),
        )
        text = resp.choices[0].message.content.strip()
        log.info("GPT réponse ok — agent=%s priority=%s tokens=%d",
                 agent_type, priority, resp.usage.total_tokens)
        return text
    except Exception as e:
        log.error("Erreur OpenAI %s: %s", agent_type, e)
        return f"[ERREUR OpenAI] {e}"


def agent_embedding(description: str) -> list:
    """Génère un embedding vectoriel pour le Data-Mining Agent."""
    if client is None:
        return []
    try:
        resp = client.embeddings.create(input=description, model=EMBED_MODEL)
        log.info("Embedding OK — dim=%d", len(resp.data[0].embedding))
        return resp.data[0].embedding
    except Exception as e:
        log.error("Erreur embedding: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════
#  LECTURE DU CONTEXTE V6.00 (status.json, session_log.json, ml_signal.json)
# ══════════════════════════════════════════════════════════════════

def _read_status_context() -> str:
    """
    Lit les fichiers de monitoring V6.00 pour enrichir le contexte GPT.
    """
    parts = []

    # status.json
    status_path = MT5_DIR / "status.json"
    if status_path.exists():
        try:
            d = safe_read_json(status_path)
            if d:
                parts.append(
                    f"Balance: ${d.get('balance', '?')}  "
                    f"Equity: ${d.get('equity', '?')}  "
                    f"Positions: {d.get('positions', 0)}  "
                    f"Trading: {'ON' if d.get('tradingEnabled') else 'OFF'}"
                )
        except Exception:
            pass

    # session_log.json (produit par logging_module.mq5)
    sess_path = MT5_DIR / "session_log.json"
    if sess_path.exists():
        try:
            d = safe_read_json(sess_path)
            if d:
                parts.append(
                    f"Session PnL: ${d.get('session_pnl', '?')}  "
                    f"Trades: {d.get('daily_trades', 0)}  "
                    f"PF: {d.get('pf', '?')}  WR: {d.get('wr', '?')}%  "
                    f"ConsecLoss: {d.get('consec_loss', 0)}  "
                    f"DD: {d.get('drawdown_pct', '?')}%"
                )
        except Exception:
            pass

    # ml_signal.json (si disponible)
    ml_path = MT5_DIR / "ml_signal.json"
    if ml_path.exists():
        try:
            d = safe_read_json(ml_path)
            if d and d.get("signals"):
                sigs = [f"{s.get('sym')}: {s.get('confidence','?')} ({s.get('proba',0):.2f})"
                        for s in d["signals"][:3]]
                parts.append("ML signals: " + " | ".join(sigs))
        except Exception:
            pass

    # news_block.json (si disponible)
    news_path = MT5_DIR / "news_block.json"
    if news_path.exists():
        try:
            d = safe_read_json(news_path)
            if d and d.get("upcoming_high"):
                next_news = d["upcoming_high"][0]
                parts.append(
                    f"Prochaine news: [{next_news.get('currency')}] "
                    f"{next_news.get('title')} dans {next_news.get('mins_until', '?')}min"
                )
        except Exception:
            pass

    return "\n".join(parts) if parts else ""


# ══════════════════════════════════════════════════════════════════
#  TRAITEMENT DE LA REQUÊTE
# ══════════════════════════════════════════════════════════════════

def process_request(data: Dict) -> Dict:
    req_id    = data.get("id", f"req_{int(time.time())}")
    req_type  = data.get("type", "COMMUNICATOR_REPORT")
    priority  = data.get("priority", "NORMAL").upper()
    payload   = data.get("payload", {})
    timestamp = datetime.now().isoformat()

    # Validation priorité
    if priority not in ("NORMAL", "HIGH", "CRITICAL"):
        priority = "NORMAL"

    log.info("► Requête [%s] type=%s id=%s", priority, req_type, req_id)

    # ── Agent Communicateur / Session Review / ML Insight / News Alert ──
    if req_type in ("COMMUNICATOR_REPORT", "SESSION_REVIEW", "ML_INSIGHT", "NEWS_ALERT"):
        log_text = (payload.get("technical_log") or
                    payload.get("log")           or
                    payload.get("context",    "") or
                    json.dumps(payload, ensure_ascii=False))
        if not log_text.strip():
            return {"id": req_id, "status": "error",
                    "result": "technical_log manquant", "ts": timestamp}
        result = agent_report(log_text, req_type, priority)
        return {"id": req_id, "status": "success",
                "result": result, "priority": priority,
                "agent": req_type, "ts": timestamp}

    # ── Agent Data-Mining (embedding) ──
    elif req_type == "DATA_MINING_EMBED":
        desc = (payload.get("setup_description") or
                payload.get("text", ""))
        if not desc:
            return {"id": req_id, "status": "error",
                    "result": "setup_description manquant", "ts": timestamp}
        emb = agent_embedding(desc)
        if emb:
            return {"id": req_id, "status": "success",
                    "result": emb, "dim": len(emb),
                    "agent": req_type, "ts": timestamp}
        return {"id": req_id, "status": "error",
                "result": "Embedding échoué", "ts": timestamp}

    else:
        log.warning("Type de requête inconnu: %s", req_type)
        return {"id": req_id, "status": "error",
                "result": f"Type inconnu: {req_type}", "ts": timestamp}


# ══════════════════════════════════════════════════════════════════
#  BOUCLE PRINCIPALE
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
#  TÂCHE A — Lecture gold_analysis.json (spec ANTIGRAVITY_INTEGRATION)
# ══════════════════════════════════════════════════════════════════

def get_gold_eod_direction() -> Optional[Dict]:
    """
    Tâche A — Lit la dernière analyse GOLD et retourne la direction recommandée.
    À appeler à 20h50 UTC (5 min avant l'exécution MT5).
    Retourne None si l'analyse est absente ou trop ancienne (> 2h).
    """
    base_dir = Path(__file__).parent
    paths = [
        base_dir / "gold_analysis.json",
        Path(MT5_COMMON_PATH) / "gold_analysis.json",
    ]
    for p in paths:
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                # Vérifier que l'analyse est récente (< 2h)
                age = time.time() - data.get("ts", 0)
                if age > 7200:
                    log.warning("[EOD_GOLD] gold_analysis.json trop ancienne (%.1fh) — ignorée", age / 3600)
                    return None
                return {
                    "direction":      data["direction"],
                    "confidence":     data["confidence"],
                    "score":          data["score"],
                    "recommendation": data["recommendation"],
                }
            except Exception as e:
                log.warning("[EOD_GOLD] Erreur lecture gold_analysis.json: %s", e)
    return None  # Pas d'analyse disponible → laisser le bot décider seul


# ══════════════════════════════════════════════════════════════════
#  TÂCHE C — Logger la décision EOD dans antigravity_bridge.log
# ══════════════════════════════════════════════════════════════════

def log_eod_decision(eod: Dict, action: str = "VALIDATED") -> None:
    """
    Tâche C — Écrit la décision EOD Gold dans antigravity_bridge.log.
    Format : [2026-04-26 20:50:00] EOD_GOLD | dir=BUY | conf=75.0% | score=+4 | action=VALIDATED
    """
    direction  = eod.get("direction", "?")
    confidence = eod.get("confidence", 0.0)
    score      = eod.get("score", 0)
    ts         = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    # Récupération du compte pour le log
    ctx = get_current_mt5_context(MT5_COMMON_PATH).refresh()
    acc_info = f" | acc={ctx['broker']} {ctx['mode']} ({ctx['account']})" if ctx else ""

    line = (
        f"[{ts}] EOD_GOLD | dir={direction} | "
        f"conf={confidence:.1f}% | score={score:+d}{acc_info} | action={action}"
    )
    log.info(line)


# ══════════════════════════════════════════════════════════════════
#  TÂCHE B — Vérification EOD intégrée à la boucle de surveillance
# ══════════════════════════════════════════════════════════════════

_eod_checked_today: Optional[str] = None  # date ISO (YYYY-MM-DD)

def _check_eod_gold_window() -> None:
    """
    Tâche B — Appelée dans watch_loop() à chaque itération.
    À 20h50 UTC (fenêtre 20:50→20:54), lit gold_analysis.json et logue la
    décision. Exécuté une seule fois par jour.
    """
    global _eod_checked_today
    now = datetime.utcnow()
    today_str = now.strftime("%Y-%m-%d")
    # Fenêtre 20h50 → 20h54 UTC (5 min avant l'exécution MT5 à 20h55)
    in_window = (now.hour == 20 and 50 <= now.minute <= 54)
    if not in_window or _eod_checked_today == today_str:
        return
    eod = get_gold_eod_direction()
    if eod:
        log_eod_decision(eod, action="VALIDATED")
        _eod_checked_today = today_str
        log.info(
            "[EOD_GOLD] Direction=%s | Confidence=%.1f%% | Score=%+d | %s",
            eod["direction"], eod["confidence"], eod["score"], eod["recommendation"]
        )
    else:
        log.warning("[EOD_GOLD] Aucune analyse Gold disponible à %s UTC — bot décide seul", now.strftime("%H:%M"))
        _eod_checked_today = today_str


def watch_loop():
    log.info("═══════════════════════════════════════════════")
    log.info("  Aladdin Pro V6 — OpenAI Bridge démarré")
    log.info("  Modèle rapide  : %s", GPT_MODEL_FAST)
    log.info("  Modèle fort    : %s (CRITICAL only)", GPT_MODEL_STRONG)
    log.info("  Surveillance   : %s", REQUEST_FILE)
    log.info("  Réponses       : %s", RESPONSE_FILE)
    log.info("═══════════════════════════════════════════════")

    if client is None:
        log.error("OpenAI client non disponible — vérifier OPENAI_API_KEY dans .env")
        return

    while True:
        try:
            # Tâche B — Vérification fenêtre EOD Gold (20h50 UTC)
            _check_eod_gold_window()

            if REQUEST_FILE.exists():
                data = safe_read_json(REQUEST_FILE)

                # Supprimer immédiatement pour éviter le double traitement
                try:
                    REQUEST_FILE.unlink(missing_ok=True)
                except Exception:
                    pass

                if data is None:
                    log.error("Requête illisible — ignorée")
                    time.sleep(1)
                    continue

                # Traitement
                response = process_request(data)

                # Écriture réponse en UTF-8
                RESPONSE_FILE.write_text(
                    json.dumps(response, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                log.info("◄ Réponse écrite — status=%s", response.get("status"))

        except KeyboardInterrupt:
            log.info("Arrêt demandé par l'utilisateur.")
            break
        except Exception as e:
            log.error("Erreur inattendue: %s", e)

        time.sleep(POLL_INTERVAL)


# ══════════════════════════════════════════════════════════════════
#  TEST RAPIDE (sans fichier MQL5)
# ══════════════════════════════════════════════════════════════════

def test_bridge():
    """Test standalone — vérifie que l'API key fonctionne."""
    print("\n" + "═" * 52)
    print("  TEST BRIDGE OPENAI — Aladdin Pro V6")
    print("═" * 52)

    if not OPENAI_API_KEY:
        print("  ✗ OPENAI_API_KEY manquante")
        return

    test_payload = {
        "id": "test_001",
        "type": "COMMUNICATOR_REPORT",
        "priority": "NORMAL",
        "payload": {
            "technical_log": (
                "Symbol: XAUUSD | Balance: $287 | "
                "Trades heute: 3 | Win: 2 | Loss: 1 | "
                "PF: 1.45 | Spread actuel: 54pts | "
                "Regime: TREND_UP | ADX: 28 | RSI: 52 | "
                "ConsecLoss: 0 | LotMult: 1.00"
            )
        }
    }

    print(f"\n  Envoi requête test ({test_payload['priority']})...")
    resp = process_request(test_payload)
    print(f"\n  Status: {resp['status']}")
    if resp["status"] == "success":
        print(f"\n  Réponse GPT:\n  {resp['result']}")
        print(f"\n  ✓ Bridge opérationnel — modèle: {GPT_MODEL_FAST}")
    else:
        print(f"  ✗ Erreur: {resp['result']}")
    print("═" * 52)


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aladdin Pro V6 — OpenAI Bridge")
    parser.add_argument("--test",  action="store_true", help="Test rapide API (sans boucle)")
    parser.add_argument("--watch", action="store_true", help="Mode surveillance (défaut)")
    args = parser.parse_args()

    if args.test:
        test_bridge()
    else:
        watch_loop()
