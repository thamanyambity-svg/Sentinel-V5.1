"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V10 — dashboard.py                                         ║
║  Terminal dashboard temps réel (sans dépendance externe)             ║
║                                                                      ║
║  Affiche :                                                           ║
║    • Compte MT5 (balance, equity, positions)                         ║
║    • Statut ML & AutoTrainer                                         ║
║    • News filter (événements bloquants)                              ║
║    • Backtest summary (derniers résultats)                           ║
║    • Logs récents du bot                                             ║
║                                                                      ║
║  Usage:                                                              ║
║    python dashboard.py                  # rafraîchit toutes les 5s  ║
║    python dashboard.py --interval 10   # rafraîchit toutes les 10s  ║
║    python dashboard.py --once          # affiche 1 fois et quitte   ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import math
import argparse
import threading
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
import threading

# Simple cache system
class SimpleCache:
    def __init__(self):
        self._cache = {}
        self._lock = threading.RLock()
    
    def get(self, key: str, ttl: float = 8.0) -> Optional[dict]:
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if (time.time() - entry['ts']) < ttl:
                    return entry['data']
                del self._cache[key]
        return None
    
    def set(self, key: str, data: dict):
        with self._lock:
            self._cache[key] = {'data': data, 'ts': time.time()}

cache = SimpleCache()

from dashboard_manager import DashboardManager
global_manager = DashboardManager()
try:
    from discord_dashboard_report import send_dashboard_report
except ImportError:
    send_dashboard_report = None

# ══════════════════════════════════════════════════════════════════
#  CODES COULEURS ANSI (pas de dépendance externe)
# ══════════════════════════════════════════════════════════════════

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_DARK = "\033[48;5;235m"

def clr(text: str, *codes) -> str:
    return "".join(codes) + str(text) + C.RESET

def bold(t): return clr(t, C.BOLD)
def green(t): return clr(t, C.GREEN)
def red(t): return clr(t, C.RED)
def yellow(t): return clr(t, C.YELLOW)
def cyan(t): return clr(t, C.CYAN)
def dim(t): return clr(t, C.DIM)
def magenta(t): return clr(t, C.MAGENTA)

# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent
MT5_DIR = Path("/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files")

FILES = {
    "status":        MT5_DIR / "status.json",
    "ticks":         MT5_DIR / "ticks_v3.json",
    "news_block":    MT5_DIR / "news_block.json",
    "news_cache":    BASE_DIR / "news_cache.json",
    "backtest":      BASE_DIR / "backtest_summary.json",
    "training":      BASE_DIR / "training_history.json",
    "action_plan":   BASE_DIR / "action_plan.json",
    "fundamental":   BASE_DIR / "fundamental_state.json",
    "model_registry":BASE_DIR / "model_registry.json",
    "bot_log":       BASE_DIR / "bot.log",
    "bot_state":     BASE_DIR / "bot_state.json",
    "optimization":  BASE_DIR / "optimization_results.json",
    "performance":   MT5_DIR / "aladdin_performance.csv",
    "bb_entry":      MT5_DIR / "aladdin_bb_entry.csv",
    "bb_live":       MT5_DIR / "aladdin_bb_evolution.csv",
    "bb_exit":       MT5_DIR / "aladdin_bb_exit.csv",
}

WIDTH = 72  # largeur totale du dashboard


# ══════════════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════════════

def read_json(path: Path) -> Optional[dict]:
    key = f"json:{path}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    
    try:
        if path.exists() and path.stat().st_size > 0:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                cache.set(key, data)
                return data
    except Exception:
        pass
    return None


def read_last_lines(path: Path, n: int = 8) -> List[str]:
    key = f"log:{path}:{n}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    
    try:
        if not path.exists():
            return []
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            chunk = min(size, 8192)
            f.seek(-chunk, 2)
            raw = f.read().decode("utf-8", errors="replace")
        lines = [l for l in raw.splitlines() if l.strip()]
        result = lines[-n:]
        cache.set(key, result)
        return result
    except Exception:
        return []


