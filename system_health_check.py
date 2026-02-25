#!/usr/bin/env python3
"""
Diagnostic Complet du Système - Sentinel V5
Vérifie tous les composants avant le test DEMO 7 jours
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Couleurs pour terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def check_status(name, condition, details=""):
    status = f"{Colors.GREEN}✅ OK{Colors.RESET}" if condition else f"{Colors.RED}❌ FAIL{Colors.RESET}"
    print(f"  {status} | {name}")
    if details:
        print(f"         {Colors.YELLOW}{details}{Colors.RESET}")
    return condition

# Charger .env
load_dotenv("bot/.env")

all_checks = []

# ========================================
# 1. CONFIGURATION ENVIRONNEMENT
# ========================================
print_header("1. CONFIGURATION ENVIRONNEMENT")

mt5_login = os.getenv("MT5_LOGIN")
mt5_server = os.getenv("MT5_SERVER")
mt5_password = os.getenv("MT5_PASSWORD")
mt5_path = os.getenv("MT5_FILES_PATH")

all_checks.append(check_status(
    "MT5 Login configuré",
    bool(mt5_login),
    f"Login: {mt5_login}" if mt5_login else "Manquant dans .env"
))

all_checks.append(check_status(
    "MT5 Server configuré",
    bool(mt5_server),
    f"Server: {mt5_server}" if mt5_server else "Manquant dans .env"
))

all_checks.append(check_status(
    "MT5 Password configuré",
    bool(mt5_password and len(mt5_password) > 0),
    "Présent (masqué)" if mt5_password else "⚠️  MANQUANT - Ajoutez MT5_PASSWORD dans .env"
))

all_checks.append(check_status(
    "MT5 Files Path configuré",
    bool(mt5_path),
    f"Path: {mt5_path[:50]}..." if mt5_path else "Manquant"
))

# ========================================
# 2. FICHIERS MT5 BRIDGE
# ========================================
print_header("2. FICHIERS MT5 BRIDGE")

if mt5_path:
    mt5_path_obj = Path(mt5_path)
    all_checks.append(check_status(
        "MT5 Files directory existe",
        mt5_path_obj.exists(),
        str(mt5_path_obj)
    ))
    
    command_dir = mt5_path_obj / "Command"
    all_checks.append(check_status(
        "Command directory existe",
        command_dir.exists(),
        str(command_dir)
    ))
    
    status_file = mt5_path_obj / "status.json"
    all_checks.append(check_status(
        "status.json détecté",
        status_file.exists(),
        "MT5 Sentinel EA semble actif" if status_file.exists() else "⚠️  Sentinel EA pas encore démarré sur MT5"
    ))
    
    # Lire status si disponible
    if status_file.exists():
        try:
            with open(status_file, 'r') as f:
                status_data = json.load(f)
            balance = status_data.get('balance', 0)
            positions = status_data.get('positions', [])
            all_checks.append(check_status(
                "Status MT5 lisible",
                True,
                f"Balance: ${balance} | Positions: {len(positions)}"
            ))
        except Exception as e:
            all_checks.append(check_status(
                "Status MT5 lisible",
                False,
                f"Erreur: {e}"
            ))
else:
    all_checks.append(check_status("MT5 Path", False, "Non configuré"))

# ========================================
# 3. CONFIGURATION TRADING
# ========================================
print_header("3. CONFIGURATION TRADING")

exec_mode = os.getenv("EXECUTION_MODE")
deriv_mode = os.getenv("DERIV_API_MODE")
trading_assets = os.getenv("TRADING_ASSETS")
risk_percent = os.getenv("TRADING_RISK_PERCENT")

all_checks.append(check_status(
    "Mode d'exécution",
    bool(exec_mode),
    f"Mode: {exec_mode}" if exec_mode else "Non défini"
))

all_checks.append(check_status(
    "Assets configurés",
    bool(trading_assets),
    f"Assets: {trading_assets}" if trading_assets else "Non définis"
))

all_checks.append(check_status(
    "Risk management",
    bool(risk_percent),
    f"Risk per trade: {risk_percent}%" if risk_percent else "Non défini"
))

# ========================================
# 4. API KEYS
# ========================================
print_header("4. API KEYS & NOTIFICATIONS")

telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
discord_token = os.getenv("DISCORD_BOT_TOKEN")
groq_key = os.getenv("GROQ_API_KEY")

all_checks.append(check_status(
    "Telegram Bot configuré",
    bool(telegram_token and telegram_chat),
    "✓ Token + Chat ID présents" if (telegram_token and telegram_chat) else "Manquant"
))

all_checks.append(check_status(
    "Discord Bot configuré",
    bool(discord_token),
    "✓ Token présent" if discord_token else "Manquant"
))

all_checks.append(check_status(
    "Groq AI configuré",
    bool(groq_key),
    "✓ API Key présente" if groq_key else "Manquant"
))

# ========================================
# 5. DÉPENDANCES PYTHON
# ========================================
print_header("5. DÉPENDANCES PYTHON")

required_modules = [
    "dotenv",
    "asyncio",
    "aiohttp",
    "logging"
]

for module in required_modules:
    try:
        __import__(module.replace("-", "_"))
        all_checks.append(check_status(f"Module {module}", True, "Installé"))
    except ImportError:
        all_checks.append(check_status(f"Module {module}", False, "⚠️  Manquant - pip install requis"))

# ========================================
# 6. ÉTAT DU BOT
# ========================================
print_header("6. ÉTAT DU BOT ACTUEL")

pid_file = Path("bot.pid")
if pid_file.exists():
    try:
        with open(pid_file, 'r') as f:
            pid = f.read().strip()
        # Vérifier si le process existe
        import subprocess
        result = subprocess.run(['ps', '-p', pid], capture_output=True)
        is_running = result.returncode == 0
        all_checks.append(check_status(
            "Bot actuellement en cours",
            is_running,
            f"PID {pid} - {'RUNNING' if is_running else 'STOPPED (PID file stale)'}"
        ))
    except Exception as e:
        all_checks.append(check_status("Bot status", False, f"Erreur: {e}"))
else:
    all_checks.append(check_status(
        "Bot actuellement en cours",
        False,
        "Aucun bot détecté (bot.pid absent)"
    ))

# ========================================
# 7. ESPACE DISQUE
# ========================================
print_header("7. RESSOURCES SYSTÈME")

import shutil
disk_usage = shutil.disk_usage(".")
free_gb = disk_usage.free / (1024**3)
all_checks.append(check_status(
    "Espace disque libre",
    free_gb > 5,
    f"{free_gb:.1f} GB disponibles"
))

# ========================================
# RÉSUMÉ FINAL
# ========================================
print_header("RÉSUMÉ FINAL")

passed = sum(all_checks)
total = len(all_checks)
success_rate = (passed / total) * 100

print(f"  Tests réussis: {passed}/{total} ({success_rate:.1f}%)\n")

if success_rate == 100:
    print(f"{Colors.GREEN}{Colors.BOLD}  ✅ SYSTÈME PRÊT POUR LE TEST DEMO{Colors.RESET}\n")
elif success_rate >= 80:
    print(f"{Colors.YELLOW}{Colors.BOLD}  ⚠️  SYSTÈME OPÉRATIONNEL AVEC AVERTISSEMENTS{Colors.RESET}")
    print(f"{Colors.YELLOW}     Corrigez les problèmes mineurs avant de lancer{Colors.RESET}\n")
else:
    print(f"{Colors.RED}{Colors.BOLD}  ❌ SYSTÈME NON PRÊT - CORRECTIONS REQUISES{Colors.RESET}")
    print(f"{Colors.RED}     Corrigez les erreurs critiques avant de continuer{Colors.RESET}\n")

# ========================================
# RECOMMANDATIONS
# ========================================
if success_rate < 100:
    print_header("ACTIONS REQUISES")
    
    if not mt5_password:
        print(f"  {Colors.RED}1. Ajoutez MT5_PASSWORD dans bot/.env{Colors.RESET}")
        print(f"     MT5_PASSWORD=VotreMotDePasseDEMO\n")
    
    if mt5_path and not (Path(mt5_path) / "status.json").exists():
        print(f"  {Colors.YELLOW}2. Démarrez Sentinel EA sur MT5{Colors.RESET}")
        print(f"     - Ouvrez MT5")
        print(f"     - Glissez Sentinel.mq5 sur un graphique")
        print(f"     - Vérifiez que status.json apparaît\n")
    
    print(f"\n{Colors.BLUE}Relancez ce diagnostic après corrections:{Colors.RESET}")
    print(f"  python system_health_check.py\n")

sys.exit(0 if success_rate == 100 else 1)
