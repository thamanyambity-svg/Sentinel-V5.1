#!/usr/bin/env python3
# =============================================================
# Aladdin Pro — Analyse réelle depuis aladdin_bb_exit.csv
# Filtre uniquement les trades 2026 (tickets longs = Aladdin V7)
# =============================================================

import os, csv
from datetime import datetime
from collections import defaultdict

MT5PATH = os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
)

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def parse_exit_csv(path):
    trades = []
    seen   = set()
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = line.split("\t")
            if len(parts) < 5: continue
            ticket  = parts[0].strip()
            timestr = parts[1].strip()
            symbol  = parts[2].strip()
            try:
                price  = float(parts[3].strip())
                pnl    = float(parts[4].strip())
            except:
                continue
            reason = parts[5].strip() if len(parts) > 5 else ""

            # Dédupliquer
            key = (ticket, timestr, symbol, pnl)
            if key in seen: continue
            seen.add(key)

            # Filtrer uniquement Aladdin V7 2026
            # Tickets courts < 10000 = ancien bot 2024
            try:
                ticket_int = int(ticket)
            except:
                continue
            if ticket_int < 1000000: continue

            try:
                dt = datetime.strptime(timestr, "%Y.%m.%d %H:%M")
            except:
                try:
                    dt = datetime.strptime(timestr, "%Y.%m.%d %H:%M:%S")
                except:
                    continue

            trades.append({
                "ticket": ticket,
                "time":   dt,
                "symbol": symbol,
                "price":  price,
                "pnl":    pnl,
                "reason": reason,
                "hour":   dt.hour,
                "date":   dt.strftime("%Y-%m-%d"),
            })

    return sorted(trades, key=lambda x: x["time"])

