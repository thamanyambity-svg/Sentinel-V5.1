#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V10 — daily_report.py                                      ║
║  Rapport quotidien automatique — 21h00 UTC (clôture NY)              ║
║                                                                      ║
║  Contenu :                                                           ║
║    • Performance globale (WR, P&L, R-R moyen)                        ║
║    • Analyse par instrument                                          ║
║    • Analyse par session (London / NY / Asia)                        ║
║    • Évolution du capital jour par jour                              ║
║                                                                      ║
║  Sorties :                                                           ║
║    • Terminal (couleurs ANSI)                                        ║
║    • Fichier PDF  → reports/report_YYYY-MM-DD.pdf                    ║
║    • Message Discord                                                 ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os, json, time, logging, threading, requests, math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("DailyReport")

# ── Chemins ──────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

MT5_FILES = Path(os.environ.get(
    "MT5_FILES_PATH",
    os.path.expanduser(
        "~/Library/Application Support/net.metaquotes.wine.metatrader5"
        "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
    )
))

TRADES_DB    = BASE_DIR / "trades_learning.json"
CAPITAL_DB   = BASE_DIR / "capital_history.json"

# ── Config ────────────────────────────────────────────────────────────
REPORT_HOUR_UTC = 21          # Heure d'envoi (21h00 UTC)
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
INITIAL_CAPITAL = 1090.49     # Capital initial Deriv-Demo

# ── Couleurs terminal ─────────────────────────────────────────────────
G  = "\033[92m"   # Vert
R  = "\033[91m"   # Rouge
Y  = "\033[93m"   # Jaune
B  = "\033[94m"   # Bleu
W  = "\033[97m"   # Blanc
DIM = "\033[2m"
X  = "\033[0m"    # Reset
BOLD = "\033[1m"


# ══════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════

def load_json(path: Path, default=None):
    try:
        if path.exists() and path.stat().st_size > 0:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.debug("load_json %s: %s", path.name, e)
    return default if default is not None else {}

def save_json(path: Path, data):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    tmp.replace(path)

def bar(value: float, max_val: float, width: int = 20, fill="█", empty="░") -> str:
    filled = int(round(value / max_val * width)) if max_val > 0 else 0
    filled = max(0, min(width, filled))
    return fill * filled + empty * (width - filled)

def pnl_color(v: float) -> str:
    if v > 0: return G
    if v < 0: return R
    return Y

def send_discord(msg: str, embed: Optional[Dict] = None):
    if not DISCORD_WEBHOOK:
        return
    try:
        payload = {"content": msg}
        if embed:
            payload["embeds"] = [embed]
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
    except Exception as e:
        log.debug("Discord error: %s", e)


# ══════════════════════════════════════════════════════════════════════
# COLLECTE DES DONNÉES
# ══════════════════════════════════════════════════════════════════════

