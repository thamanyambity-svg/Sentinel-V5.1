#!/usr/bin/env python3
"""
Rapport filtré par plage horaire
Usage : python report_range.py --from "2026-03-08 21:00" --to "2026-03-09 08:00" --tz UTC+1
"""
import json, sys, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR  = Path(__file__).parent
TRADES_DB = BASE_DIR / "trades_learning.json"
MT5_FILES = Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"

# ── Couleurs terminal ──────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
B = "\033[94m"; W = "\033[97m"; X = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"

def pnl_c(v): return G if v>0 else (R if v<0 else Y)

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="date_from", default="2026-03-08 21:00",
                   help="Début (heure locale) ex: '2026-03-08 21:00'")
    p.add_argument("--to",   dest="date_to",   default="2026-03-09 08:00",
                   help="Fin   (heure locale) ex: '2026-03-09 08:00'")
    p.add_argument("--tz",   dest="tz_offset",  default="UTC+1",
                   help="Fuseau horaire ex: UTC+1 (Kinshasa)")
    return p.parse_args()

def parse_tz(tz_str: str) -> int:
    """Retourne l'offset en heures depuis UTC"""
    tz_str = tz_str.upper().replace("UTC","").strip()
    if not tz_str: return 0
    return int(tz_str)

def local_to_utc(dt_str: str, offset_h: int) -> datetime:
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    return dt - timedelta(hours=offset_h)

def load_trades():
    trades = []
    # 1. Charger la DB d'apprentissage
    if TRADES_DB.exists():
        try:
            db = json.loads(TRADES_DB.read_text())
            trades.extend(db.get("trades", []))
        except: pass
    
    # 2. Charger l'historique exporté par MT5
    hist_path = MT5_FILES / "trade_history.json"
    if hist_path.exists():
        try:
            content = hist_path.read_text()
            hist = json.loads(content)
            # Support both straight list or {"trades": [...]}
            hist_list = hist.get("trades", []) if isinstance(hist, dict) else hist
            if not isinstance(hist_list, list): hist_list = []
            
            existing = {str(t.get("ticket")) for t in trades}
            for t in hist_list:
                if str(t.get("ticket")) not in existing:
                    trades.append(t)
        except: pass
    return trades

def filter_trades(trades, utc_from: datetime, utc_to: datetime):
    result = []
    for t in trades:
        # Chercher un timestamp de clôture
        ts = t.get("time_close") or t.get("closed_at") or t.get("collected_at") or t.get("close_time")
        if not ts: continue
        
        try:
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
            else:
                dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        except:
            try:
                dt = datetime.strptime(str(ts)[:19], "%Y.%m.%d %H:%M:%S")
            except: continue
            
        if utc_from <= dt <= utc_to:
            result.append(t)
    return result

