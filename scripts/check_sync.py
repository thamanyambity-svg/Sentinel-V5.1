#!/usr/bin/env python3
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Couleurs
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"

def check_integrity():
    print(f"\n{B}🔍 DIAGNOSTIC D'INTÉGRITÉ SENTINEL{X}")
    print(f"{'='*40}")
    
    # 1. Charger Env
    load_dotenv("bot/.env")
    mt5_path_env = os.getenv("MT5_FILES_PATH")
    if mt5_path_env:
        mt5_path_env = mt5_path_env.strip("\"").strip("'")
    
    if not mt5_path_env:
        print(f" {R}✘{X} MT5_FILES_PATH absent de .env")
        return
    
    mt5_path = Path(mt5_path_env)
    print(f"📂 Dossier cible : {mt5_path}")
    
    if not mt5_path.exists():
        print(f" {R}✘{X} Dossier MT5 introuvable. Vérifiez le chemin dans .env")
        return
    print(f" {G}✔{X} Dossier MT5 accessible")

    # 2. Vérifier Fichiers Critiques
    critical_files = ["status.json", "ticks_v3.json", "trade_history.json"]
    for f in critical_files:
        p = mt5_path / f
        if p.exists():
            age = time.time() - p.stat().st_mtime
            status = G if age < 120 else Y if age < 3600 else R
            print(f" {status}•{X} {f:<18} : Présent ({int(age)}s ago)")
        else:
            print(f" {R}✘{X} {f:<18} : MANQUANT")

    # 3. Vérifier Symlinks Racine
    root_links = ["status.json", "ticks_v3.json"]
    for link in root_links:
        p = Path(link)
        if p.is_symlink():
            target = os.readlink(p)
            if target == mt5_path_env + "/" + link or target == str(mt5_path / link):
                print(f" {G}✔{X} Symlink racine {link:<10} : OK")
            else:
                print(f" {Y}⚠{X} Symlink racine {link:<10} : Mauvaise cible ({target})")
        else:
            print(f" {R}✘{X} Symlink racine {link:<10} : absent ou n'est pas un lien")

    print(f"{'='*40}")
    print(f"{B}Résultat :{X} Si tout est au {G}VERT{X}, votre bot est parfaitement synchronisé.")

if __name__ == "__main__":
    check_integrity()
