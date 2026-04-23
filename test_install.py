#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V11 — test_install.py                                     ║
║  Script de validation d'installation & configuration                ║
║                                                                      ║
║  Vérifie:                                                            ║
║    • Dépendances Python instalées                                   ║
║    • Fichiers de données accessibles                                ║
║    • Dashboard Manager fonctionnel                                  ║
║    • API Flask démarrable                                           ║
║    • Endpoints accessibles                                          ║
║                                                                      ║
║  Usage:                                                              ║
║    python test_install.py                                            ║
║    python test_install.py --verbose  (mode debug)                   ║
║    python test_install.py --api      (test API uniquement)          ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import time
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Colors
class C:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def info(msg):
    print(f"{C.CYAN}ℹ{C.RESET} {msg}")

def success(msg):
    print(f"{C.GREEN}✓{C.RESET} {msg}")

def warning(msg):
    print(f"{C.YELLOW}⚠{C.RESET} {msg}")

def error(msg):
    print(f"{C.RED}✗{C.RESET} {msg}")

def header(msg):
    print(f"\n{C.BOLD}{C.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
    print(f"{C.BOLD}{msg}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}\n")


# ══════════════════════════════════════════════════════════════════
#  TEST 1: DÉPENDANCES
# ══════════════════════════════════════════════════════════════════

def test_dependencies():
    """Vérifie que tous les packages Python nécessaires sont installés"""
    header("1️⃣  TEST DES DÉPENDANCES PYTHON")
    
    required = {
        "flask": "Flask (API server)",
        "flask_cors": "Flask-CORS (Cross-Origin)",
        "pathlib": "Pathlib (File handling)",
        "json": "JSON (Data parsing)",
    }
    
    failed = []
    
    for package, description in required.items():
        try:
            __import__(package)
            success(f"{description:40} installed")
        except ImportError:
            error(f"{description:40} MISSING")
            failed.append(package)
    
    if failed:
        warning(f"\nInstall missing packages:\n  pip install {' '.join(failed)}")
        return False
    
    success("All dependencies OK\n")
    return True


# ══════════════════════════════════════════════════════════════════
#  TEST 2: FICHIERS & CHEMINS
# ══════════════════════════════════════════════════════════════════

def test_files():
    """Vérifie l'existence des fichiers critiques"""
    header("2️⃣  TEST DES FICHIERS & CHEMINS")
    
    base_dir = Path(__file__).parent
    
    required_files = {
        "dashboard_manager.py": "Core manager",
        "api_server.py": "REST API server",
        "config_sentinel.py": "Configuration",
        "dashboard.html": "Web dashboard (original)",
    }
    
    info(f"Base directory: {base_dir}\n")
    
    failed = []
    for filename, description in required_files.items():
        path = base_dir / filename
        if path.exists():
            size = path.stat().st_size
            success(f"{filename:30} ({size:>8} bytes) — {description}")
        else:
            error(f"{filename:30} MISSING")
            failed.append(filename)
    
    if failed:
        error(f"\nMissing files: {', '.join(failed)}")
        return False
    
    success("All core files present\n")
    return True


# ══════════════════════════════════════════════════════════════════
#  TEST 3: DASHBOARD MANAGER
# ══════════════════════════════════════════════════════════════════

def test_dashboard_manager():
    """Teste le gestionnaire dashboard"""
    header("3️⃣  TEST DASHBOARD MANAGER")
    
    try:
        from dashboard_manager import DashboardManager, CacheManager, Colors
        success("Dashboard manager imported successfully")
        
        # Créer instance
        mgr = DashboardManager()
        success("DashboardManager instance created")
        
        # Tester cache
        mgr.cache.set("test", {"value": 123}, ttl=5)
        cached = mgr.cache.get("test")
        if cached and cached["value"] == 123:
            success("Cache system working")
        else:
            error("Cache system failed")
            return False
        
        # Tester format
        formatted = mgr.format_number(1234.567, decimals=2, currency=True)
        if "$1,234.57" in formatted:
            success(f"Number formatting working: {formatted}")
        else:
            warning(f"Unexpected format: {formatted}")
        
        # Tester chargement données
        status = mgr.load_data("status", cache_ttl=0)
        if status:
            success("Successfully loaded status.json")
            if "balance" in status:
                success(f"  → Balance: ${status.get('balance', 0):,.2f}")
        else:
            warning("status.json not found (expected if EA not running)")
        
        # Metrics
        metrics = mgr.get_metrics()
        success(f"Metrics: renders={metrics['renders']}, cache_entries={metrics['cache']['total']}")
        
        return True
        
    except Exception as e:
        error(f"Dashboard manager test failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
#  TEST 4: API SERVER
# ══════════════════════════════════════════════════════════════════

def test_api_server():
    """Teste l'API Flask"""
    header("4️⃣  TEST API SERVER")
    
    try:
        from api_server import app
        success("Flask app imported successfully")
        
        # Créer test client
        client = app.test_client()
        
        # Test health endpoint
        response = client.get('/api/v1/health')
        if response.status_code == 200:
            success(f"Health endpoint: {response.status_code} OK")
            data = response.get_json()
            if data.get("status") == "success":
                success("  → Status: healthy")
        else:
            error(f"Health endpoint failed: {response.status_code}")
            return False
        
        # Test account endpoint
        response = client.get('/api/v1/account')
        if response.status_code in [200, 500]:  # 500 si status.json absent
            success(f"Account endpoint: {response.status_code}")
        
        # Test positions endpoint
        response = client.get('/api/v1/positions')
        if response.status_code == 200:
            success(f"Positions endpoint: {response.status_code} OK")
        
        # Test dashboard endpoint
        response = client.get('/api/v1/dashboard')
        if response.status_code == 200:
            success(f"Dashboard endpoint: {response.status_code} OK")
            data = response.get_json()
            if "data" in data:
                success("  → Full dashboard data available")
        
        return True
        
    except Exception as e:
        error(f"API server test failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
#  TEST 5: CONFIGURATION
# ══════════════════════════════════════════════════════════════════

def test_configuration():
    """Teste la configuration"""
    header("5️⃣  TEST CONFIGURATION")
    
    try:
        from config_sentinel import CONFIG, DATA_FILES
        success("Configuration module imported")
        
        # Afficher résumé config
        print(f"Dashboard refresh interval: {CONFIG['dashboard']['refresh']['interval']}s")
        print(f"API server port: {CONFIG['api']['server']['port']}")
        print(f"Cache TTL: {CONFIG['api']['cache']['default_ttl']}s")
        
        # Vérifier fichiers config
        missing = []
        for name, path in DATA_FILES.items():
            path = Path(path)
            exists = "✓" if path.exists() else "✗"
            exists_sym = C.GREEN + "✓" + C.RESET if path.exists() else C.RED + "✗" + C.RESET
            print(f"  {exists_sym} {name:20} {path}")
            if not path.exists():
                missing.append(name)
        
        if missing:
            warning(f"\nSome data files not found: {', '.join(missing)}")
            warning("This is expected if MT5 EA is not running.")
        else:
            success("All data files accessible")
        
        return True
        
    except Exception as e:
        error(f"Configuration test failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
#  RÉSUMÉ
# ══════════════════════════════════════════════════════════════════

def run_all_tests(verbose=False, api_only=False):
    """Exécute tous les tests"""
    print(f"\n{C.BOLD}{C.CYAN}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   SENTINEL V11 - INSTALLATION & CONFIGURATION TEST        ║")
    print("║             Testing complete setup validation              ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{C.RESET}")
    
    results = {}
    
    if not api_only:
        results["Dependencies"] = test_dependencies()
        if not results["Dependencies"]:
            error("Please install dependencies first!")
            return False
        
        results["Files"] = test_files()
        if not results["Files"]:
            error("Core files missing!")
            return False
        
        results["Dashboard Manager"] = test_dashboard_manager()
    
    results["API Server"] = test_api_server()
    results["Configuration"] = test_configuration()
    
    # Résumé final
    header("📊 RÉSUMÉ DES TESTS")
    
    for test_name, result in results.items():
        status = f"{C.GREEN}PASS{C.RESET}" if result else f"{C.RED}FAIL{C.RESET}"
        print(f"  {status}  {test_name}")
    
    all_passed = all(results.values())
    
    print(f"\n{C.BOLD}{C.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
    
    if all_passed:
        print(f"\n{C.GREEN}{C.BOLD}✓ ALL TESTS PASSED!{C.RESET}")
        print(f"\n{C.CYAN}Next steps:{C.RESET}")
        print(f"  1. Start API server:  {C.BOLD}python api_server.py{C.RESET}")
        print(f"  2. Open in browser:   {C.BOLD}http://localhost:5000{C.RESET}")
        print(f"  3. Test endpoints:    {C.BOLD}curl http://localhost:5000/api/v1/health{C.RESET}")
        return True
    else:
        print(f"\n{C.RED}{C.BOLD}✗ SOME TESTS FAILED{C.RESET}")
        print(f"\nPlease fix the issues above and try again.")
        return False


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentinel V11 Installation Test")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--api", action="store_true", help="Test API only")
    args = parser.parse_args()
    
    success = run_all_tests(verbose=args.verbose, api_only=args.api)
    
    sys.exit(0 if success else 1)
