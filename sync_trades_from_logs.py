#!/usr/bin/env python3
import json, re, os, sys
from pathlib import Path
from datetime import datetime, timezone

# ── Configuration ──────────────────────────────────────────────────────────
LOG_DIR = Path(os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/Program Files/MetaTrader 5/MQL5/Logs"
))
DB_PATH = Path(os.path.expanduser("~/Downloads/bot_project/trades_learning.json"))
TICKS_PATH = Path(os.path.expanduser("~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/ticks_v3.json"))

def load_json(path, default=None):
    if not path.exists(): return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except:
        return default if default is not None else {}

def sync():
    print(f"🔍 Recherche de trades dans {LOG_DIR}...")
    
    # 1. Charger la DB existante
    db = load_json(DB_PATH, {"trades": [], "stats": {}})
    existing_tickets = {str(t.get("ticket")) for t in db.get("trades", [])}
    
    # 2. Charger les données techniques pour enrichissement
    tech_data = {}
    ticks = load_json(TICKS_PATH, [])
    for tick in (ticks if isinstance(ticks, list) else [ticks]):
        sym = tick.get("sym", tick.get("symbol", "")).upper()
        if sym: tech_data[sym] = tick

    # 3. Parcourir les logs récents
    new_trades = []
    log_files = sorted(LOG_DIR.glob("2026030[89].log")) # Hier et aujourd'hui
    
    # Regex pour MT5 deals
    # Exemple: deal #8576719 buy 0.10 USDJPY at 158.371 done (profit -8.15)
    # Note: On cherche aussi les commentaires de l'EA
    pattern = re.compile(r'deal #(\d+)\s+(\w+)\s+([\d.]+)\s+(\w+)\s+at\s+([\d.]+).*?profit\s+([-\d.]+)')

    for log_file in log_files:
        try:
            content = log_file.read_bytes().decode('utf-16')
            for line in content.splitlines():
                match = pattern.search(line)
                if match:
                    ticket, t_type, volume, symbol, price, profit = match.groups()
                    ticket = str(ticket)
                    
                    if ticket in existing_tickets:
                        continue
                        
                    # Filtrer: on ne veut que les "deals de sortie" (profit est souvent présent sur les sorties)
                    # Dans MT5, le profit est affiché quand un trade est fermé.
                    pnl = float(profit)
                    sym = symbol.upper()
                    
                    # Enrichissement minimal
                    tech = tech_data.get(sym, {})
                    
                    trade_info = {
                        "ticket": ticket,
                        "symbol": sym,
                        "type": t_type.lower(),
                        "volume": float(volume),
                        "entry": 0, # Non dispo dans cette ligne de log
                        "exit": float(price),
                        "pnl": pnl,
                        "result": "WIN" if pnl > 0 else "LOSS",
                        "rsi": float(tech.get("rsi", 50)),
                        "adx": float(tech.get("adx", 25)),
                        "atr": float(tech.get("atr", 0)),
                        "spread": int(tech.get("spread", 0)),
                        "regime": int(tech.get("regime", 0)),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "label": 1 if pnl > 0 else 0,
                    }
                    
                    new_trades.append(trade_info)
                    existing_tickets.add(ticket)
                    print(f"✅ Trouvé: {sym} {t_type} {volume} | PnL: {pnl}$ | Ticket: {ticket}")
        except Exception as e:
            print(f"❌ Erreur lecture {log_file.name}: {e}")

    # 4. Sauvegarder
    if new_trades:
        db["trades"].extend(new_trades)
        all_trades = db["trades"]
        wins = sum(1 for t in all_trades if t.get("result") == "WIN")
        total = len(all_trades)
        db["stats"] = {
            "total": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins/total*100, 1) if total > 0 else 0,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
        DB_PATH.write_text(json.dumps(db, indent=2))
        print(f"\n✨ Synchro terminée ! {len(new_trades)} nouveaux trades ajoutés.")
        print(f"📊 Nouveau Total: {total}/50 | WR: {db['stats']['win_rate']}%")
    else:
        print("\nℹ️ Aucun nouveau trade trouvé dans les logs récents.")

if __name__ == "__main__":
    sync()
