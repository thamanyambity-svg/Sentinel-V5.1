"""
Aladdin Pro V7.19 — point d'entrée officiel.
Délègue à bot.main (Deriv + MT5 + Discord + stack complète).
L'EA MT5 correspondant : Aladdin_Pro_V7_19_Live.mq5
"""
import os
import runpy
import sys

os.environ.setdefault("ALADDIN_EA_VERSION", "7.19")

if __name__ == "__main__":
    print("🚀 Aladdin Pro V7.19 — démarrage (orchestrateur Python → bot.main)")
    sys.argv[0] = "bot.main"
    runpy.run_module("bot.main", run_name="__main__", alter_sys=True)