def bar(val: float, max_val: float = 100.0, width: int = 20,
        fill: str = "█", empty: str = "░") -> str:
    ratio = max(0.0, min(1.0, val / max_val if max_val else 0))
    filled = int(ratio * width)
    return fill * filled + empty * (width - filled)


def fmt_age(ts_epoch: float) -> str:
    """Convertit un timestamp en âge lisible."""
    try:
        diff = time.time() - float(ts_epoch)
        if diff < 60:
            return f"{int(diff)}s"
        elif diff < 3600:
            return f"{int(diff/60)}m"
        else:
            return f"{int(diff/3600)}h{int((diff%3600)/60)}m"
    except Exception:
        return "?"


def sep(char: str = "─", label: str = "", width: int = WIDTH) -> str:
    if label:
        pad = width - len(label) - 4
        left = pad // 2
        right = pad - left
        return cyan("─" * left + f" {bold(label)} " + "─" * right)
    return dim("─" * width)


def box_top(label: str = "") -> str:
    inner = WIDTH - 2
    if label:
        pad = inner - len(label) - 2
        left = pad // 2
        right = pad - left
        return cyan("╔" + "═" * left + f" {bold(C.WHITE + label + C.CYAN)} " + "═" * right + "╗")
    return cyan("╔" + "═" * inner + "╗")


def box_bottom() -> str:
    return cyan("╚" + "═" * (WIDTH - 2) + "╝")


def box_row(content: str, width: int = WIDTH) -> str:
    # Retire les codes ANSI pour calculer la vraie longueur
    import re
    raw = re.sub(r'\033\[[0-9;]*m', '', content)
    pad = max(0, width - 2 - len(raw))
    return cyan("║") + " " + content + " " * pad + cyan("║")


# ══════════════════════════════════════════════════════════════════
#  SECTIONS DU DASHBOARD
# ══════════════════════════════════════════════════════════════════

def section_header() -> List[str]:
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    lines = [
        box_top("SENTINEL V10 — DASHBOARD LIVE"),
        box_row(f"  {cyan('🕐')} {bold(now)}   {dim('Rafraîchissement automatique')}"),
        box_row(""),
    ]
    return lines


def section_account() -> List[str]:
    lines = [box_row(sep(label="💰 COMPTE MT5"))]

    data = read_json(FILES["status"])
    if not data:
        lines.append(box_row(f"  {yellow('⚠️  status.json introuvable — EA non actif ou fichier absent')}"))
        return lines

    balance  = data.get("balance", 0)
    equity   = data.get("equity", 0)
    enabled  = data.get("trading", False)
    updated  = data.get("ts", 0)  # EA writes 'ts', not 'updated'
    positions = data.get("positions", [])

    pnl_open  = sum(p.get("pnl", p.get("profit", 0)) for p in positions)
    status_str = green("✅ ACTIF") if enabled else red("🔴 DÉSACTIVÉ")

    lines.append(box_row(f"  Balance  : {bold(f'${balance:,.2f}')}   Equity : {bold(f'${equity:,.2f}')}   ({fmt_age(updated)} ago)"))
    lines.append(box_row(f"  Trading  : {status_str}   PnL ouvert : {(green if pnl_open >= 0 else red)(f'${pnl_open:+.2f}')}   Sync: {dim(datetime.fromtimestamp(updated).strftime('%H:%M:%S') if updated else 'N/A')}"))

    if positions:
        lines.append(box_row(f"  {dim('─' * 60)}"))
        lines.append(box_row(f"  {bold('Positions ouvertes')} ({len(positions)}) :"))
        for p in positions[:5]:
            sym     = p.get("sym", p.get("symbol", "?"))    # EA writes 'sym'
            ptype   = p.get("type", "?")
            vol     = p.get("lot", p.get("volume", 0))       # EA writes 'lot'
            profit  = p.get("pnl", p.get("profit", 0))       # EA writes 'pnl'
            price   = p.get("price", p.get("sl", 0))
            pnl_col = green if profit >= 0 else red
            type_col = cyan if ptype == "BUY" else magenta
            lines.append(box_row(
                f"  {type_col(ptype):<4}  {bold(sym):<10}  {vol:.2f} lot  "
                f"@ {price:.5f}  PnL: {pnl_col(f'{profit:+.2f}')}"
            ))
        if len(positions) > 5:
            lines.append(box_row(f"  {dim(f'... et {len(positions)-5} autre(s)')}"))
    else:
        lines.append(box_row(f"  {dim('Aucune position ouverte')}"))

    return lines


