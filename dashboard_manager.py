"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V11 — dashboard_manager.py                                ║
║  Gestionnaire de Dashboard Refactorisé (Classe)                      ║
║                                                                      ║
║  Améliorations:                                                      ║
║    ✓ Architecture OOP pour meilleure maintenabilité                 ║
║    ✓ Système de caching pour éviter les lectures répétées           ║
║    ✓ Gestion d'erreurs centralisée                                  ║
║    ✓ Logging structuré                                              ║
║    ✓ Validation de données robuste                                  ║
║    ✓ Support pour plugins/extensions                                ║
║    ✓ Métriques de performance                                       ║
║                                                                      ║
║  Usage:                                                              ║
║    from dashboard_manager import DashboardManager                    ║
║    manager = DashboardManager()                                      ║
║    manager.refresh()                                                 ║
║    print(manager.render())                                           ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import re


# ══════════════════════════════════════════════════════════════════
#  LOGGING STRUCTURÉ
# ══════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s | %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  CODES COULEURS ANSI
# ══════════════════════════════════════════════════════════════════

class Colors:
    """Codes ANSI de couleurs minimalistes"""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"

    @staticmethod
    def apply(text: str, *codes) -> str:
        return "".join(codes) + str(text) + Colors.RESET

    @staticmethod
    def bold(t): return Colors.apply(t, Colors.BOLD)
    @staticmethod
    def green(t): return Colors.apply(t, Colors.GREEN)
    @staticmethod
    def red(t): return Colors.apply(t, Colors.RED)
    @staticmethod
    def yellow(t): return Colors.apply(t, Colors.YELLOW)
    @staticmethod
    def cyan(t): return Colors.apply(t, Colors.CYAN)
    @staticmethod
    def dim(t): return Colors.apply(t, Colors.DIM)
    @staticmethod
    def magenta(t): return Colors.apply(t, Colors.MAGENTA)


# ══════════════════════════════════════════════════════════════════
#  CACHE SYSTEM
# ══════════════════════════════════════════════════════════════════

@dataclass
class CacheEntry:
    """Entrée de cache avec métadonnées"""
    data: Any
    timestamp: float
    ttl: float  # Time-to-live en secondes

    def is_valid(self) -> bool:
        """Vérifie si le cache est encore valide"""
        return (time.time() - self.timestamp) < self.ttl

    def age_seconds(self) -> float:
        """Retourne l'âge en secondes"""
        return time.time() - self.timestamp


