#!/usr/bin/env python3
import json, os, shutil
from datetime import datetime

MT5_COMMON = os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
)
MT5_FILES = os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
)
BOT_DIR         = os.path.expanduser("~/Downloads/bot_project")
OUTPUT_LEARNING = os.path.join(BOT_DIR, "trades_learning.json")

def find_trade_history():
    candidates = [
        os.path.join(MT5_COMMON, "trade_history.json"),
        os.path.join(MT5_FILES,  "trade_history.json"),
    ]
    for root, dirs, files in os.walk(os.path.expanduser(
        "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    )):
        if "trade_history.json" in files:
            candidates.append(os.path.join(root, "trade_history.json"))
    for path in candidates:
        if os.path.exists(path):
            print(f"  Trouve: {path} ({os.path.getsize(path)} bytes)")
            return path
    return None

def main():
    print("=" * 60)
    print("  BACKTEST -> ML CONVERTER")
    print("=" * 60)
    print("\nRecherche trade_history.json...")
    source = find_trade_history()
    if not source:
        print("INTROUVABLE - attends la fin du backtest puis relance")
        return

    with open(source) as f:
        data = json.load(f)
    trades_raw = data.get("trades", [])
    print(f"Trades bruts: {len(trades_raw)}")

    converted, skipped = [], 0
    for t in trades_raw:
        rsi = float(t.get("rsi", 50.0))
        adx = float(t.get("adx", 0.0))
        pnl = float(t.get("pnl", 0.0))
        if rsi == 50.0 and adx == 0.0:
            skipped += 1
            continue
        converted.append({
            "rsi": rsi, "adx": adx,
            "atr": float(t.get("atr", 0.001)),
            "spread": int(t.get("spread", 20)),
            "regime": int(t.get("regime", 0)),
            "hour": int(t.get("hour", 12)),
            "day_of_week": int(t.get("day_of_week", 2)),
            "ema_distance": float(t.get("ema_distance", 0.0)),
            "confluence": float(t.get("confluence", 0.0)),
            "symbol": t.get("symbol", "UNKNOWN"),
            "type": t.get("type", "buy"),
            "session": t.get("session", "OFF"),
            "pnl": pnl,
            "duration": int(t.get("duration", 0)),
            "volume": float(t.get("volume", 0.01)),
            "outcome": 1 if pnl > 0 else 0,
            "timestamp": datetime.now().isoformat()
        })

    wins = sum(1 for t in converted if t["outcome"] == 1)
    wr   = (wins / len(converted) * 100) if converted else 0
    print(f"Convertis : {len(converted)} | Ignores: {skipped}")
    print(f"Win Rate  : {wr:.1f}% ({wins}W / {len(converted)-wins}L)")

    sessions = {}
    for t in converted:
        sessions[t["session"]] = sessions.get(t["session"], 0) + 1
    print("\nSessions:")
    for s, n in sorted(sessions.items(), key=lambda x: -x[1]):
        print(f"  {s}: {n}")

    symbols = {}
    for t in converted:
        symbols[t["symbol"]] = symbols.get(t["symbol"], 0) + 1
    print("\nSymboles:")
    for s, n in sorted(symbols.items(), key=lambda x: -x[1]):
        print(f"  {s}: {n}")

    if os.path.exists(OUTPUT_LEARNING):
        bak = OUTPUT_LEARNING + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(OUTPUT_LEARNING, bak)
        print(f"\nBackup: {bak}")

    with open(OUTPUT_LEARNING, "w") as f:
        json.dump(converted, f, indent=2)
    print(f"\nSauve: {OUTPUT_LEARNING}")
    print("Lance: python3 continuous_trainer.py")

if __name__ == "__main__":
    main()