def section_ticks() -> List[str]:
    lines = [box_row(sep(label="📊 PRIX EN TEMPS RÉEL"))]

    data = read_json(FILES["ticks"])
    if not data:
        lines.append(box_row(f"  {dim('ticks_v3.json introuvable')}"))
        return lines

    if isinstance(data, list):
        ticks = {item.get("sym", "?"): item.get("ask", 0) for item in data}
        eq = 0
        ts = time.time()
    else:
        ticks = data.get("ticks", {})
        ts    = data.get("t", 0)
        eq    = data.get("equity", 0)

    row = ""
    for sym, price in list(ticks.items())[:4]:
        row += f"  {bold(sym)}: {cyan(str(price))}"
    lines.append(box_row(row if row else dim("  Aucun tick")))
    if eq:
        lines.append(box_row(f"  Equity MT5 (tick): {bold(f'${eq:,.2f}')}   {dim(f'({fmt_age(ts)} ago)')}"))

    return lines


def section_news() -> List[str]:
    lines = [box_row(sep(label="📰 NEWS FILTER"))]

    data = read_json(FILES["news_block"])
    if not data:
        lines.append(box_row(f"  {yellow('⚠️  news_block.json introuvable — NewsFilter non démarré')}"))
        return lines

    blocked  = data.get("blocked", {})
    upcoming = data.get("upcoming_high", [])
    updated  = data.get("updated", "?")
    total    = data.get("total_loaded", 0)

    blocked_syms = []
    if isinstance(blocked, dict):
        blocked_syms = [s for s, v in blocked.items() if v.get("blocked")]
        
    status_str = (red(f"🔴 {len(blocked_syms)} instrument(s) BLOQUÉ(s)")
                  if blocked_syms else green("✅ Aucun blocage actif"))

    lines.append(box_row(f"  {status_str}   {dim(f'({total} événements chargés)')}"))

    if blocked_syms:
        for sym in blocked_syms[:3]:
            reason = blocked[sym].get("reason", "?")[:50]
            lines.append(box_row(f"  {red('⛔')} {bold(sym)}: {dim(reason)}"))

    if upcoming:
        lines.append(box_row(f"  {dim('─' * 60)}"))
        lines.append(box_row(f"  {bold('Prochaines HIGH')} (12h) :"))
        for ev in upcoming[:4]:
            title = ev.get("title", "?")[:32]
            mins  = ev.get("mins_until", 0)
            curr  = ev.get("currency", "?")
            dt_str = ev.get("dt", "?")
            urgency = red if mins < 30 else yellow if mins < 120 else dim
            lines.append(box_row(
                f"  {urgency('▶')} [{cyan(curr)}] {bold(title):<33}  dans {urgency(f'{mins:.0f}min')}"
            ))
    else:
        lines.append(box_row(f"  {dim('Aucune news HIGH dans les 12 prochaines heures')}"))

    return lines


