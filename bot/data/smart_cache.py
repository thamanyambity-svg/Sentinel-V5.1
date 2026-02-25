import pandas as pd
import pickle
import os
import hashlib
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
import shutil

class SmartCache:
    def __init__(self, cache_dir="bot/data/smart_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        # Auto-cleanup on init
        self.cleanup_expired()

    def get_cache_key(self, symbol: str, timeframe: str, params: dict) -> str:
        """Génère une clé de cache unique basée sur les paramètres."""
        # Sort params to ensure consistent key
        param_str = str(sorted(params.items()))
        key_data = f"{symbol}_{timeframe}_{param_str}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get_or_compute(self, 
                       symbol: str, 
                       timeframe: str, 
                       params: dict, 
                       compute_func: Callable[[], Any],
                       ttl_minutes: int = 5) -> Any:
        """
        Récupère la donnée depuis le cache si valide, sinon exécute compute_func().
        ttl_minutes: Temps de validité en minutes.
        """
        cache_key = self.get_cache_key(symbol, timeframe, params)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pkl")
        
        # 1. Vérifier le cache
        if os.path.exists(cache_file):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
                file_age = datetime.now() - mtime
                
                if file_age < timedelta(minutes=ttl_minutes):
                    # Cache valide
                    with open(cache_file, 'rb') as f:
                        data = pickle.load(f)
                    return data
            except Exception as e:
                print(f"⚠️ Cache read error ({cache_key}): {e}")
        
        # 2. Si pas de cache ou expiré, calculer
        result = compute_func()
        
        # 3. Sauvegarder le cache (si résultat valide)
        if result is not None:
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(result, f)
            except Exception as e:
                print(f"⚠️ Cache write error ({cache_key}): {e}")
        
        return result

    def cleanup_expired(self, max_age_hours=1):
        """Nettoie les fichiers de cache obsolètes (> 1h par défaut)"""
        try:
            now = datetime.now()
            count = 0
            for filename in os.listdir(self.cache_dir):
                if filename.endswith(".pkl"):
                    filepath = os.path.join(self.cache_dir, filename)
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if now - mtime > timedelta(hours=max_age_hours):
                        os.remove(filepath)
                        count += 1
            if count > 0:
                print(f"🧹 SmartCache cleaned {count} expired files.")
        except Exception as e:
            print(f"⚠️ Cache cleanup error: {e}")

    def clear_all(self):
        """Vide tout le cache."""
        try:
            shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            print("🧹 SmartCache fully cleared.")
        except Exception as e:
            print(f"❌ Failed to clear cache: {e}")
