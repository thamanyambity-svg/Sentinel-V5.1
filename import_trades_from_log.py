import json, re, os
from pathlib import Path
from datetime import datetime

MT5_LOG = Path(os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/Program Files/MetaTrader 5/MQL5/Logs"
))
DB_PATH = Path(os.path.expanduser("~/Downloads/bot_project/trades_learning.json"))

# Lire tous les logs disponibles
log_content = ""
for log_file in sorted(MT5_LOG.glob("*.log")):
    try:
        content = log_file.read_bytes()
        try:
            log_content += content.decode("utf-16")
        except:
            log_content += content.decode("utf-8", errors="ignore")
    except: pass

# Pattern pour détecter les trades fermés dans les logs MT5
# Format MT5: deal #TICKET symbol type volume at price
patterns = [
    r'deal #(\d+).*?(EURUSD|GBPUSD|USDJPY|XAUUSD|AUDUSD|USDCAD).*?(buy|sell).*?(\d+\.\d+).*?profit\s+([-\d.]+)',
    r'#(\d+)\s+(EURUSD|GBPUSD|USDJPY|XAUUSD)\s+(buy|sell)\s+([\d.]+)\s+.*?profit[:\s]+([-\d.]+)',
]

# On va construire les trades depuis les données de la capture d'écran
# que tu as partagée (données manuelles pour démarrer)
manual_trades = [
    # Données extraites de ta capture MT5 d'hier soir et aujourd'hui
    {"ticket":"8573969","symbol":"USDJPY","type":"buy","volume":0.10,"entry":157.749,"exit":157.830,"profit":5.13,"session":"NEW_YORK"},
    {"ticket":"8573970","symbol":"USDJPY","type":"buy","volume":0.10,"entry":157.750,"exit":157.830,"profit":5.07,"session":"NEW_YORK"},
    {"ticket":"8574024","symbol":"USDJPY","type":"buy","volume":0.21,"entry":157.784,"exit":157.682,"profit":-13.58,"session":"NEW_YORK"},
    {"ticket":"8574024","symbol":"EURUSD","type":"sell","volume":0.11,"entry":1.15760,"exit":1.15884,"profit":-13.64,"session":"NEW_YORK"},
    {"ticket":"8574024","symbol":"GBPUSD","type":"sell","volume":0.09,"entry":1.33237,"exit":1.33359,"profit":-11.97,"session":"NEW_YORK"},
    {"ticket":"8574028","symbol":"EURUSD","type":"sell","volume":0.09,"entry":1.15883,"exit":1.16001,"profit":-10.89,"session":"NEW_YORK"},
    {"ticket":"8574029","symbol":"GBPUSD","type":"sell","volume":0.08,"entry":1.33367,"exit":1.33484,"profit":-9.36,"session":"NEW_YORK"},
    {"ticket":"8574125","symbol":"EURUSD","type":"sell","volume":0.07,"entry":1.33473,"exit":1.33593,"profit":-8.47,"session":"NEW_YORK"},
    {"ticket":"8574126","symbol":"GBPUSD","type":"sell","volume":0.07,"entry":1.33478,"exit":1.33598,"profit":-8.40,"session":"NEW_YORK"},
    {"ticket":"8574129","symbol":"GBPUSD","type":"sell","volume":0.08,"entry":1.33513,"exit":1.33633,"profit":-9.68,"session":"NEW_YORK"},
    {"ticket":"8574129","symbol":"GBPUSD","type":"sell","volume":0.08,"entry":1.33508,"exit":1.33628,"profit":-9.60,"session":"NEW_YORK"},
    {"ticket":"8574143","symbol":"USDJPY","type":"buy","volume":0.17,"entry":157.513,"exit":157.532,"profit":2.05,"session":"ASIA"},
    {"ticket":"8574214","symbol":"USDJPY","type":"buy","volume":0.13,"entry":157.516,"exit":157.661,"profit":11.96,"session":"ASIA"},
    {"ticket":"8574214","symbol":"USDJPY","type":"buy","volume":0.12,"entry":157.485,"exit":157.630,"profit":11.04,"session":"ASIA"},
    {"ticket":"8574215","symbol":"USDJPY","type":"buy","volume":0.12,"entry":157.493,"exit":157.642,"profit":11.34,"session":"ASIA"},
    {"ticket":"8574302","symbol":"EURUSD","type":"sell","volume":0.21,"entry":1.16129,"exit":1.16072,"profit":11.97,"session":"LONDON"},
    {"ticket":"8574303","symbol":"GBPUSD","type":"sell","volume":0.21,"entry":1.16134,"exit":1.16077,"profit":12.18,"session":"LONDON"},
    {"ticket":"8574303","symbol":"USDJPY","type":"buy","volume":0.20,"entry":157.740,"exit":157.836,"profit":12.16,"session":"LONDON"},
    {"ticket":"8574320","symbol":"USDJPY","type":"buy","volume":0.11,"entry":157.809,"exit":157.687,"profit":-8.51,"session":"LONDON"},
    {"ticket":"8574323","symbol":"USDJPY","type":"buy","volume":0.11,"entry":157.817,"exit":157.697,"profit":-8.37,"session":"LONDON"},
    {"ticket":"8574556","symbol":"GBPUSD","type":"sell","volume":0.06,"entry":1.33331,"exit":1.33462,"profit":-7.86,"session":"LONDON"},
    {"ticket":"8574556","symbol":"USDJPY","type":"buy","volume":0.14,"entry":157.879,"exit":157.935,"profit":4.96,"session":"LONDON"},
    {"ticket":"8574564","symbol":"EURUSD","type":"sell","volume":0.08,"entry":1.15796,"exit":1.15724,"profit":5.76,"session":"LONDON"},
    {"ticket":"8574564","symbol":"USDJPY","type":"buy","volume":0.14,"entry":157.873,"exit":157.935,"profit":5.50,"session":"LONDON"},
    {"ticket":"8574587","symbol":"USDJPY","type":"buy","volume":0.20,"entry":157.923,"exit":158.023,"profit":12.66,"session":"LONDON"},
    {"ticket":"8574587","symbol":"USDJPY","type":"buy","volume":0.19,"entry":157.925,"exit":158.026,"profit":12.14,"session":"LONDON"},
    {"ticket":"8574614","symbol":"USDJPY","type":"buy","volume":0.20,"entry":157.969,"exit":158.068,"profit":12.53,"session":"LONDON"},
    {"ticket":"8574634","symbol":"EURUSD","type":"sell","volume":0.09,"entry":1.15660,"exit":1.15821,"profit":-14.49,"session":"LONDON"},
    {"ticket":"8574634","symbol":"GBPUSD","type":"sell","volume":0.06,"entry":1.33367,"exit":1.33486,"profit":-7.38,"session":"LONDON"},
]

