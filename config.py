"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V10 — config.py                                            ║
║  Configuration centralisée — chargée par TOUS les modules           ║
║                                                                      ║
║  Priorité de chargement :                                            ║
║    1. Variables d'environnement (OS / .env)                          ║
║    2. Fichier sentinel_config.json (si présent)                      ║
║    3. Valeurs par défaut ci-dessous                                  ║
║                                                                      ║
║  Usage dans n'importe quel module :                                  ║
║    from config import cfg                                            ║
║    port = cfg.SENTINEL_PORT                                          ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("Config")

# ══════════════════════════════════════════════════════════════════
#  CLASSE DE CONFIGURATION
# ══════════════════════════════════════════════════════════════════

class SentinelConfig:

    def __init__(self):
        # Répertoire racine du projet (là où se trouve config.py)
        self.BASE_DIR = Path(__file__).parent

        # ── Réseau ───────────────────────────────────────────────
        self.SENTINEL_HOST      = "127.0.0.1"   # JAMAIS 0.0.0.0 sans firewall
        self.SENTINEL_PORT      = 5555
        self.SENTINEL_API_KEY   = "CHANGE_ME_BEFORE_PRODUCTION"

        # ── MetaTrader 5 ─────────────────────────────────────────
        self.MT5_FILES_PATH = Path(
            "/Users/macbookpro/Library/Application Support/"
            "net.metaquotes.wine.metatrader5/drive_c/Program Files/"
            "MetaTrader 5/MQL5/Files"
        )

        # ── Fichiers d'interface MQL5 ↔ Python ───────────────────
        self.AI_REQUEST_FILE    = "ai_request.json"
        self.AI_RESPONSE_FILE   = "ai_response.json"
        self.AI_ERROR_FILE      = "ai_error.json"
        self.NEWS_BLOCK_FILE    = "news_block.json"
        self.ML_SIGNAL_FILE     = "ml_signal.json"
        self.STATUS_FILE        = "status.json"
        self.TICKS_FILE         = "ticks_v3.json"
        self.HEARTBEAT_FILE     = "heartbeat.txt"
        self.METRICS_FILE       = "metrics.json"

        # ── Bridge ───────────────────────────────────────────────
        self.BRIDGE_POLL_INTERVAL_SEC   = 1.0    # Fréquence de poll ai_request.json
        self.BRIDGE_REQUEST_TIMEOUT_SEC = 30     # Timeout attente réponse Sentinel
        self.BRIDGE_MAX_RETRIES         = 3      # Tentatives si Sentinel KO

        # ── News Filter ──────────────────────────────────────────
        self.NEWS_BLOCK_BEFORE_MIN  = 30
        self.NEWS_BLOCK_AFTER_MIN   = 60
        self.NEWS_TIER1_MULTIPLIER  = 2
        self.NEWS_REFRESH_SEC       = 3600

        # ── ML Predictor ─────────────────────────────────────────
        self.ML_MIN_CONFIDENCE      = 0.58
        self.ML_HIGH_CONFIDENCE     = 0.72
        self.ML_POLL_INTERVAL_SEC   = 0.5
        self.ML_MODEL_TTL_DAYS      = 7

        # ── AutoTrainer ──────────────────────────────────────────
        self.RETRAIN_INTERVAL_DAYS  = 7
        self.MIN_TRADES_TO_TRAIN    = 50
        self.TRAINING_WINDOW_DAYS   = 90

        # ── Optimizer ────────────────────────────────────────────
        self.OPT_IS_PCT             = 0.70
        self.OPT_OOS_PF_CAP         = 20.0
        self.OPT_MIN_OOS_TRADES     = 10
        self.OPT_WARN_OOS_TRADES    = 30

        # ── Logging ──────────────────────────────────────────────
        self.LOG_LEVEL              = "INFO"
        self.LOG_FILE               = self.BASE_DIR / "system.log"
        self.LOG_MAX_BYTES          = 10 * 1024 * 1024   # 10 MB
        self.LOG_BACKUP_COUNT       = 5

        # ── Risk (pour référence Python — pas pour l'EA MQL5) ────
        self.RISK_PER_TRADE_PCT     = 0.5    # 0.5% — balance < $200, spread XAUUSD ~$1.50-2.00
        self.MAX_DAILY_LOSS_PCT     = 3.0
        self.MAX_WEEKLY_LOSS_PCT    = 6.0
        self.DAILY_PROFIT_TARGET    = 2.0

        # Chargement des surcharges
        self._load_from_env()
        self._load_from_json()
        self._validate()

    # ── Chargement depuis les variables d'environnement ───────────
    def _load_from_env(self):
        env_map = {
            "SENTINEL_HOST":            ("SENTINEL_HOST",      str),
            "SENTINEL_PORT":            ("SENTINEL_PORT",      int),
            "SENTINEL_API_KEY":         ("SENTINEL_API_KEY",   str),
            "MT5_FILES_PATH":           ("MT5_FILES_PATH",     lambda x: Path(x)),
            "BRIDGE_POLL_INTERVAL":     ("BRIDGE_POLL_INTERVAL_SEC", float),
            "BRIDGE_TIMEOUT":           ("BRIDGE_REQUEST_TIMEOUT_SEC", int),
            "LOG_LEVEL":                ("LOG_LEVEL",          str),
        }
        for env_key, (attr, cast) in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                try:
                    setattr(self, attr, cast(val))
                    log.debug("Config depuis env: %s = %s", attr, val)
                except (ValueError, TypeError) as e:
                    log.warning("Config env invalide %s=%s: %s", env_key, val, e)

    # ── Chargement depuis sentinel_config.json ────────────────────
    def _load_from_json(self):
        cfg_path = self.BASE_DIR / "sentinel_config.json"
        if not cfg_path.exists():
            return
        try:
            with open(cfg_path, encoding="utf-8") as f:
                data = json.load(f)
            for key, val in data.items():
                if hasattr(self, key):
                    attr_type = type(getattr(self, key))
                    if attr_type == Path:
                        setattr(self, key, Path(val))
                    else:
                        setattr(self, key, attr_type(val))
                    log.debug("Config depuis JSON: %s = %s", key, val)
                else:
                    log.warning("Clé inconnue dans sentinel_config.json: %s", key)
        except Exception as e:
            log.error("Erreur lecture sentinel_config.json: %s", e)

    # ── Validation des valeurs critiques ──────────────────────────
    def _validate(self):
        errors = []

        if self.SENTINEL_API_KEY == "CHANGE_ME_BEFORE_PRODUCTION":
            log.warning("⚠️  SENTINEL_API_KEY non configurée — utiliser la valeur par défaut "
                        "est DANGEREUX en production")

        if str(self.SENTINEL_HOST) == "0.0.0.0":
            log.warning("⚠️  SENTINEL_HOST=0.0.0.0 expose le serveur sur toutes les interfaces")

        if not (0 < self.SENTINEL_PORT < 65536):
            errors.append(f"SENTINEL_PORT invalide: {self.SENTINEL_PORT}")

        if not (0.0 < self.OPT_IS_PCT < 1.0):
            errors.append(f"OPT_IS_PCT doit être entre 0 et 1: {self.OPT_IS_PCT}")

        if errors:
            raise ValueError("Configuration invalide:\n" + "\n".join(f"  - {e}" for e in errors))

    def mt5_path(self, filename: str) -> Path:
        """Retourne le chemin complet d'un fichier dans MT5/Files."""
        return Path(self.MT5_FILES_PATH) / filename

    def summary(self) -> str:
        """Résumé lisible de la configuration active."""
        return (
            f"Sentinel Config:\n"
            f"  Host:Port      = {self.SENTINEL_HOST}:{self.SENTINEL_PORT}\n"
            f"  API Key        = {'*** (configurée)' if self.SENTINEL_API_KEY != 'CHANGE_ME_BEFORE_PRODUCTION' else '⚠️  NON CONFIGURÉE'}\n"
            f"  MT5 Path       = {self.MT5_FILES_PATH}\n"
            f"  Bridge poll    = {self.BRIDGE_POLL_INTERVAL_SEC}s\n"
            f"  Bridge timeout = {self.BRIDGE_REQUEST_TIMEOUT_SEC}s\n"
            f"  Log level      = {self.LOG_LEVEL}\n"
            f"  Log file       = {self.LOG_FILE}\n"
        )