def section_ml() -> List[str]:
    lines = [box_row(sep(label="🧠 ML & SOVEREIGN GOVERNOR"))]

    # Action Plan (dernier signal Sovereign)
    ap = read_json(FILES["action_plan"])
    if ap:
        decision   = ap.get("decision", "?")
        kelly      = ap.get("kelly_risk", 0)
        nexus_prob = ap.get("nexus_prob", 0)
        spm        = ap.get("spm_score", 0)
        reason     = ap.get("reasoning", "")[:55]
        ts         = ap.get("timestamp", "")[:16]
        asset      = ap.get("asset", "?")

        dec_col = green if decision not in ("IGNORE", "?") else yellow
        lines.append(box_row(
            f"  {bold('Dernier signal')} [{dim(ts)}]  Asset: {bold(asset)}"
        ))
        lines.append(box_row(
            f"  Décision: {dec_col(bold(decision))}   Kelly: {bold(f'{kelly:.2f}x')}   "
            f"Nexus P={bold(f'{nexus_prob:.2f}')}   SPM={bold(f'{spm:.2f}')}"
        ))
        lines.append(box_row(f"  {dim(reason)}"))
    else:
        lines.append(box_row(f"  {dim('action_plan.json introuvable')}"))

    # Training history (peut être une liste ou un dict avec clé "runs")
    th_raw = read_json(FILES["training"])
    if th_raw:
        runs = th_raw if isinstance(th_raw, list) else th_raw.get("runs", [])
        if runs:
            last = runs[-1]
            auc  = last.get("auc", last.get("accuracy", last.get("validation_accuracy", "?")))
            wr   = last.get("win_rate", last.get("success", "?"))
            date = last.get("ts", last.get("date", "?"))[:10]
            n    = len(runs)
            auc_col = green if isinstance(auc, float) and auc >= 0.6 else yellow
            lines.append(box_row(dim("─" * 60)))
            lines.append(box_row(
                f"  {bold('AutoTrainer')} — {n} session(s)   "
                f"Dernière: {dim(date)}   "
                f"AUC: {auc_col(bold(str(auc)))}   WR: {bold(str(wr))}"
            ))

    # Fundamental / FinBERT
    fund = read_json(FILES["fundamental"])
    if fund:
        mood  = fund.get("market_mood", "NEUTRAL")
        score = fund.get("spm_score", fund.get("aggregate_score", 0))
        mood_col = (green if "BULL" in str(mood).upper()
                    else red if "BEAR" in str(mood).upper()
                    else yellow)
        lines.append(box_row(
            f"  {bold('FinBERT')} → {mood_col(bold(mood))}   SPM Score: {bold(f'{score:.3f}')}"
        ))

    return lines


def section_backtest() -> List[str]:
    lines = [box_row(sep(label="📈 DERNIERS RÉSULTATS BACKTEST"))]

    data = read_json(FILES["backtest"])
    if not data:
        lines.append(box_row(f"  {dim('backtest_summary.json introuvable — lancez run_backtest_pipeline.sh')}"))
        return lines

    pf       = data.get("profit_factor", 0)
    wr       = data.get("win_rate", 0)
    dd       = data.get("max_drawdown_pct", 0)
    sharpe   = data.get("sharpe", 0)
    ret      = data.get("return_pct", 0)
    n        = data.get("n_trades", 0)
    gen      = data.get("generated", "?")[:16]
    wfe_val  = data.get("wfe", {}).get("wfe", 0) if isinstance(data.get("wfe"), dict) else 0

    pf_col  = green if pf >= 1.25 else red
    dd_col  = green if dd <= 20   else red
    sh_col  = green if sharpe >= 0.8 else yellow
    wfe_col = green if wfe_val >= 0.4 else yellow
    ret_col = green if ret > 0 else red

    lines.append(box_row(f"  {dim(f'Généré: {gen}')}  {dim(f'{n} trades analysés')}"))
    lines.append(box_row(
        f"  PF: {pf_col(bold(f'{pf:.3f}'))}  ({'✅' if pf >= 1.25 else '❌'})   "
        f"WR: {bold(f'{wr*100:.1f}%')}   DD: {dd_col(bold(f'{dd:.1f}%'))} ({'✅' if dd <= 20 else '❌'})"
    ))
    lines.append(box_row(
        f"  Sharpe: {sh_col(bold(f'{sharpe:.2f}'))}   WFE: {wfe_col(bold(f'{wfe_val:.3f}'))}   "
        f"Retour: {ret_col(bold(f'{ret:+.1f}%'))}"
    ))

    # Barre PF visuelle
    pf_bar = bar(min(pf, 2.0), 2.0, 30)
    pf_bar_col = green(pf_bar) if pf >= 1.25 else red(pf_bar)
    lines.append(box_row(f"  PF [{pf_bar_col}] {pf:.3f} / 2.0+"))

    return lines


