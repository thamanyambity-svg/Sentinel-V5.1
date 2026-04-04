#!/usr/bin/env python3
"""Liste les dossiers candidats (un seul dossier = tout le bridge fichier)."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.bridge.mt5_path_resolver import list_status_candidates, resolve_mt5_files_path

def main():
    now = time.time()
    rows = list_status_candidates()
    print("Dossiers avec status.json (plus récent en premier) :", len(rows))
    for d, m, fp in rows[:12]:
        print(f"  {now - m:6.0f}s  {d}")
    exp = os.environ.get("MT5_FILES_PATH", "").strip() or None
    p, r = resolve_mt5_files_path(exp)
    print()
    print("resolve_mt5_files_path →", r)
    print("  dossier unique :", p)
    if not rows or min(now - m for _d, m, _fp in rows) > 300:
        print()
        print("Aucun flux récent : lance MT5 + EA sur ce terminal pour rafraîchir ce dossier.")

if __name__ == "__main__":
    main()