# ══════════════════════════════════════════════════════════════════
#  LOGGER UNIFIÉ
# ══════════════════════════════════════════════════════════════════

def setup_logging(cfg: SentinelConfig):
    """
    Configure le logging centralisé pour tous les composants.
    Un seul fichier system.log avec rotation automatique.
    Format : timestamp [LEVEL] composant — message
    """
    import logging.handlers

    level = getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)-16s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    root = logging.getLogger()
    root.setLevel(level)

    # ── Handler console ───────────────────────────────────────────
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(level)
        root.addHandler(console)

    # ── Handler fichier avec rotation ────────────────────────────
    try:
        cfg.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            cfg.LOG_FILE,
            maxBytes    = cfg.LOG_MAX_BYTES,
            backupCount = cfg.LOG_BACKUP_COUNT,
            encoding    = "utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)
    except Exception as e:
        logging.warning("Impossible d'ouvrir le fichier log %s: %s", cfg.LOG_FILE, e)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ══════════════════════════════════════════════════════════════════
#  GÉNÉRATEUR DE FICHIER DE CONFIG JSON
# ══════════════════════════════════════════════════════════════════

def generate_config_file(output_path: Path = None):
    """
    Génère un fichier sentinel_config.json avec les valeurs par défaut.
    À remplir avant le premier démarrage en production.
    """
    if output_path is None:
        output_path = Path(__file__).parent / "sentinel_config.json"
    template = {
        "SENTINEL_HOST":                "127.0.0.1",
        "SENTINEL_PORT":                5555,
        "SENTINEL_API_KEY":             "REMPLACER_PAR_UNE_CLE_SECRETE",
        "MT5_FILES_PATH":               str(Path(
            "/Users/macbookpro/Library/Application Support/"
            "net.metaquotes.wine.metatrader5/drive_c/Program Files/"
            "MetaTrader 5/MQL5/Files"
        )),
        "BRIDGE_POLL_INTERVAL_SEC":     1.0,
        "BRIDGE_REQUEST_TIMEOUT_SEC":   30,
        "BRIDGE_MAX_RETRIES":           3,
        "NEWS_BLOCK_BEFORE_MIN":        30,
        "NEWS_BLOCK_AFTER_MIN":         60,
        "ML_MIN_CONFIDENCE":            0.58,
        "RETRAIN_INTERVAL_DAYS":        7,
        "OPT_IS_PCT":                   0.70,
        "OPT_OOS_PF_CAP":               20.0,
        "OPT_MIN_OOS_TRADES":           10,
        "LOG_LEVEL":                    "INFO",
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2)
    print(f"✅ Config générée → {output_path}")
    print("   Éditez SENTINEL_API_KEY et MT5_FILES_PATH avant de démarrer")


# ══════════════════════════════════════════════════════════════════
#  SINGLETON
# ══════════════════════════════════════════════════════════════════

cfg = SentinelConfig()


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE (génération du fichier de config)
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sentinel Config")
    parser.add_argument("--generate", action="store_true",
                        help="Générer sentinel_config.json avec les valeurs par défaut")
    parser.add_argument("--show", action="store_true",
                        help="Afficher la configuration active")
    args = parser.parse_args()

    if args.generate:
        generate_config_file()
    elif args.show:
        print(cfg.summary())
    else:
        print(cfg.summary())