class DataCollector:
    """Collecte et structure les données pour le rapport."""

    def collect(self) -> Dict:
        """Retourne toutes les données nécessaires au rapport."""
        trades   = self._load_trades()
        capital  = self._load_capital()
        status   = load_json(MT5_FILES / "status.json", {})

        return {
            "trades":        trades,
            "capital":       capital,
            "status":        status,
            "generated_at":  datetime.now(timezone.utc).isoformat(),
            "date":          datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

    def _load_trades(self) -> List[Dict]:
        """Charge tous les trades depuis trades_learning.json + trade_history.json."""
        trades = []

        # Source 1 : trades_learning.json (enrichi Python)
        db = load_json(TRADES_DB, {"trades": []})
        if isinstance(db, list):
            trades.extend(db)
        else:
            trades.extend(db.get("trades", []))

        # Source 2 : trade_history.json (export MQL5)
        hist = load_json(MT5_FILES / "trade_history.json", {"trades": []})
        if isinstance(hist, list):
            mql_trades = hist
        else:
            mql_trades = hist.get("trades", [])

        # Fusionner sans doublons
        existing_tickets = {str(t.get("ticket")) for t in trades}
        for t in mql_trades:
            if str(t.get("ticket")) not in existing_tickets:
                trades.append(t)

        return trades

    def _load_capital(self) -> List[Dict]:
        """Charge l'historique du capital."""
        db = load_json(CAPITAL_DB, {"history": []})
        history = db.get("history", [])

        # Ajouter le capital actuel depuis status.json
        status = load_json(MT5_FILES / "status.json", {})
        balance = float(status.get("balance", status.get("equity", 0)))
        if balance > 0:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            # Mettre à jour ou ajouter aujourd'hui
            updated = False
            for entry in history:
                if entry.get("date") == today:
                    entry["balance"] = balance
                    updated = True
                    break
            if not updated:
                history.append({
                    "date":    today,
                    "balance": balance,
                    "pnl":     balance - (history[-1]["balance"] if history else INITIAL_CAPITAL),
                })
            save_json(CAPITAL_DB, {"history": history})

        return history


# ══════════════════════════════════════════════════════════════════════
# ANALYSEUR
# ══════════════════════════════════════════════════════════════════════

class ReportAnalyzer:
    """Calcule toutes les métriques du rapport."""

    def analyze(self, data: Dict) -> Dict:
        trades  = data["trades"]
        capital = data["capital"]

        return {
            "global":     self._global_stats(trades),
            "by_symbol":  self._by_symbol(trades),
            "by_session": self._by_session(trades),
            "daily_pnl":  self._daily_pnl(trades, capital),
            "today":      self._today_stats(trades),
            "best_trade": self._best_trade(trades),
            "worst_trade":self._worst_trade(trades),
        }

    def _global_stats(self, trades: List[Dict]) -> Dict:
        if not trades:
            return {"total": 0}

        wins   = [t for t in trades if float(t.get("profit", t.get("pnl", 0))) > 0]
        losses = [t for t in trades if float(t.get("profit", t.get("pnl", 0))) < 0]
        total_pnl = sum(float(t.get("profit", t.get("pnl", 0))) for t in trades)

        avg_win  = sum(float(t.get("profit", t.get("pnl", 0))) for t in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(float(t.get("profit", t.get("pnl", 0))) for t in losses) / len(losses)) if losses else 0
        rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # Profit Factor
        gross_profit = sum(float(t.get("profit", t.get("pnl", 0))) for t in wins)
        gross_loss   = abs(sum(float(t.get("profit", t.get("pnl", 0))) for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Max Drawdown
        max_dd = self._max_drawdown(trades)

        return {
            "total":          len(trades),
            "wins":           len(wins),
            "losses":         len(losses),
            "win_rate":       round(len(wins) / len(trades) * 100, 1),
            "total_pnl":      round(total_pnl, 2),
            "avg_win":        round(avg_win, 2),
            "avg_loss":       round(avg_loss, 2),
            "rr_ratio":       round(rr_ratio, 2),
            "profit_factor":  round(profit_factor, 2),
            "max_drawdown":   round(max_dd, 2),
            "expectancy":     round((len(wins)/len(trades) * avg_win) - (len(losses)/len(trades) * avg_loss), 2) if trades else 0,
        }

    def _max_drawdown(self, trades: List[Dict]) -> float:
        """Calcule le drawdown maximum."""
        equity = INITIAL_CAPITAL
        peak   = equity
        max_dd = 0.0
        for t in sorted(trades, key=lambda x: x.get("collected_at", x.get("closed_at", ""))):
            pnl    = float(t.get("profit", t.get("pnl", 0)))
            equity += pnl
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _by_symbol(self, trades: List[Dict]) -> Dict:
        result = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
        for t in trades:
            sym = t.get("symbol", "?").upper()
            pnl = float(t.get("profit", t.get("pnl", 0)))
            result[sym]["trades"] += 1
            result[sym]["pnl"]    += pnl
            if pnl > 0:
                result[sym]["wins"] += 1

        for sym, d in result.items():
            d["win_rate"] = round(d["wins"] / d["trades"] * 100, 1) if d["trades"] > 0 else 0
            d["pnl"]      = round(d["pnl"], 2)

        return dict(sorted(result.items(), key=lambda x: x[1]["pnl"], reverse=True))

    def _by_session(self, trades: List[Dict]) -> Dict:
        sessions = {"LONDON": [], "NEW_YORK": [], "ASIA": [], "OFF": []}
        for t in trades:
            session = t.get("session", "OFF")
            if session not in sessions:
                session = "OFF"
            sessions[session].append(float(t.get("profit", t.get("pnl", 0))))

        result = {}
        for session, pnls in sessions.items():
            if not pnls:
                result[session] = {"trades": 0, "pnl": 0, "win_rate": 0}
                continue
            wins = sum(1 for p in pnls if p > 0)
            result[session] = {
                "trades":   len(pnls),
                "wins":     wins,
                "pnl":      round(sum(pnls), 2),
                "win_rate": round(wins / len(pnls) * 100, 1),
            }
        return result

    def _daily_pnl(self, trades: List[Dict], capital: List[Dict]) -> List[Dict]:
        """P&L par jour sur les 14 derniers jours."""
        daily = defaultdict(float)
        for t in trades:
            ts  = t.get("collected_at", t.get("closed_at", ""))
            pnl = float(t.get("profit", t.get("pnl", 0)))
            if ts:
                day = ts[:10]
                daily[day] += pnl

        # Compléter avec l'historique capital
        for entry in capital:
            day = entry.get("date", "")
            if day and day not in daily:
                daily[day] = entry.get("pnl", 0)

        # 14 derniers jours
        result = []
        for i in range(13, -1, -1):
            day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            result.append({
                "date": day,
                "pnl":  round(daily.get(day, 0), 2),
            })
        return result

    def _today_stats(self, trades: List[Dict]) -> Dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_trades = [
            t for t in trades
            if (t.get("collected_at", t.get("closed_at", "")) or "")[:10] == today
        ]
        pnl  = sum(float(t.get("profit", t.get("pnl", 0))) for t in today_trades)
        wins = sum(1 for t in today_trades if float(t.get("profit", t.get("pnl", 0))) > 0)
        return {
            "trades":   len(today_trades),
            "wins":     wins,
            "pnl":      round(pnl, 2),
            "win_rate": round(wins / len(today_trades) * 100, 1) if today_trades else 0,
        }

    def _best_trade(self, trades: List[Dict]) -> Optional[Dict]:
        if not trades:
            return None
        return max(trades, key=lambda t: float(t.get("profit", t.get("pnl", 0))))

    def _worst_trade(self, trades: List[Dict]) -> Optional[Dict]:
        if not trades:
            return None
        return min(trades, key=lambda t: float(t.get("profit", t.get("pnl", 0))))


# ══════════════════════════════════════════════════════════════════════
# GÉNÉRATEUR DE RAPPORT TERMINAL
# ══════════════════════════════════════════════════════════════════════

class TerminalReport:
    """Affiche le rapport en couleur dans le terminal."""

    def render(self, metrics: Dict, data: Dict):
        date = data.get("date", "?")
        g    = metrics["global"]
        today = metrics["today"]

        lines = []
        W60  = "═" * 60

        lines.append(f"\n{BOLD}{B}╔{W60}╗{X}")
        lines.append(f"{BOLD}{B}║{'  📊 RAPPORT QUOTIDIEN ALADDIN PRO':^60}║{X}")
        lines.append(f"{BOLD}{B}║{f'  {date} — Clôture NY 21h00 UTC':^60}║{X}")
        lines.append(f"{BOLD}{B}╚{W60}╝{X}\n")

        # ── Aujourd'hui ─────────────────────────────────────────────
        lines.append(f"{BOLD}{W}📅 AUJOURD'HUI{X}")
        c = pnl_color(today["pnl"])
        lines.append(f"  Trades : {today['trades']} | "
                     f"Wins : {G}{today['wins']}{X} | "
                     f"P&L : {c}{today['pnl']:+.2f}${X} | "
                     f"WR : {today['win_rate']}%")

        # ── Global ───────────────────────────────────────────────────
        lines.append(f"\n{BOLD}{W}📈 PERFORMANCE GLOBALE{X}")
        if g.get("total", 0) == 0:
            lines.append(f"  {DIM}Aucun trade enregistré encore.{X}")
        else:
            wr_color = G if g["win_rate"] >= 55 else (Y if g["win_rate"] >= 45 else R)
            pf_color = G if g["profit_factor"] >= 1.5 else (Y if g["profit_factor"] >= 1.0 else R)
            lines.append(f"  Total trades   : {BOLD}{g['total']}{X}")
            lines.append(f"  Win Rate       : {wr_color}{BOLD}{g['win_rate']}%{X}  "
                         f"{bar(g['win_rate'], 100)}")
            lines.append(f"  P&L Total      : {pnl_color(g['total_pnl'])}{BOLD}{g['total_pnl']:+.2f}${X}")
            lines.append(f"  Profit Factor  : {pf_color}{g['profit_factor']:.2f}{X}")
            lines.append(f"  R-R Moyen      : {G}{g['rr_ratio']:.2f}{X}")
            lines.append(f"  Espérance/trade: {pnl_color(g['expectancy'])}{g['expectancy']:+.2f}${X}")
            lines.append(f"  Max Drawdown   : {R}{g['max_drawdown']:.2f}${X}")
            lines.append(f"  Avg Win        : {G}+{g['avg_win']:.2f}${X}  |  "
                         f"Avg Loss : {R}-{g['avg_loss']:.2f}${X}")

        # ── Par Instrument ───────────────────────────────────────────
        lines.append(f"\n{BOLD}{W}🎯 PAR INSTRUMENT{X}")
        by_sym = metrics["by_symbol"]
        if not by_sym:
            lines.append(f"  {DIM}Aucune donnée.{X}")
        else:
            max_trades = max(d["trades"] for d in by_sym.values()) if by_sym else 1
            for sym, d in by_sym.items():
                c = pnl_color(d["pnl"])
                wr_c = G if d["win_rate"] >= 55 else (Y if d["win_rate"] >= 45 else R)
                lines.append(
                    f"  {BOLD}{sym:<8}{X} "
                    f"{bar(d['trades'], max_trades, 10)} "
                    f"{d['trades']:>3} trades | "
                    f"WR: {wr_c}{d['win_rate']:>5.1f}%{X} | "
                    f"P&L: {c}{d['pnl']:>+8.2f}${X}"
                )

        # ── Par Session ──────────────────────────────────────────────
        lines.append(f"\n{BOLD}{W}🕐 PAR SESSION{X}")
        session_order = ["LONDON", "NEW_YORK", "ASIA", "OFF"]
        session_emoji = {"LONDON": "🇬🇧", "NEW_YORK": "🇺🇸", "ASIA": "🌏", "OFF": "😴"}
        by_ses = metrics["by_session"]
        for ses in session_order:
            d = by_ses.get(ses, {"trades": 0, "pnl": 0, "win_rate": 0})
            if d["trades"] == 0:
                continue
            c = pnl_color(d["pnl"])
            emoji = session_emoji.get(ses, "")
            lines.append(
                f"  {emoji} {ses:<10} "
                f"{d['trades']:>3} trades | "
                f"WR: {d['win_rate']:>5.1f}% | "
                f"P&L: {c}{d['pnl']:>+8.2f}${X}"
            )

        # ── Évolution Capital ────────────────────────────────────────
        lines.append(f"\n{BOLD}{W}💰 ÉVOLUTION DU CAPITAL (14 jours){X}")
        daily = metrics["daily_pnl"]
        max_abs = max((abs(d["pnl"]) for d in daily), default=1) or 1
        for d in daily[-7:]:  # Derniers 7 jours
            pnl = d["pnl"]
            c   = pnl_color(pnl)
            b   = bar(abs(pnl), max_abs, 15, "█" if pnl >= 0 else "▓")
            lines.append(f"  {d['date']}  {b}  {c}{pnl:>+8.2f}${X}")

        # ── Meilleur / Pire trade ────────────────────────────────────
        best  = metrics.get("best_trade")
        worst = metrics.get("worst_trade")
        if best:
            bp = float(best.get("profit", best.get("pnl", 0)))
            lines.append(f"\n{BOLD}{W}🏆 MEILLEUR TRADE{X}  "
                         f"{best.get('symbol','?')} {best.get('type','').upper()} → "
                         f"{G}{bp:+.2f}${X}")
        if worst:
            wp = float(worst.get("profit", worst.get("pnl", 0)))
            lines.append(f"{BOLD}{W}💀 PIRE TRADE{X}     "
                         f"{worst.get('symbol','?')} {worst.get('type','').upper()} → "
                         f"{R}{wp:+.2f}${X}")

        lines.append(f"\n{DIM}{'─'*60}{X}\n")

        report = "\n".join(lines)
        print(report)
        return report


# ══════════════════════════════════════════════════════════════════════
# GÉNÉRATEUR PDF
# ══════════════════════════════════════════════════════════════════════

class PDFReport:
    """Génère un rapport PDF professionnel."""

    def render(self, metrics: Dict, data: Dict) -> Optional[Path]:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.colors import HexColor, black, white
            from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                            Table, TableStyle, HRFlowable)
            from reportlab.lib.units import cm
            from reportlab.lib import colors
        except ImportError:
            log.warning("reportlab non disponible — pip install reportlab")
            return None

        date     = data.get("date", datetime.now().strftime("%Y-%m-%d"))
        filename = REPORTS_DIR / f"report_{date}.pdf"
        g        = metrics["global"]
        today    = metrics["today"]

        doc = SimpleDocTemplate(str(filename), pagesize=A4,
                                topMargin=1.5*cm, bottomMargin=1.5*cm,
                                leftMargin=2*cm, rightMargin=2*cm)

        # Couleurs
        DARK    = HexColor("#1a1a2e")
        GOLD    = HexColor("#f0a500")
        GREEN   = HexColor("#00c853")
        RED_C   = HexColor("#d50000")
        LIGHT   = HexColor("#f5f5f5")
        MEDIUM  = HexColor("#e0e0e0")

        styles  = getSampleStyleSheet()
        story   = []

        def h1(txt):
            return Paragraph(f"<b>{txt}</b>",
                ParagraphStyle("h1", fontSize=18, textColor=GOLD,
                               spaceAfter=6, fontName="Helvetica-Bold"))

        def h2(txt):
            return Paragraph(f"<b>{txt}</b>",
                ParagraphStyle("h2", fontSize=12, textColor=DARK,
                               spaceAfter=4, fontName="Helvetica-Bold"))

        def body(txt, color=black):
            return Paragraph(txt,
                ParagraphStyle("body", fontSize=10, textColor=color,
                               spaceAfter=2, fontName="Helvetica"))

        def table_style(header_color=DARK):
            return TableStyle([
                ("BACKGROUND", (0,0), (-1,0), header_color),
                ("TEXTCOLOR",  (0,0), (-1,0), white),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",   (0,0), (-1,0), 10),
                ("ALIGN",      (0,0), (-1,-1), "CENTER"),
                ("ALIGN",      (0,1), (0,-1),  "LEFT"),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [LIGHT, MEDIUM]),
                ("FONTSIZE",   (0,1), (-1,-1), 9),
                ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
                ("TOPPADDING",    (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ])

        # ── En-tête ──────────────────────────────────────────────────
        story.append(h1(f"📊 Rapport Quotidien — AladdinPro V7"))
        story.append(body(f"Date : {date} | Clôture NY 21h00 UTC | "
                          f"Généré le {datetime.now().strftime('%H:%M:%S')}"))
        story.append(HRFlowable(width="100%", thickness=2, color=GOLD))
        story.append(Spacer(1, 0.3*cm))

        # ── Aujourd'hui ──────────────────────────────────────────────
        story.append(h2("📅 Performance du Jour"))
        td = [
            ["Trades", "Wins", "Losses", "P&L Jour", "Win Rate"],
            [today["trades"], today["wins"],
             today["trades"] - today["wins"],
             f"{today['pnl']:+.2f}$", f"{today['win_rate']}%"]
        ]
        t = Table(td, colWidths=[3*cm]*5)
        t.setStyle(table_style(GOLD))
        story.append(t)
        story.append(Spacer(1, 0.4*cm))

        # ── Global ───────────────────────────────────────────────────
        story.append(h2("📈 Performance Globale"))
        if g.get("total", 0) > 0:
            gd = [
                ["Métrique", "Valeur", "Métrique", "Valeur"],
                ["Total Trades",   g["total"],
                 "Win Rate",       f"{g['win_rate']}%"],
                ["P&L Total",      f"{g['total_pnl']:+.2f}$",
                 "Profit Factor",  f"{g['profit_factor']:.2f}"],
                ["R-R Moyen",      f"{g['rr_ratio']:.2f}",
                 "Espérance",      f"{g['expectancy']:+.2f}$"],
                ["Avg Win",        f"+{g['avg_win']:.2f}$",
                 "Avg Loss",       f"-{g['avg_loss']:.2f}$"],
                ["Max Drawdown",   f"{g['max_drawdown']:.2f}$",
                 "Wins / Losses",  f"{g['wins']} / {g['losses']}"],
            ]
            t = Table(gd, colWidths=[4.5*cm, 3*cm, 4.5*cm, 3*cm])
            t.setStyle(table_style())
            story.append(t)
        else:
            story.append(body("Aucun trade enregistré encore."))
        story.append(Spacer(1, 0.4*cm))

        # ── Par Instrument ───────────────────────────────────────────
        story.append(h2("🎯 Performance par Instrument"))
        by_sym = metrics["by_symbol"]
        if by_sym:
            sym_data = [["Instrument", "Trades", "Wins", "Win Rate", "P&L Total"]]
            for sym, d in by_sym.items():
                sym_data.append([
                    sym, d["trades"], d["wins"],
                    f"{d['win_rate']}%", f"{d['pnl']:+.2f}$"
                ])
            t = Table(sym_data, colWidths=[4*cm, 2.5*cm, 2.5*cm, 3*cm, 3*cm])
            t.setStyle(table_style())
            story.append(t)
        else:
            story.append(body("Aucune donnée par instrument."))
        story.append(Spacer(1, 0.4*cm))

        # ── Par Session ──────────────────────────────────────────────
        story.append(h2("🕐 Performance par Session"))
        by_ses = metrics["by_session"]
        ses_data = [["Session", "Trades", "Wins", "Win Rate", "P&L"]]
        for ses in ["LONDON", "NEW_YORK", "ASIA", "OFF"]:
            d = by_ses.get(ses, {"trades": 0, "wins": 0, "win_rate": 0, "pnl": 0})
            if d["trades"] > 0:
                ses_data.append([
                    ses, d["trades"], d.get("wins", 0),
                    f"{d['win_rate']}%", f"{d['pnl']:+.2f}$"
                ])
        if len(ses_data) > 1:
            t = Table(ses_data, colWidths=[4*cm, 2.5*cm, 2.5*cm, 3*cm, 3*cm])
            t.setStyle(table_style())
            story.append(t)
        story.append(Spacer(1, 0.4*cm))

        # ── Évolution Capital ────────────────────────────────────────
        story.append(h2("💰 Évolution P&L (14 jours)"))
        daily = metrics["daily_pnl"]
        cap_data = [["Date", "P&L Journalier", "Tendance"]]
        cumul = 0
        for d in daily:
            pnl   = d["pnl"]
            cumul += pnl
            trend = "▲" if pnl > 0 else ("▼" if pnl < 0 else "—")
            cap_data.append([d["date"], f"{pnl:+.2f}$", trend])
        t = Table(cap_data, colWidths=[5*cm, 5*cm, 5*cm])
        ts = table_style()
        # Colorier les P&L
        for i, d in enumerate(daily, 1):
            color = GREEN if d["pnl"] > 0 else (RED_C if d["pnl"] < 0 else colors.grey)
            ts.add("TEXTCOLOR", (1, i), (1, i), color)
        t.setStyle(ts)
        story.append(t)
        story.append(Spacer(1, 0.4*cm))

        # ── Meilleur / Pire ──────────────────────────────────────────
        best  = metrics.get("best_trade")
        worst = metrics.get("worst_trade")
        if best or worst:
            story.append(h2("🏆 Trades Remarquables"))
            if best:
                bp = float(best.get("profit", best.get("pnl", 0)))
                story.append(body(
                    f"🏆 Meilleur : {best.get('symbol','?')} "
                    f"{best.get('type','').upper()} → +{bp:.2f}$",
                    GREEN
                ))
            if worst:
                wp = float(worst.get("profit", worst.get("pnl", 0)))
                story.append(body(
                    f"💀 Pire : {worst.get('symbol','?')} "
                    f"{worst.get('type','').upper()} → {wp:.2f}$",
                    RED_C
                ))

        # ── Footer ────────────────────────────────────────────────────
        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=GOLD))
        story.append(body("AladdinPro V7 — Rapport généré automatiquement à 21h00 UTC",
                          colors.grey))

        doc.build(story)
        log.info("📄 PDF généré : %s", filename)
        return filename


# ══════════════════════════════════════════════════════════════════════
# RAPPORT DISCORD
# ══════════════════════════════════════════════════════════════════════

class DiscordReport:
    """Envoie un rapport formaté sur Discord."""

    def send(self, metrics: Dict, data: Dict, pdf_path: Optional[Path] = None):
        g     = metrics["global"]
        today = metrics["today"]
        date  = data.get("date", "?")

        # Emoji performance
        if g.get("total", 0) == 0:
            grade = "⏳"
        elif g["win_rate"] >= 60 and g["profit_factor"] >= 1.5:
            grade = "🔥"
        elif g["win_rate"] >= 50:
            grade = "✅"
        else:
            grade = "⚠️"

        # Message principal
        pnl_today_str = f"+${today['pnl']:.2f}" if today["pnl"] >= 0 else f"-${abs(today['pnl']):.2f}"

        embed = {
            "title": f"{grade} Rapport Quotidien — {date}",
            "color": 0x00c853 if g.get("total_pnl", 0) >= 0 else 0xd50000,
            "fields": [],
            "footer": {"text": "AladdinPro V7 • Rapport automatique 21h00 UTC"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Aujourd'hui
        embed["fields"].append({
            "name":   "📅 Aujourd'hui",
            "value":  (f"Trades: **{today['trades']}** | "
                       f"WR: **{today['win_rate']}%** | "
                       f"P&L: **{pnl_today_str}**"),
            "inline": False,
        })

        # Global
        if g.get("total", 0) > 0:
            pnl_str = f"+${g['total_pnl']:.2f}" if g["total_pnl"] >= 0 else f"-${abs(g['total_pnl']):.2f}"
            embed["fields"].append({
                "name":   "📈 Performance Globale",
                "value":  (f"```\n"
                           f"Total trades   : {g['total']}\n"
                           f"Win Rate       : {g['win_rate']}%\n"
                           f"P&L Total      : {pnl_str}\n"
                           f"Profit Factor  : {g['profit_factor']}\n"
                           f"R-R Moyen      : {g['rr_ratio']}\n"
                           f"Max Drawdown   : ${g['max_drawdown']:.2f}\n"
                           f"```"),
                "inline": False,
            })

            # Par instrument
            by_sym = metrics["by_symbol"]
            if by_sym:
                sym_lines = []
                for sym, d in list(by_sym.items())[:5]:
                    arrow = "📈" if d["pnl"] >= 0 else "📉"
                    sym_lines.append(
                        f"{arrow} **{sym}** — {d['trades']} trades | "
                        f"WR {d['win_rate']}% | P&L {d['pnl']:+.2f}$"
                    )
                embed["fields"].append({
                    "name":   "🎯 Par Instrument",
                    "value":  "\n".join(sym_lines),
                    "inline": False,
                })

            # Par session
            by_ses = metrics["by_session"]
            ses_lines = []
            emojis = {"LONDON": "🇬🇧", "NEW_YORK": "🇺🇸", "ASIA": "🌏"}
            for ses, emoji in emojis.items():
                d = by_ses.get(ses, {})
                if d.get("trades", 0) > 0:
                    ses_lines.append(
                        f"{emoji} {ses}: {d['trades']} trades | "
                        f"WR {d['win_rate']}% | {d['pnl']:+.2f}$"
                    )
            if ses_lines:
                embed["fields"].append({
                    "name":   "🕐 Par Session",
                    "value":  "\n".join(ses_lines),
                    "inline": False,
                })

        # P&L 7 jours
        daily = metrics["daily_pnl"][-7:]
        chart = ""
        for d in daily:
            arrow = "🟢" if d["pnl"] > 0 else ("🔴" if d["pnl"] < 0 else "⬜")
            chart += f"{arrow} `{d['date'][-5:]}` {d['pnl']:+.2f}$\n"
        if chart:
            embed["fields"].append({
                "name":   "💰 P&L 7 Derniers Jours",
                "value":  chart,
                "inline": False,
            })

        # Envoyer
        send_discord("", embed=embed)
        log.info("📱 Rapport Discord envoyé")


# ══════════════════════════════════════════════════════════════════════
# ORCHESTRATEUR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════

class DailyReportSystem:
    """Lance le rapport tous les jours à 21h00 UTC."""

    def __init__(self):
        self.collector = DataCollector()
        self.analyzer  = ReportAnalyzer()
        self.terminal  = TerminalReport()
        self.pdf       = PDFReport()
        self.discord   = DiscordReport()

    def generate_now(self):
        """Génère et envoie le rapport immédiatement."""
        log.info("📊 Génération du rapport...")
        data    = self.collector.collect()
        metrics = self.analyzer.analyze(data)

        # 1. Terminal
        self.terminal.render(metrics, data)

        # 2. PDF
        pdf_path = self.pdf.render(metrics, data)

        # 3. Discord
        self.discord.send(metrics, data, pdf_path)

        if pdf_path:
            log.info("✅ Rapport complet généré : %s", pdf_path)
        return metrics

    def start_scheduler(self):
        """Lance le planificateur automatique 21h UTC."""
        log.info("⏰ Planificateur démarré — rapport chaque jour à %dh00 UTC",
                 REPORT_HOUR_UTC)

        def _scheduler():
            while True:
                now = datetime.now(timezone.utc)
                # Prochain 21h00 UTC
                target = now.replace(
                    hour=REPORT_HOUR_UTC, minute=0, second=0, microsecond=0
                )
                if now >= target:
                    target += timedelta(days=1)

                wait_sec = (target - now).total_seconds()
                log.info("⏳ Prochain rapport dans %.0f minutes (à %s UTC)",
                         wait_sec / 60, target.strftime("%H:%M"))

                time.sleep(wait_sec)
                try:
                    self.generate_now()
                except Exception as e:
                    log.error("Erreur génération rapport: %s", e)

        t = threading.Thread(target=_scheduler, daemon=True, name="ReportScheduler")
        t.start()
        return t


# ══════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════

def main():
    import signal, argparse

    parser = argparse.ArgumentParser(description="AladdinPro Daily Report")
    parser.add_argument("--now",       action="store_true", help="Générer le rapport maintenant")
    parser.add_argument("--schedule",  action="store_true", help="Mode planificateur 21h UTC")
    args = parser.parse_args()

    system = DailyReportSystem()

    if args.now or not args.schedule:
        # Rapport immédiat
        system.generate_now()

    if args.schedule:
        # Planificateur continu
        t = system.start_scheduler()
        def _shutdown(sig, frame):
            log.info("Arrêt propre...")
            exit(0)
        signal.signal(signal.SIGINT,  _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
        t.join()


if __name__ == "__main__":
    main()