def section_logs() -> List[str]:
    lines = [box_row(sep(label="📋 LOGS RÉCENTS (bot.log)"))]

    log_lines = read_last_lines(FILES["bot_log"], n=6)
    if not log_lines:
        lines.append(box_row(f"  {dim('bot.log vide ou introuvable')}"))
        return lines

    for line in log_lines:
        # Colorisation selon le niveau
        if "ERROR" in line or "CRITICAL" in line:
            display = red(line[:68])
        elif "WARN" in line or "WARNING" in line:
            display = yellow(line[:68])
        elif "EXEC" in line or "Trade" in line or "BUY" in line or "SELL" in line:
            display = cyan(line[:68])
        elif "INFO" in line:
            display = dim(line[:68])
        else:
            display = dim(line[:68])
        lines.append(box_row(f"  {display}"))

    return lines


def section_performance() -> List[str]:
    lines = [box_row(sep(label="💰 PERFORMANCE RÉELLE (ALADDIN V7)"))]
    
    # Use cached CSV loader (max 10 lines)
    try:
        from dashboard_manager import DashboardManager
        manager = DashboardManager()
        csv_data = manager.load_data("performance")
        
        if not csv_data or len(csv_data.get("rows", [])) <= 1:
            lines.append(box_row(f"  {dim('aladdin_performance.csv vide/introuvable')}"))
            return lines
        
        trades = csv_data["rows"][-4:]  # Last 4 trades
        for t_line in trades:
            cols = t_line.strip().split(",")
            if len(cols) < 5: continue
            t_time = cols[0][11:16] # HH:MM
            t_sym  = cols[1]
            t_type = cols[2]
            t_lot  = cols[3]
            t_conf = cols[9] if len(cols) > 9 else "?"
            
            type_col = green if t_type == "BUY" else red
            lines.append(box_row(
                f"  {dim(t_time)}  {bold(t_sym):<7} {type_col(bold(t_type)):<4} "
                f"Lot: {bold(t_lot)}   Conf: {yellow(bold(t_conf))}"
            ))
    except Exception as e:
        lines.append(box_row(f"  {red(f'Erreur performance: {e}')}"))
        
    return lines


def section_blackbox_live() -> List[str]:
    lines = [box_row(sep(label="📡 BLACKBOX : ÉVOLUTION LIVE"))]
    
    csv_data = global_manager.load_data("bb_live")
    if not csv_data or len(csv_data.get("rows", [])) <= 1:
        lines.append(box_row(f"  {dim('En attente de trades live...')}"))
        return lines
    
    # Parse last 3 rows (skip header)
    recent_trades = []
    for row in csv_data["rows"][-4:]:  # Extra for safety
        cols = row.strip().split(",")
        if len(cols) < 7: continue  # Ticket,Time,Sym,Price,PnL_Pts,PnL_Money,Equity
        
        try:
            ticket = cols[0]
            t_time = cols[1][11:19]  # HH:MM:SS
            sym = cols[2]
            pnl_pts = float(cols[4])
            pnl_money = float(cols[5])
            recent_trades.append((t_time, sym, pnl_money, pnl_pts, ticket))
        except (ValueError, IndexError):
            continue
    
    if not recent_trades:
        lines.append(box_row(f"  {dim('Aucun trade live récent')}"))
        return lines
    
    for t_time, sym, pnl_money, pnl_pts, ticket in recent_trades[:3]:
        pnl_col = green if pnl_money >= 0 else red
        lines.append(box_row(
            f"  {dim(t_time)} {bold(sym):<8} {pnl_col(bold(f'{pnl_money:+.1f}$'))} "
            f"({pnl_pts:+.1f}pts) {dim(f'T{ticket[-4:]}')}"
        ))
    
    return lines


