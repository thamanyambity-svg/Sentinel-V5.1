#!/usr/bin/env python3
"""Liste complete des 181 positions — 10 avril 2026"""
import re

MT5_LOG = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/logs/20260410.log"
data = open(MT5_LOG, "rb").read()
text = data.decode("utf-16-le", errors="ignore")
lines = text.split("\n")

deals = []
for l in lines:
    if "deal" in l.lower() and "done" in l.lower():
        m = re.search(r"(\d{2}:\d{2}:\d{2})\.\d+.*deal #(\d+)\s+(buy|sell)\s+(\S+)\s+(\S+)\s+at\s+(\S+)\s+done.*order #(\d+)", l, re.IGNORECASE)
        if m:
            deals.append({
                "time": m.group(1), "deal": m.group(2), "side": m.group(3).upper(),
                "volume": float(m.group(4)), "symbol": m.group(5),
                "price": float(m.group(6)), "order": m.group(7)
            })

def t2s(t):
    h, m, s = t.split(":")
    return int(h)*3600 + int(m)*60 + int(s)

def dur(s):
    if s < 0: s += 86400
    if s < 60: return "%ds" % s
    elif s < 3600: return "%dm%02ds" % (s//60, s%60)
    else: return "%dh%02dm" % (s//3600, (s%3600)//60)

def sess(t):
    h = int(t[:2])
    if h < 2: return "NUIT"
    elif h < 7: return "ASIA"
    elif h < 13: return "LONDON"
    elif h < 17: return "NY-AM"
    elif h < 20: return "NY-PM"
    else: return "NUIT-US"

def trend(ep, xp):
    mv = xp - ep
    if abs(mv) < 0.5: return "RANGE"
    return "HAUSSE" if mv > 0 else "BAISSE"

all_closed = []
all_open = []

for sym in ["USDJPY", "XAUUSD", "Volatility 100 Index"]:
    sd = [d for d in deals if d["symbol"] == sym]
    if not sd:
        continue
    stack = []
    for d in sd:
        opp = "SELL" if d["side"] == "BUY" else "BUY"
        matched = False
        for i, p in enumerate(stack):
            if p["side"] == opp:
                if sym in ["XAUUSD", "GOLD"]:
                    if p["side"] == "BUY":
                        pnl = (d["price"] - p["price"]) * d["volume"] * 100
                    else:
                        pnl = (p["price"] - d["price"]) * d["volume"] * 100
                elif sym == "USDJPY":
                    if p["side"] == "BUY":
                        pnl = (d["price"] - p["price"]) * d["volume"] * 1000 / d["price"] * 100
                    else:
                        pnl = (p["price"] - d["price"]) * d["volume"] * 1000 / d["price"] * 100
                else:
                    if p["side"] == "BUY":
                        pnl = (d["price"] - p["price"]) * d["volume"]
                    else:
                        pnl = (p["price"] - d["price"]) * d["volume"]
                all_closed.append({"entry": p, "exit": d, "pnl": round(pnl, 2), "symbol": sym})
                stack.pop(i)
                matched = True
                break
        if not matched:
            stack.append(d)
    for p in stack:
        all_open.append(p)

all_closed.sort(key=lambda c: c["entry"]["time"])

SEP = "=" * 135
LINE = "-" * 135

print()
print(SEP)
print("  LISTE COMPLÈTE DES %d POSITIONS FERMÉES — VENDREDI 10 AVRIL 2026 — Compte 101573422" % len(all_closed))
print(SEP)
print("%4s | %-12s | %-5s | %5s | %8s | %8s | %8s | %10s | %10s | %8s | %6s | %-7s | %-8s" % (
    "#", "SYMBOLE", "TYPE", "VOL", "ENTRÉE", "SORTIE", "DURÉE", "PRIX IN", "PRIX OUT", "PnL($)", "PIPS", "MARCHÉ", "SESSION"))
print(LINE)

total_pnl = 0
wins = 0
losses = 0
bes = 0

for i, c in enumerate(all_closed, 1):
    e = c["entry"]
    x = c["exit"]
    p = c["pnl"]
    s = c["symbol"]
    d_sec = t2s(x["time"]) - t2s(e["time"])
    
    if s in ["XAUUSD", "GOLD"]:
        pips = abs(x["price"] - e["price"]) * 10
    elif s == "USDJPY":
        pips = abs(x["price"] - e["price"]) * 100
    else:
        pips = abs(x["price"] - e["price"])
    
    tr = trend(e["price"], x["price"])
    se = sess(e["time"])
    total_pnl += p
    
    if p > 0:
        tag = " WIN"
        wins += 1
    elif p < 0:
        tag = " LOSS"
        losses += 1
    else:
        tag = " BE"
        bes += 1
    
    sym_short = s if len(s) <= 12 else s[:11] + "."
    
    print("%4d | %-12s | %-5s | %5.2f | %8s | %8s | %8s | %10.2f | %10.2f | %+8.2f | %5.1fp | %-7s | %-8s%s" % (
        i, sym_short, e["side"], e["volume"], e["time"], x["time"], dur(d_sec),
        e["price"], x["price"], p, pips, tr, se, tag))

print(LINE)
wr = wins / len(all_closed) * 100 if all_closed else 0
print("TOTAL: %d positions | Gagnants: %d | Perdants: %d | BE: %d | WR: %.1f%% | PnL: $%+.2f" % (
    len(all_closed), wins, losses, bes, wr, total_pnl))
print()

if all_open:
    print("POSITIONS ENCORE OUVERTES (%d):" % len(all_open))
    for j, p in enumerate(all_open, 1):
        sym = p["symbol"] if len(p["symbol"]) <= 12 else p["symbol"][:11] + "."
        print("  %d. %-12s | %-5s | %.2f | %s | @ %.2f | order #%s" % (
            j, sym, p["side"], p["volume"], p["time"], p["price"], p["order"]))
    print()
print(SEP)