class CacheManager:
    """Gestionnaire de cache simple mais efficace"""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Récupère une valeur du cache (retourne None si invalide)"""
        with self._lock:
            if key not in self._cache:
                return None
            entry = self._cache[key]
            if not entry.is_valid():
                del self._cache[key]
                logger.debug(f"Cache expired for key: {key}")
                return None
            return entry.data

    def set(self, key: str, value: Any, ttl: float = 5.0):
        """Stocke une valeur avec un TTL"""
        with self._lock:
            self._cache[key] = CacheEntry(data=value, timestamp=time.time(), ttl=ttl)
            logger.debug(f"Cache set for key: {key} (TTL: {ttl}s)")

    def clear(self, pattern: str = ""):
        """Vide le cache (partiellement si pattern fourni)"""
        with self._lock:
            if pattern:
                keys_to_delete = [k for k in self._cache.keys() if pattern in k]
                for k in keys_to_delete:
                    del self._cache[k]
            else:
                self._cache.clear()

    def stats(self) -> Dict[str, int]:
        """Retourne les stats du cache"""
        with self._lock:
            valid = sum(1 for e in self._cache.values() if e.is_valid())
            return {"total": len(self._cache), "valid": valid}


# ══════════════════════════════════════════════════════════════════
#  DATA LOADERS (PLUGGABLE)
# ══════════════════════════════════════════════════════════════════

class DataLoader(ABC):
    """Interface pour les chargeurs de données"""

    @abstractmethod
    def load(self) -> Optional[Dict[str, Any]]:
        """Charge les données"""
        pass

    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> bool:
        """Valide la structure des données"""
        pass


class JSONFileLoader(DataLoader):
    """Charge des données d'un fichier JSON"""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> Optional[Dict[str, Any]]:
        try:
            if not self.path.exists() or self.path.stat().st_size == 0:
                return None
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {self.path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading {self.path}: {e}")
            return None

    def validate(self, data: Dict[str, Any]) -> bool:
        """Validation de base (à surcharger)"""
        return isinstance(data, dict)


class CSVFileLoader(DataLoader):
    """Charge les 3 dernières lignes d'un CSV"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.max_lines = 10

    def load(self) -> Optional[Dict[str, Any]]:
        try:
            if not self.path.exists():
                return None
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) <= 1:
                return None
            return {"header": lines[0].strip(), "rows": lines[-self.max_lines:]}
        except Exception as e:
            logger.error(f"Error loading CSV {self.path}: {e}")
            return None

    def validate(self, data: Dict[str, Any]) -> bool:
        return "header" in data and "rows" in data


# ══════════════════════════════════════════════════════════════════
#  GESTIONNAIRE PRINCIPAL
# ══════════════════════════════════════════════════════════════════

class DashboardManager:
    """Gestionnaire centralisé pour tous les composants du dashboard"""

    def __init__(self, config_path: Optional[Path] = None):
        self.base_dir = Path(__file__).parent
        self.config = self._load_config(config_path)
        self.cache = CacheManager()
        self.loaders: Dict[str, DataLoader] = {}
        self._init_loaders()
        self.metrics = {"renders": 0, "refreshes": 0, "errors": 0}
        self._lock = threading.RLock()
        logger.info("DashboardManager initialized")

    def _load_config(self, path: Optional[Path]) -> Dict[str, Any]:
        """Charge la configuration"""
        if path is None:
            path = self.base_dir / "dashboard_config.json"
        
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load config: {e}")
        
        # Configuration par défaut
        return {
            "width": 72,
            "refresh_interval": 5,
            "cache_ttl": 5,
            "mt5_dir": "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files",
            "files": {
                "status": "status.json",
                "ticks": "ticks_v3.json",
                "backtest": "backtest_summary.json",
                "training": "training_history.json",
                "action_plan": "action_plan.json",
                "fundamental": "fundamental_state.json",
                "bot_log": "bot.log",
            }
        }

    def _init_loaders(self):
        """Initialise les chargeurs de données"""
        mt5_dir = Path(self.config["mt5_dir"])
        base_dir = self.base_dir

        # Tous les loaders avec chemins
        self.loaders = {
            "status": JSONFileLoader(mt5_dir / self.config["files"]["status"]),
            "ticks": JSONFileLoader(mt5_dir / self.config["files"]["ticks"]),
            "backtest": JSONFileLoader(base_dir / self.config["files"]["backtest"]),
            "training": JSONFileLoader(base_dir / self.config["files"]["training"]),
            "action_plan": JSONFileLoader(base_dir / self.config["files"]["action_plan"]),
            "fundamental": JSONFileLoader(base_dir / self.config["files"]["fundamental"]),
        }

    def load_data(self, key: str, cache_ttl: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Charge les données avec caching"""
        cache_ttl = cache_ttl or self.config["cache_ttl"]

        # Essayer le cache
        cached = self.cache.get(f"data:{key}")
        if cached is not None:
            return cached

        # Charger le fichier
        if key not in self.loaders:
            logger.warning(f"No loader for key: {key}")
            return None

        try:
            data = self.loaders[key].load()
            if data and self.loaders[key].validate(data):
                self.cache.set(f"data:{key}", data, ttl=cache_ttl)
                return data
            return None
        except Exception as e:
            logger.error(f"Error loading data for {key}: {e}")
            self.metrics["errors"] += 1
            return None

    def refresh(self):
        """Rafraîchit toutes les données"""
        self.cache.clear()
        self.metrics["refreshes"] += 1
        logger.info("Dashboard data refreshed")

    def format_number(self, value: Any, decimals: int = 2, currency: bool = False) -> str:
        """Formate les nombres"""
        try:
            if isinstance(value, (int, float)):
                fmt = f"${value:,.{decimals}f}" if currency else f"{value:,.{decimals}f}"
                return fmt
            return str(value)
        except Exception:
            return str(value)

    def format_timestamp(self, ts: float) -> str:
        """Formate un timestamp"""
        try:
            diff = time.time() - float(ts)
            if diff < 60:
                return f"{int(diff)}s ago"
            elif diff < 3600:
                return f"{int(diff/60)}m ago"
            else:
                h = int(diff / 3600)
                m = int((diff % 3600) / 60)
                return f"{h}h{m}m ago"
        except Exception:
            return "unknown"

    def build_box(self, title: str, content: List[str]) -> List[str]:
        """Construit une boîte formatée"""
        width = self.config["width"]
        lines = []
        
        # Top
        inner = width - 2
        if title:
            pad = inner - len(title) - 2
            left = pad // 2
            right = pad - left
            lines.append(Colors.cyan("╔" + "═" * left + f" {Colors.bold(title)} " + "═" * right + "╗"))
        else:
            lines.append(Colors.cyan("╔" + "═" * inner + "╗"))

        # Content
        for line in content:
            # Remove ANSI codes to calculate padding
            clean = re.sub(r'\033\[[0-9;]*m', '', line)
            pad = max(0, width - 2 - len(clean))
            lines.append(Colors.cyan("║") + " " + line + " " * pad + Colors.cyan("║"))

        # Bottom
        lines.append(Colors.cyan("╚" + "═" * inner + "╝"))

        return lines

    def render_summary(self) -> str:
        """Rend un petit résumé (peut être appelé rapidement)"""
        self.metrics["renders"] += 1
        lines = []
        
        # Header
        lines.append(Colors.cyan("╔" + "═" * 36 + "╗"))
        lines.append(Colors.cyan("║") + Colors.bold(" SENTINEL V11 RAPID DASHBOARD ") + Colors.cyan("║"))
        lines.append(Colors.cyan("╚" + "═" * 36 + "╝"))
        
        # Account summary
        status = self.load_data("status")
        if status:
            balance = status.get("balance", 0)
            lines.append(f"  Balance: {Colors.bold(Colors.green(f'${balance:,.2f}'))}")
        
        return "\n".join(lines)

    def get_metrics(self) -> Dict[str, int]:
        """Retourne les métriques de performance"""
        return {**self.metrics, "cache": self.cache.stats()}


# ══════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mgr = DashboardManager()
    
    print("\n" + Colors.cyan("=" * 50))
    print(Colors.bold(Colors.cyan("Dashboard Manager Test")))
    print(Colors.cyan("=" * 50) + "\n")
    
    # Test loading
    status = mgr.load_data("status")
    if status:
        print(Colors.green("✓") + " Status loaded")
    else:
        print(Colors.yellow("⚠") + " Status not available")
    
    # Metrics
    print(f"\n{Colors.bold('Metrics')}:")
    for k, v in mgr.get_metrics().items():
        print(f"  {k}: {v}")
    
    print("\n" + Colors.cyan("=" * 50) + "\n")
