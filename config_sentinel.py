"""
SENTINEL V11 - Configuration Centralisée
========================================

Ce fichier centralise toutes les configurations de la plateforme.
À modifier selon votre environnement.
"""

import json
from pathlib import Path

# Chemins principales
BASE_DIR = Path(__file__).parent
MT5_DIR = Path("/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
DATA_DIR = BASE_DIR / "data"

# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION DASHBOARD
# ══════════════════════════════════════════════════════════════════

DASHBOARD_CONFIG = {
    # Affichage
    "display": {
        "width": 72,
        "height": 30,
        "theme": "dark",  # 'dark', 'light', 'amber'
        "colors_enabled": True,
    },
    
    # Rafraîchissement
    "refresh": {
        "interval": 5,  # secondes
        "cache_ttl": 5,  # secondes
        "auto_clear_cache": True,
    },
    
    # Affichage des sections
    "sections": {
        "header": True,
        "account": True,
        "positions": True,
        "ticks": True,
        "news": True,
        "ml": True,
        "backtest": True,
        "performance": True,
        "blackbox": True,
        "logs": True,
        "footer": True,
    },
    
    # Limites d'affichage
    "limits": {
        "max_positions": 5,
        "max_logs": 6,
        "max_trades": 4,
        "news_hours": 12,
    }
}


# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION API
# ══════════════════════════════════════════════════════════════════

API_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": True,
        "threaded": True,
    },
    
    "cors": {
        "enabled": True,
        "origins": ["*"],  # À restreindre en production
    },
    
    "cache": {
        "default_ttl": 5,
        "ttls": {
            "account": 3,
            "positions": 2,
            "ticks": 2,
            "ml": 5,
            "backtest": 10,
            "health": 1,
        }
    },
    
    "rate_limit": {
        "enabled": False,  # À activer en production
        "requests_per_minute": 60,
    }
}


# ══════════════════════════════════════════════════════════════════
#  CHEMINS DES FICHIERS DE DONNÉES
# ══════════════════════════════════════════════════════════════════

DATA_FILES = {
    # MT5 Bridge outputs (dans MT5_DIR)
    "status": MT5_DIR / "status.json",
    "ticks": MT5_DIR / "ticks_v3.json",
    "positions": MT5_DIR / "positions.json",
    "news_block": MT5_DIR / "news_block.json",
    "performance": MT5_DIR / "aladdin_performance.csv",
    "bb_entry": MT5_DIR / "aladdin_bb_entry.csv",
    "bb_evolution": MT5_DIR / "aladdin_bb_evolution.csv",
    "bb_exit": MT5_DIR / "aladdin_bb_exit.csv",
    
    # Bot outputs (dans BASE_DIR)
    "backtest": BASE_DIR / "backtest_summary.json",
    "training": BASE_DIR / "training_history.json",
    "action_plan": BASE_DIR / "action_plan.json",
    "fundamental": BASE_DIR / "fundamental_state.json",
    "bot_log": BASE_DIR / "bot.log",
    "bot_state": BASE_DIR / "bot_state.json",
    "model_registry": BASE_DIR / "model_registry.json",
}


# ══════════════════════════════════════════════════════════════════
#  THRESHOLDS & ALERTES
# ══════════════════════════════════════════════════════════════════

TRADING_THRESHOLDS = {
    "backtest": {
        "min_profit_factor": 1.25,
        "max_drawdown_pct": 20.0,
        "min_sharpe": 0.8,
        "min_win_rate": 0.5,
    },
    
    "account": {
        "min_balance_alert": 1000,  # Alerte si balance < X
        "max_drawdown_pct": 30,     # Alerte si drawdown > X%
    },
    
    "ml": {
        "min_confidence": 0.55,
        "min_kelly_risk": 0.1,
        "max_kelly_risk": 5.0,
    }
}


# ══════════════════════════════════════════════════════════════════
#  INTÉGRATIONS
# ══════════════════════════════════════════════════════════════════

INTEGRATIONS = {
    "discord": {
        "enabled": False,
        "webhook_url": "YOUR_WEBHOOK_HERE",
        "frequency": 60,  # minutes
    },
    
    "telegram": {
        "enabled": False,
        "bot_token": "YOUR_TOKEN_HERE",
        "chat_id": "YOUR_CHAT_ID_HERE",
    },
    
    "email": {
        "enabled": False,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "from_email": "your_email@gmail.com",
        "recipients": [],
    }
}


# ══════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════

LOGGING_CONFIG = {
    "level": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "format": "[%(asctime)s] %(levelname)-8s | %(name)s: %(message)s",
    "file": BASE_DIR / "logs" / "sentinel.log",
    "max_bytes": 10 * 1024 * 1024,  # 10 MB
    "backup_count": 5,
}


# ══════════════════════════════════════════════════════════════════
#  SECURITY
# ══════════════════════════════════════════════════════════════════

SECURITY_CONFIG = {
    "validate_json": True,
    "validate_csv": True,
    "max_file_size": 50 * 1024 * 1024,  # 50 MB
    "allowed_origins": ["localhost", "127.0.0.1"],
    "api_keys": {
        "enabled": False,
        "keys": {}
    }
}


# ══════════════════════════════════════════════════════════════════
#  HELPERS DE CONFIGURATION
# ══════════════════════════════════════════════════════════════════

def save_config(filename: str = "dashboard_config.json"):
    """Sauvegarde la configuration dans un fichier JSON"""
    config = {
        "dashboard": DASHBOARD_CONFIG,
        "api": API_CONFIG,
        "files": {k: str(v) for k, v in DATA_FILES.items()},
        "thresholds": TRADING_THRESHOLDS,
        "integrations": INTEGRATIONS,
        "logging": {k: str(v) if isinstance(v, Path) else v for k, v in LOGGING_CONFIG.items()},
        "security": SECURITY_CONFIG,
    }
    
    with open(BASE_DIR / filename, "w") as f:
        json.dump(config, f, indent=2)
    print(f"✓ Configuration saved to {filename}")


def load_config(filename: str = "dashboard_config.json") -> dict:
    """Charge la configuration depuis un fichier JSON"""
    path = BASE_DIR / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


# ══════════════════════════════════════════════════════════════════
#  EXPORT DE CONFIGURATION POUR UTILISATION
# ══════════════════════════════════════════════════════════════════

CONFIG = {
    "dashboard": DASHBOARD_CONFIG,
    "api": API_CONFIG,
    "files": DATA_FILES,
    "thresholds": TRADING_THRESHOLDS,
    "integrations": INTEGRATIONS,
    "logging": LOGGING_CONFIG,
    "security": SECURITY_CONFIG,
    "base_dir": str(BASE_DIR),
    "mt5_dir": str(MT5_DIR),
}


if __name__ == "__main__":
    # Affiche la configuration
    print("\n" + "=" * 60)
    print("SENTINEL V11 - CONFIGURATION SUMMARY")
    print("=" * 60)
    
    print(f"\nBase directory: {BASE_DIR}")
    print(f"MT5 directory: {MT5_DIR}")
    
    print(f"\nDashboard refresh interval: {DASHBOARD_CONFIG['refresh']['interval']}s")
    print(f"API server: {API_CONFIG['server']['host']}:{API_CONFIG['server']['port']}")
    
    print(f"\nData files configured: {len(DATA_FILES)}")
    for name, path in DATA_FILES.items():
        exists = "✓" if path.exists() else "✗"
        print(f"  {exists} {name:<20} {path}")
    
    print("\n" + "=" * 60 + "\n")
    
    # Option: Save config template
    import sys
    if "--save" in sys.argv:
        save_config()