def render(trades, date_from, date_to, tz_label):
    total = len(trades)
    wins  = [t for t in trades if float(t.get("profit", t.get("pnl", 0))) > 0]
    losses= [t for t in trades if float(t.get("profit", t.get("pnl", 0))) < 0]
    pnl   = sum(float(t.get("profit", t.get("pnl", 0))) for t in trades)

    avg_win  = sum(float(t.get("profit",t.get("pnl",0))) for t in wins)  / len(wins)  if wins   else 0
    avg_loss = abs(sum(float(t.get("profit",t.get("pnl",0))) for t in losses) / len(losses)) if losses else 0
    wr       = round(len(wins)/total*100, 1) if total else 0
    rr       = round(avg_win/avg_loss, 2) if avg_loss else 0
    pf_gross = sum(float(t.get("profit",t.get("pnl",0))) for t in wins)
    pf_loss  = abs(sum(float(t.get("profit",t.get("pnl",0))) for t in losses))
    pf       = round(pf_gross/pf_loss, 2) if pf_loss else 0

    # Par instrument
    by_sym = {}
    for t in trades:
        sym = t.get("symbol","?").upper()
        p   = float(t.get("profit", t.get("pnl", 0)))
        if sym not in by_sym: by_sym[sym] = {"trades":0,"wins":0,"pnl":0.0}
        by_sym[sym]["trades"] += 1
        by_sym[sym]["pnl"]    += p
        if p > 0: by_sym[sym]["wins"] += 1

    W60 = "═" * 62
    print(f"\n{BOLD}{B}╔{W60}╗{X}")
    print(f"{BOLD}{B}║{'  📊 RAPPORT DÉTAILLÉ':^62}║{X}")
    print(f"{BOLD}{B}║{f'  {date_from} → {date_to} ({tz_label})':^62}║{X}")
    print(f"{BOLD}{B}╚{W60}╝{X}\n")

    if total == 0:
        print(f"  {Y}Aucun trade fermé sur cette plage horaire.{X}")
        print(f"  {DIM}Vérifier que trade_history.json est à jour.{X}\n")
        return

    # ── Résumé global ──────────────────────────────────────────────
    print(f"{BOLD}{W}📈 RÉSUMÉ GLOBAL{X}")
    print(f"  Période       : {date_from} → {date_to} ({tz_label})")
    print(f"  Total trades  : {BOLD}{total}{X}  ({G}{len(wins)} wins{X} / {R}{len(losses)} losses{X})")
    wr_c = G if wr>=55 else (Y if wr>=45 else R)
    print(f"  Win Rate      : {wr_c}{BOLD}{wr}%{X}")
    print(f"  P&L Total     : {pnl_c(pnl)}{BOLD}{pnl:+.2f}${X}")
    print(f"  R-R Moyen     : {G}{rr}{X}")
    print(f"  Profit Factor : {(G if pf>=1.5 else Y)}{pf}{X}")
    print(f"  Avg Win       : {G}+{avg_win:.2f}${X}  |  Avg Loss : {R}-{avg_loss:.2f}${X}")

    # ── Par instrument ─────────────────────────────────────────────
    print(f"\n{BOLD}{W}🎯 PAR INSTRUMENT{X}")
    for sym, d in sorted(by_sym.items(), key=lambda x: x[1]["pnl"], reverse=True):
        wr_s = round(d["wins"]/d["trades"]*100,1) if d["trades"] else 0
        c    = pnl_c(d["pnl"])
        wr_c = G if wr_s>=55 else (Y if wr_s>=45 else R)
        print(f"  {BOLD}{sym:<8}{X}  {d['trades']:>3} trades | WR: {wr_c}{wr_s:>5.1f}%{X} | P&L: {c}{d['pnl']:>+8.2f}${X}")

    # ── Tous les trades ────────────────────────────────────────────
    print(f"\n{BOLD}{W}📋 DÉTAIL TOUS LES TRADES{X}")
    print(f"  {'#':<4} {'Symbole':<8} {'Type':<6} {'Lot':<6} {'Entrée':<10} {'Sortie':<10} {'P&L':>8}")
    print(f"  {'─'*62}")
    for i, t in enumerate(trades, 1):
        p     = float(t.get("profit", t.get("pnl", 0)))
        c     = pnl_c(p)
        entry = t.get("price_open", t.get("entry", 0))
        exit_ = t.get("price_close", t.get("exit", 0))
        print(f"  {i:<4} {t.get('symbol','?'):<8} {t.get('type','?').upper():<6} "
              f"{float(t.get('volume',0)):<6.2f} {float(entry):<10.5f} {float(exit_):<10.5f} "
              f"{c}{p:>+8.2f}${X}")

    print(f"\n{DIM}{'─'*62}{X}\n")

def main():
    args = parse_args()
    tz_h = parse_tz(args.tz_offset)

    utc_from = local_to_utc(args.date_from, tz_h)
    utc_to   = local_to_utc(args.date_to,   tz_h)

    print(f"\n{DIM}Plage UTC : {utc_from.strftime('%Y-%m-%d %H:%M')} → {utc_to.strftime('%Y-%m-%d %H:%M')}{X}")

    trades  = load_trades()
    filtered = filter_trades(trades, utc_from, utc_to)

    render(filtered, args.date_from, args.date_to, args.tz_offset)

if __name__ == "__main__":
    main()