def run_report(trades):
    print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"{BOLD}{CYAN}   ALADDIN V7 — RAPPORT REEL (12/12/2026 -> 17/03/2026){RESET}")
    print(f"{BOLD}{CYAN}{'='*65}{RESET}\n")

    if not trades:
        print(f"{RED}Aucun trade Aladdin V7 trouve.{RESET}")
        return

    total      = len(trades)
    winners    = [t for t in trades if t["pnl"] > 0]
    losers     = [t for t in trades if t["pnl"] < 0]
    breakevens = [t for t in trades if t["pnl"] == 0]
    total_pnl  = sum(t["pnl"] for t in trades)
    gross_win  = sum(t["pnl"] for t in winners)
    gross_loss = sum(t["pnl"] for t in losers)
    win_rate   = len(winners) / total * 100
    avg_win    = gross_win  / len(winners) if winners else 0
    avg_loss   = gross_loss / len(losers)  if losers  else 0
    pf         = abs(gross_win / gross_loss) if gross_loss != 0 else float("inf")

    pnl_col = GREEN if total_pnl >= 0 else RED
    print(f"{BOLD}RESUME GLOBAL{RESET}")
    print(f"  Trades total    : {BOLD}{total}{RESET}")
    print(f"  Gagnants        : {GREEN}{len(winners)}{RESET} ({win_rate:.1f}%)")
    print(f"  Perdants        : {RED}{len(losers)}{RESET}")
    print(f"  Break-even      : {YELLOW}{len(breakevens)}{RESET}")
    print(f"  PnL net         : {pnl_col}{BOLD}${total_pnl:+.2f}{RESET}")
    print(f"  Gain brut       : {GREEN}${gross_win:+.2f}{RESET}")
    print(f"  Perte brute     : {RED}${gross_loss:+.2f}{RESET}")
    print(f"  Gain moyen      : {GREEN}${avg_win:.2f}{RESET}")
    print(f"  Perte moyenne   : {RED}${avg_loss:.2f}{RESET}")
    print(f"  Profit Factor   : {BOLD}{pf:.2f}{RESET}")

    # Par symbole
    print(f"\n{BOLD}PAR SYMBOLE{RESET}")
    by_sym = defaultdict(list)
    for t in trades: by_sym[t["symbol"]].append(t)
    for sym in sorted(by_sym):
        st   = by_sym[sym]
        spnl = sum(t["pnl"] for t in st)
        sw   = len([t for t in st if t["pnl"] > 0])
        swr  = sw / len(st) * 100
        col  = GREEN if spnl >= 0 else RED
        print(f"  {BOLD}{sym:<10}{RESET} {len(st):>3} trades | "
              f"WR:{swr:>5.1f}% | PnL:{col}${spnl:+.2f}{RESET}")

    # Par jour
    print(f"\n{BOLD}PAR JOUR{RESET}")
    by_day = defaultdict(list)
    for t in trades: by_day[t["date"]].append(t)
    for day in sorted(by_day):
        dt   = by_day[day]
        dpnl = sum(t["pnl"] for t in dt)
        dw   = len([t for t in dt if t["pnl"] > 0])
        dwr  = dw / len(dt) * 100
        col  = GREEN if dpnl >= 0 else RED
        print(f"  {day}  {len(dt):>3} trades | "
              f"WR:{dwr:>5.1f}% | PnL:{col}${dpnl:+.2f}{RESET}")

    # Par heure
    print(f"\n{BOLD}PNL PAR HEURE (broker time){RESET}")
    by_hour = defaultdict(list)
    for t in trades: by_hour[t["hour"]].append(t)
    for h in sorted(by_hour):
        ht   = by_hour[h]
        hpnl = sum(t["pnl"] for t in ht)
        col  = GREEN if hpnl >= 0 else RED
        bar  = "+" * min(int(abs(hpnl)), 20) if hpnl >= 0 else "-" * min(int(abs(hpnl)), 20)
        print(f"  {h:02d}h  {len(ht):>3} trades | {col}{bar} ${hpnl:+.2f}{RESET}")

    # Raisons sortie
    print(f"\n{BOLD}RAISONS DE SORTIE{RESET}")
    sl_trades = [t for t in trades if "sl" in t["reason"].lower()]
    tp_trades = [t for t in trades if "tp" in t["reason"].lower()]
    sl_pnl = sum(t["pnl"] for t in sl_trades)
    tp_pnl = sum(t["pnl"] for t in tp_trades)
    be_saved = [t for t in sl_trades if t["pnl"] >= 0]
    print(f"  SL touche  : {RED}{len(sl_trades):>3}{RESET} trades | PnL:{RED}${sl_pnl:+.2f}{RESET}")
    print(f"  TP touche  : {GREEN}{len(tp_trades):>3}{RESET} trades | PnL:{GREEN}${tp_pnl:+.2f}{RESET}")
    print(f"  BE sauves  : {GREEN}{len(be_saved):>3}{RESET} trades (SL au BE = pas de perte) OK")

    # Top 5 gains
    sorted_t = sorted(trades, key=lambda x: x["pnl"], reverse=True)
    print(f"\n{BOLD}TOP 5 MEILLEURS{RESET}")
    for t in sorted_t[:5]:
        print(f"  {GREEN}${t['pnl']:+.2f}{RESET} | {t['symbol']} | "
              f"{t['time'].strftime('%m/%d %H:%M')} | {t['reason']}")

    print(f"\n{BOLD}TOP 5 PIRES{RESET}")
    for t in sorted_t[-5:]:
        print(f"  {RED}${t['pnl']:+.2f}{RESET} | {t['symbol']} | "
              f"{t['time'].strftime('%m/%d %H:%M')} | {t['reason']}")

    # XAUUSD nuit vs jour
    gold = [t for t in trades if t["symbol"] == "XAUUSD"]
    if gold:
        gold_night = [t for t in gold if t["hour"] < 7 or t["hour"] >= 23]
        gold_day   = [t for t in gold if 7 <= t["hour"] < 23]
        pnl_night  = sum(t["pnl"] for t in gold_night)
        pnl_day    = sum(t["pnl"] for t in gold_day)
        print(f"\n{BOLD}XAUUSD — NUIT vs JOUR{RESET}")
        print(f"  Nuit (23h-07h) : {len(gold_night):>3} trades | "
              f"PnL:{RED if pnl_night < 0 else GREEN}${pnl_night:+.2f}{RESET}")
        print(f"  Jour (07h-23h) : {len(gold_day):>3} trades | "
              f"PnL:{RED if pnl_day < 0 else GREEN}${pnl_day:+.2f}{RESET}")
        if gold_night:
            print(f"  {YELLOW}ATTENTION : {len(gold_night)} trades nocturnes encore presents{RESET}")
            print(f"  {YELLOW}=> V7.13 filtre horaire pas actif pendant ces trades{RESET}")

    # Recommandations
    print(f"\n{BOLD}RECOMMANDATIONS{RESET}")
    if pf < 1.0:
        print(f"  {RED}-> Profit Factor < 1 — pertes > gains{RESET}")
    if win_rate < 45:
        print(f"  {YELLOW}-> WR {win_rate:.1f}% — entrees a revoir{RESET}")
    if len(be_saved) > 0:
        print(f"  {GREEN}-> Break-Even a protege {len(be_saved)} trades{RESET}")
    if pf >= 1.0:
        print(f"  {GREEN}-> Profit Factor positif — continuer Phase A++{RESET}")
    print(f"  {CYAN}-> Balance actuelle: verifier status.json{RESET}")

    print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"  {total} trades | "
          f"{trades[0]['time'].strftime('%d/%m %H:%M')} -> "
          f"{trades[-1]['time'].strftime('%d/%m %H:%M')}")
    print(f"{BOLD}{CYAN}{'='*65}{RESET}\n")

if __name__ == "__main__":
    exit_path = os.path.join(MT5PATH, "aladdin_bb_exit.csv")
    if not os.path.exists(exit_path):
        print(f"{RED}Fichier non trouve : {exit_path}{RESET}")
    else:
        print(f"\n{CYAN}Lecture de {exit_path}{RESET}")
        trades = parse_exit_csv(exit_path)
        run_report(trades)
