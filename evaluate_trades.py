#!/usr/bin/env python3
import os
from datetime import datetime
from collections import defaultdict

MT5PATH = os.path.expanduser("~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
RED="\033[91m"; GREEN="\033[92m"; YELLOW="\033[93m"; CYAN="\033[96m"; BOLD="\033[1m"; RESET="\033[0m"

def parse_exit_csv(path):
    trades = []; seen = set()
    with open(path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 5: continue
            ticket = parts[0].strip()
            try:
                ticket_int = int(ticket)
            except:
                continue
            if ticket_int < 1000000: continue
            try:
                pnl = float(parts[4].strip())
                price = float(parts[3].strip())
            except:
                continue
            timestr = parts[1].strip()
            symbol = parts[2].strip()
            reason = parts[5].strip() if len(parts) > 5 else ""
            key = (ticket, timestr, symbol, pnl)
            if key in seen: continue
            seen.add(key)
            try:
                dt = datetime.strptime(timestr, "%Y.%m.%d %H:%M")
            except:
                try:
                    dt = datetime.strptime(timestr, "%Y.%m.%d %H:%M:%S")
                except:
                    continue
            trades.append({"ticket":ticket,"time":dt,"symbol":symbol,"pnl":pnl,"reason":reason,"hour":dt.hour,"date":dt.strftime("%Y-%m-%d")})
    return sorted(trades, key=lambda x: x["time"])

def run_report(trades):
    print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"{BOLD}{CYAN}   ALADDIN V7 — RAPPORT REEL (tickets 2026 uniquement){RESET}")
    print(f"{BOLD}{CYAN}{'='*65}{RESET}\n")
    if not trades:
        print(f"{RED}Aucun trade Aladdin V7 trouve.{RESET}"); return
    total = len(trades)
    winners = [t for t in trades if t["pnl"] > 0]
    losers  = [t for t in trades if t["pnl"] < 0]
    bes     = [t for t in trades if t["pnl"] == 0]
    total_pnl = sum(t["pnl"] for t in trades)
    gross_win = sum(t["pnl"] for t in winners)
    gross_loss= sum(t["pnl"] for t in losers)
    wr = len(winners)/total*100
    avg_win  = gross_win/len(winners) if winners else 0
    avg_loss = gross_loss/len(losers) if losers else 0
    pf = abs(gross_win/gross_loss) if gross_loss != 0 else float("inf")
    col = GREEN if total_pnl >= 0 else RED
    print(f"{BOLD}RESUME GLOBAL{RESET}")
    print(f"  Trades     : {BOLD}{total}{RESET}  |  Gagnants: {GREEN}{len(winners)}{RESET} ({wr:.1f}%)  |  Perdants: {RED}{len(losers)}{RESET}  |  BE: {YELLOW}{len(bes)}{RESET}")
    print(f"  PnL net    : {col}{BOLD}${total_pnl:+.2f}{RESET}")
    print(f"  Gain brut  : {GREEN}${gross_win:+.2f}{RESET}  |  Gain moy: {GREEN}${avg_win:.2f}{RESET}")
    print(f"  Perte brute: {RED}${gross_loss:+.2f}{RESET}  |  Perte moy: {RED}${avg_loss:.2f}{RESET}")
    print(f"  Profit Factor: {BOLD}{pf:.2f}{RESET}")
    print(f"\n{BOLD}PAR SYMBOLE{RESET}")
    by_sym = defaultdict(list)
    for t in trades: by_sym[t["symbol"]].append(t)
    for sym in sorted(by_sym):
        st=by_sym[sym]; spnl=sum(t["pnl"] for t in st)
        sw=len([t for t in st if t["pnl"]>0]); swr=sw/len(st)*100
        col=GREEN if spnl>=0 else RED
        print(f"  {BOLD}{sym:<10}{RESET} {len(st):>3} trades | WR:{swr:>5.1f}% | PnL:{col}${spnl:+.2f}{RESET}")
    print(f"\n{BOLD}PAR JOUR{RESET}")
    by_day = defaultdict(list)
    for t in trades: by_day[t["date"]].append(t)
    for day in sorted(by_day):
        dt=by_day[day]; dpnl=sum(t["pnl"] for t in dt)
        dw=len([t for t in dt if t["pnl"]>0]); dwr=dw/len(dt)*100
        col=GREEN if dpnl>=0 else RED
        print(f"  {day}  {len(dt):>3} trades | WR:{dwr:>5.1f}% | PnL:{col}${dpnl:+.2f}{RESET}")
    print(f"\n{BOLD}PNL PAR HEURE{RESET}")
    by_hour = defaultdict(list)
    for t in trades: by_hour[t["hour"]].append(t)
    for h in sorted(by_hour):
        ht=by_hour[h]; hpnl=sum(t["pnl"] for t in ht)
        col=GREEN if hpnl>=0 else RED
        bar=("+" if hpnl>=0 else "-")*min(int(abs(hpnl)),25)
        print(f"  {h:02d}h {len(ht):>3} trades | {col}{bar} ${hpnl:+.2f}{RESET}")
    sl_t=[t for t in trades if "sl" in t["reason"].lower()]
    tp_t=[t for t in trades if "tp" in t["reason"].lower()]
    be_saved=[t for t in sl_t if t["pnl"]>=0]
    print(f"\n{BOLD}RAISONS SORTIE{RESET}")
    print(f"  SL: {RED}{len(sl_t)}{RESET} trades ${sum(t['pnl'] for t in sl_t):+.2f}  |  TP: {GREEN}{len(tp_t)}{RESET} trades ${sum(t['pnl'] for t in tp_t):+.2f}  |  BE sauves: {GREEN}{len(be_saved)}{RESET}")
    gold=[t for t in trades if t["symbol"]=="XAUUSD"]
    if gold:
        gn=[t for t in gold if t["hour"]<7 or t["hour"]>=23]
        gd=[t for t in gold if 7<=t["hour"]<23]
        pn=sum(t["pnl"] for t in gn); pd=sum(t["pnl"] for t in gd)
        print(f"\n{BOLD}XAUUSD NUIT vs JOUR{RESET}")
        print(f"  Nuit (23h-07h): {len(gn):>3} trades | PnL:{RED if pn<0 else GREEN}${pn:+.2f}{RESET} {'<= V7.13 devrait bloquer' if gn else ''}")
        print(f"  Jour (07h-23h): {len(gd):>3} trades | PnL:{RED if pd<0 else GREEN}${pd:+.2f}{RESET}")
    sorted_t=sorted(trades,key=lambda x:x["pnl"],reverse=True)
    print(f"\n{BOLD}TOP 5 MEILLEURS{RESET}")
    for t in sorted_t[:5]:
        print(f"  {GREEN}${t['pnl']:+.2f}{RESET} | {t['symbol']} | {t['time'].strftime('%m/%d %H:%M')} | {t['reason']}")
    print(f"\n{BOLD}TOP 5 PIRES{RESET}")
    for t in sorted_t[-5:]:
        print(f"  {RED}${t['pnl']:+.2f}{RESET} | {t['symbol']} | {t['time'].strftime('%m/%d %H:%M')} | {t['reason']}")
    print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"  {total} trades | {trades[0]['time'].strftime('%d/%m %H:%M')} -> {trades[-1]['time'].strftime('%d/%m %H:%M')}")
    print(f"{BOLD}{CYAN}{'='*65}{RESET}\n")

if __name__ == "__main__":
    exit_path = os.path.join(os.path.expanduser(MT5PATH), "aladdin_bb_exit.csv")
    print(f"\n{CYAN}Lecture: {exit_path}{RESET}")
    trades = parse_exit_csv(exit_path)
    run_report(trades)