def section_blackbox_reasoning() -> List[str]:
    lines = [box_row(sep(label="🧠 BLACKBOX : RAISONNEMENT (POURQUOI?)"))]
    
    # Last decisions from bb_entry
    csv_data = global_manager.load_data("bb_entry")
    if csv_data and len(csv_data.get("rows", [])) > 1:
        for row in csv_data["rows"][-3:]:
            cols = row.strip().split(",")
            if len(cols) < 13: continue
            try:
                t_time = cols[0][11:16]  # HH:MM
                sym = cols[1]
                type_ = cols[2]
                strats = cols[11][:20]  # Truncate
                rsi = cols[7]
                adx = cols[8]
                conf = cols[10]
                type_col = green if type_ == "BUY" else red
                lines.append(box_row(
                    f"  {dim(t_time)} {bold(sym)} {type_col(type_)}  "
                    f"{cyan(strats)}  RSI:{dim(rsi)} ADX:{dim(adx)} C:{conf}"
                ))
            except (ValueError, IndexError):
                continue
    
    # Last Sovereign reasoning from action_plan
    ap = global_manager.load_data("action_plan")
    if ap:
        decision = ap.get("decision", "?")
        reasoning = ap.get("reasoning", "")[:60]
        asset = ap.get("asset", "?")
        dec_col = green if decision in ("BUY", "SELL") else yellow
        lines.append(box_row(dim("─" * 60)))
        lines.append(box_row(
            f"  🧠 Sovereign [{bold(asset)}]: {dec_col(bold(decision))}  {dim(reasoning)}"
        ))
    
    if not csv_data and not ap:
        lines.append(box_row(f"  {dim('Aucune décision récente')}"))
    
    return lines


def section_footer(interval: int) -> List[str]:
    # Cache stats
    cache_hits = len([k for k,v in cache._cache.items() if (time.time() - v['ts']) < 8])
    discord_info = f" (Discord: {bold('ON')})" if "--discord" in str(sys.argv) else f" ({dim('--discord pour rapports')})"
    return [
        box_row(""),
        box_row(
            f"  {dim('Q: quitter    R: forcer refresh')}  "
            f"{dim(f'Ref: {interval}s')}  Cache: {bold(f'{cache_hits}/15')}  🚀"
            f"{discord_info}"
        ),
        box_bottom(),
        "",
    ]


# ══════════════════════════════════════════════════════════════════
#  RENDU COMPLET
# ══════════════════════════════════════════════════════════════════

def render(interval: int) -> str:
    sections = []
    sections += section_header()
    sections += section_account()
    sections += section_ticks()
    sections += section_news()
    sections += section_ml()
    sections += section_blackbox_live()
    sections += section_blackbox_reasoning()
    sections += section_performance()
    sections += section_backtest()
    sections += section_logs()
    sections += section_footer(interval)
    return "\n".join(sections)


def clear_screen():
    os.system("clear" if os.name != "nt" else "cls")


# ══════════════════════════════════════════════════════════════════
#  BOUCLE PRINCIPALE
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Sentinel V10 — Dashboard Live")
    parser.add_argument("--interval", type=int, default=10,
                        help="Intervalle de rafraîchissement en secondes (défaut: 10)")
    parser.add_argument("--once", action="store_true",
                        help="Affiche une fois et quitte")
    parser.add_argument("--discord", action="store_true",
                        help="Envoie un rapport à Discord périodiquement")
    parser.add_argument("--discord-interval", type=int, default=60,
                        help="Intervalle d'envoi à Discord en minutes (défaut: 60)")
    args = parser.parse_args()

    if args.once:
        print(render(args.interval))
        return

    # Boucle live
    stop_event = threading.Event()

    print(f"\n  {cyan('Sentinel V10 Dashboard')} — {dim('Ctrl+C pour quitter')}\n")
    time.sleep(0.5)

    last_discord_send = 0
    
    try:
        while not stop_event.is_set():
            # Gestion Discord périodique
            if args.discord and send_dashboard_report:
                if time.time() - last_discord_send >= (args.discord_interval * 60):
                    asyncio.run(send_dashboard_report())
                    last_discord_send = time.time()

            clear_screen()
            print(render(args.interval))
            # Attente interruptible
            for _ in range(args.interval * 10):
                if stop_event.is_set():
                    break
                time.sleep(0.1)
    except KeyboardInterrupt:
        clear_screen()
        print(f"\n  {yellow('Dashboard arrêté.')}  {dim('À bientôt !')}\n")


if __name__ == "__main__":
    main()