# Enrichir et dédupliquer
db = json.loads(DB_PATH.read_text()) if DB_PATH.exists() else {"trades": []}
existing = {t["ticket"] + t["symbol"] for t in db["trades"]}

added = 0
for t in manual_trades:
    key = str(t["ticket"]) + t["symbol"]
    if key in existing:
        continue
    t["ticket"]       = str(t["ticket"])
    t["result"]       = "WIN" if t["profit"] > 0 else "LOSS"
    t["label"]        = 1 if t["profit"] > 0 else 0
    t["rsi"]          = 50.0
    t["adx"]          = 30.0
    t["atr"]          = 0.5
    t["spread"]       = 15
    t["regime"]       = 1 if t["type"] == "buy" else -1
    t["collected_at"] = datetime.utcnow().isoformat()
    db["trades"].append(t)
    existing.add(key)
    added += 1

# Stats
total = len(db["trades"])
wins  = sum(1 for t in db["trades"] if t["result"] == "WIN")
db["stats"] = {
    "total":    total,
    "wins":     wins,
    "losses":   total - wins,
    "win_rate": round(wins/total*100, 1) if total > 0 else 0,
    "last_update": datetime.utcnow().isoformat(),
}

DB_PATH.write_text(json.dumps(db, indent=2))
print(f"✅ {added} trades importés")
print(f"📊 Total: {total}/50 | Wins: {wins} | WR: {db['stats']['win_rate']}%")
print(f"⏳ Manque encore: {max(0, 50-total)} trades pour entraînement ML")
