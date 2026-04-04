#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("/Users/macbookpro/Downloads/bot_project/trades_learning.json")

def add_trades():
    db = json.loads(DB_PATH.read_text(encoding='utf-8'))
    existing_tickets = {str(t.get("ticket")) for t in db.get("trades", [])}
    
    # Données extraites de la capture d'écran
    screenshot_trades = [
        {"ticket":"8576719", "pnl":-8.15, "vol":0.10},
        {"ticket":"8576722", "pnl":-7.45, "vol":0.09},
        {"ticket":"8576723", "pnl":-7.39, "vol":0.09},
        {"ticket":"8576721", "pnl":-7.28, "vol":0.09},
        {"ticket":"8576725", "pnl":2.90,  "vol":0.09},
        {"ticket":"8576726_1", "pnl":2.27, "vol":0.08, "ticket_real":"8576726"},
        {"ticket":"8576726_2", "pnl":3.79, "vol":0.08, "ticket_real":"8576726"},
        {"ticket":"8576776", "pnl":3.58,  "vol":0.09},
        {"ticket":"8576851_1", "pnl":4.30, "vol":0.11, "ticket_real":"8576851"},
        {"ticket":"8576851_2", "pnl":5.96, "vol":0.11, "ticket_real":"8576851"},
        {"ticket":"8576850", "pnl":3.40,  "vol":0.11},
        {"ticket":"8576868", "pnl":4.01,  "vol":0.13},
        {"ticket":"8576872_1", "pnl":3.10, "vol":0.12, "ticket_real":"8576872"},
        {"ticket":"8576872_2", "pnl":3.63, "vol":0.12, "ticket_real":"8576872"},
        {"ticket":"8576894", "pnl":12.75, "vol":0.15},
    ]
    
    added = 0
    for t in screenshot_trades:
        ticket_id = t["ticket"]
        if ticket_id in existing_tickets:
            continue
            
        pnl = t["pnl"]
        new_trade = {
            "ticket": ticket_id,
            "symbol": "USDJPY",
            "type": "buy",
            "volume": t["vol"],
            "entry": 0,
            "exit": 0,
            "pnl": pnl,
            "result": "WIN" if pnl > 0 else "LOSS",
            "rsi": 50.0,
            "adx": 25.0,
            "atr": 0,
            "spread": 15,
            "regime": 1,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "label": 1 if pnl > 0 else 0,
        }
        db["trades"].append(new_trade)
        added += 1
        
    if added > 0:
        # Recalculer stats
        all_t = db["trades"]
        wins = sum(1 for tr in all_t if tr.get("result") == "WIN")
        total = len(all_t)
        db["stats"] = {
            "total": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins/total*100, 1) if total > 0 else 0,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
        DB_PATH.write_text(json.dumps(db, indent=2))
        print(f"✅ {added} trades ajoutés manuellement (screenshot).")
        print(f"📊 Nouveau Total: {total}/50 | WR: {db['stats']['win_rate']}%")
    else:
        print("ℹ️ Aucun nouveau trade à ajouter.")

if __name__ == "__main__":
    add_trades()
