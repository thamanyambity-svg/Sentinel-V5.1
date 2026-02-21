#!/usr/bin/env python3
"""
Script de diagnostic pour voir le contenu de ticks_v3.json et l'analyse par actif.
Lancez depuis la racine: python3 scripts/diagnostic_ticks.py
"""
import asyncio
import json
import os
import sys

# Project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env
from dotenv import load_dotenv
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(root, "bot", ".env"))

MT5_FILES = os.environ.get("MT5_FILES_PATH", os.path.expanduser("~/Library/Application Support/MetaQuotes/Terminal/COMMON/Files"))
TICKS_PATH = os.path.join(MT5_FILES, "ticks_v3.json")
M5_PATH = os.path.join(MT5_FILES, "m5_bars.json")

def main():
    print("=== Diagnostic ticks / M5 ===\n")
    print("MT5_FILES_PATH:", MT5_FILES)
    print("ticks_v3.json:", TICKS_PATH)
    print("m5_bars.json:", M5_PATH)
    print()

    if not os.path.exists(TICKS_PATH):
        print("❌ ticks_v3.json NON TROUVÉ — Sentinel doit exporter les ticks.")
        print("   Vérifiez: EA attaché, ExportTickData=true, MT5_FILES_PATH correct.")
        return

    with open(TICKS_PATH, "r") as f:
        ticks = json.load(f)

    print("✓ ticks_v3.json trouvé")
    print("  timestamp:", ticks.get("t", "n/a"))
    tick_values = ticks.get("ticks", {})
    print("  symboles dans ticks:", list(tick_values.keys()))
    for sym, val in tick_values.items():
        print(f"    {sym}: {val}")

    if os.path.exists(M5_PATH):
        with open(M5_PATH, "r") as f:
            m5 = json.load(f)
        print("\n✓ m5_bars.json trouvé")
        print("  symboles:", list(m5.keys()))
    else:
        print("\n❌ m5_bars.json NON TROUVÉ")

    # Try analysis via market_intelligence
    print("\n--- Analyse via get_symbol_analysis ---")
    try:
        from bot.ai_agents.market_intelligence import MarketIntelligence

        async def run():
            brain = MarketIntelligence()
            for asset in ["Volatility 100 Index", "Volatility 75 Index"]:
                a = await brain.get_symbol_analysis(asset)
                print(f"\n{asset}:")
                print("  valid:", a.get("valid"))
                print("  price:", a.get("price"))
                print("  change_percent:", a.get("change_percent"))
                print("  error:", a.get("error"))

        asyncio.run(run())
    except Exception as e:
        print("Erreur:", e)

if __name__ == "__main__":
    main()
