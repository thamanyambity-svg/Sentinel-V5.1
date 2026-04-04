"""
╔══════════════════════════════════════════════════════════════════════╗
║  ALADDIN PRO V6 — backtest_analyzer.py                              ║
║                                                                      ║
║  Analyse complète des résultats de backtest MT5 Strategy Tester     ║
║                                                                      ║
║  Usage:                                                              ║
║    python backtest_analyzer.py --report trade_log_all.jsonl         ║
║    python backtest_analyzer.py --report trade_log_all.jsonl \\       ║
║                                --capital 1000 --plot                 ║
║    python backtest_analyzer.py --demo                                ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import math
import argparse
import statistics
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple


# ══════════════════════════════════════════════════════════════════
#  CHARGEMENT DES TRADES
# ══════════════════════════════════════════════════════════════════

def load_trades(path: str) -> List[dict]:
    trades = []
    p = Path(path)
    if not p.exists():
        print(f"  Fichier introuvable: {path}")
        return trades
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                trades.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # Trier chronologiquement
    trades.sort(key=lambda t: t.get("open_time", t.get("close_time", "")))
    return trades


# ══════════════════════════════════════════════════════════════════
#  MÉTRIQUES DE BACKTEST
# ══════════════════════════════════════════════════════════════════

class BacktestMetrics:

    def __init__(self, trades: List[dict], initial_capital: float = 1000.0):
        self.trades  = trades
        self.capital = initial_capital
        self._compute()

    def _compute(self):
        trades = self.trades
        n = len(trades)

        if n == 0:
            self._zero()
            return

        # PnL par trade (net_profit ou profit)
        pnls = [float(t.get("net_profit", t.get("profit", 0))) for t in trades]

        wins  = [p for p in pnls if p > 0]
        losses= [p for p in pnls if p <= 0]

        self.n_trades     = n
        self.n_wins       = len(wins)
        self.n_losses     = len(losses)
        self.win_rate     = len(wins) / n if n > 0 else 0
        self.total_profit = sum(pnls)
        self.gross_profit = sum(wins)
        self.gross_loss   = abs(sum(losses))
        self.profit_factor= self.gross_profit / self.gross_loss if self.gross_loss > 0 else float("inf")
        self.avg_win      = statistics.mean(wins)   if wins   else 0
        self.avg_loss     = abs(statistics.mean(losses)) if losses else 0
        self.expectancy   = statistics.mean(pnls) if pnls else 0

        # Courbe d'équité
        equity = [self.capital]
        for p in pnls:
            equity.append(equity[-1] + p)
        self.equity_curve = equity
        self.final_equity = equity[-1]
        self.return_pct   = (self.final_equity - self.capital) / self.capital * 100

        # Max Drawdown
        peak = equity[0]
        max_dd = 0.0
        max_dd_pct = 0.0
        for e in equity:
            if e > peak:
                peak = e
            dd = peak - e
            dd_pct = dd / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
        self.max_drawdown     = max_dd
        self.max_drawdown_pct = max_dd_pct

        # Sharpe Ratio (mensuel approximé)
        if len(pnls) > 1:
            std = statistics.stdev(pnls)
            self.sharpe = (self.expectancy / std * math.sqrt(252)) if std > 0 else 0
        else:
            self.sharpe = 0

        # Calmar Ratio
        annual_return = self.return_pct  # Approximation sur la période
        self.calmar   = annual_return / max_dd_pct if max_dd_pct > 0 else 0

        # Recovery Factor
        self.recovery_factor = self.total_profit / self.max_drawdown if self.max_drawdown > 0 else 0

        # Séries consécutives max
        self.max_consec_wins   = self._max_streak(pnls, win=True)
        self.max_consec_losses = self._max_streak(pnls, win=False)

        # Durée moyenne des trades
        durations = [int(t.get("duration_min", 0)) for t in trades if t.get("duration_min")]
        self.avg_duration_min = statistics.mean(durations) if durations else 0

        # Analyse temporelle
        self._by_symbol()
        self._by_session()
        self._monthly()

    def _zero(self):
        attrs = ["n_trades","n_wins","n_losses","win_rate","total_profit",
                 "gross_profit","gross_loss","profit_factor","avg_win","avg_loss",
                 "expectancy","final_equity","return_pct","max_drawdown",
                 "max_drawdown_pct","sharpe","calmar","recovery_factor",
                 "max_consec_wins","max_consec_losses","avg_duration_min"]
        for a in attrs:
            setattr(self, a, 0)
        self.equity_curve = [self.capital]

    def _max_streak(self, pnls: List[float], win: bool) -> int:
        max_s = cur_s = 0
        for p in pnls:
            is_win = p > 0
            if is_win == win:
                cur_s += 1
                max_s = max(max_s, cur_s)
            else:
                cur_s = 0
        return max_s

    def _by_symbol(self):
        """Stats par instrument."""
        by_sym: Dict[str, List[float]] = {}
        for t in self.trades:
            sym = t.get("symbol", "?")
            pnl = float(t.get("net_profit", t.get("profit", 0)))
            by_sym.setdefault(sym, []).append(pnl)
        self.by_symbol = {
            sym: {
                "n":      len(pnls),
                "pf":     sum(p for p in pnls if p > 0) / max(abs(sum(p for p in pnls if p <= 0)), 1e-10),
                "wr":     sum(1 for p in pnls if p > 0) / len(pnls),
                "total":  round(sum(pnls), 2),
            }
            for sym, pnls in by_sym.items()
        }

    def _by_session(self):
        """Stats par session de trading."""
        sessions = {"London": [], "NY": [], "Asia": [], "Overlap": []}
        for t in self.trades:
            pnl  = float(t.get("net_profit", t.get("profit", 0)))
            time_str = t.get("open_time", "")
            hour = 12  # Défaut
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M:%S"]:
                try:
                    hour = datetime.strptime(time_str, fmt).hour
                    break
                except ValueError:
                    pass

            if 13 <= hour < 16:
                sessions["Overlap"].append(pnl)
            elif 7 <= hour < 17:
                sessions["London"].append(pnl)
            elif 13 <= hour < 22:
                sessions["NY"].append(pnl)
            else:
                sessions["Asia"].append(pnl)

        self.by_session = {
            s: {
                "n":  len(pnls),
                "wr": sum(1 for p in pnls if p > 0) / len(pnls) if pnls else 0,
                "total": round(sum(pnls), 2),
            }
            for s, pnls in sessions.items() if pnls
        }

    def _monthly(self):
        """PnL mensuel."""
        monthly: Dict[str, float] = {}
        for t in self.trades:
            pnl = float(t.get("net_profit", t.get("profit", 0)))
            ts  = t.get("open_time", t.get("close_time", ""))
            month = ts[:7] if ts else "?"
            monthly[month] = monthly.get(month, 0) + pnl
        self.monthly_pnl = {k: round(v, 2) for k, v in sorted(monthly.items())}


# ══════════════════════════════════════════════════════════════════
#  WALK-FORWARD EFFICIENCY (WFE)
# ══════════════════════════════════════════════════════════════════

def compute_wfe(trades: List[dict], split_date: str = None) -> Dict:
    """Calcule le WFE en splitant IS/OOS à la date donnée (ou 50/50)."""
    if not trades:
        return {"wfe": 0, "pf_is": 0, "pf_oos": 0}

    if split_date:
        is_t  = [t for t in trades if t.get("open_time", "") < split_date]
        oos_t = [t for t in trades if t.get("open_time", "") >= split_date]
    else:
        mid   = len(trades) // 2
        is_t  = trades[:mid]
        oos_t = trades[mid:]

    def pf(ts):
        profits = sum(float(t.get("net_profit", t.get("profit", 0))) for t in ts if float(t.get("net_profit", t.get("profit", 0))) > 0)
        losses  = abs(sum(float(t.get("net_profit", t.get("profit", 0))) for t in ts if float(t.get("net_profit", t.get("profit", 0))) <= 0))
        return profits / losses if losses > 0 else 0

    pf_is  = pf(is_t)
    pf_oos = pf(oos_t)
    wfe    = pf_oos / pf_is if pf_is > 0 else 0

    return {
        "pf_is":    round(pf_is, 3),
        "pf_oos":   round(pf_oos, 3),
        "wfe":      round(wfe, 3),
        "n_is":     len(is_t),
        "n_oos":    len(oos_t),
        "verdict":  "ROBUSTE" if wfe >= 0.50 else ("ACCEPTABLE" if wfe >= 0.35 else "FRAGILE"),
    }


# ══════════════════════════════════════════════════════════════════
#  RAPPORT FORMATÉ
# ══════════════════════════════════════════════════════════════════

def format_report(m: BacktestMetrics, trades: List[dict],
                  wfe: Dict, capital: float) -> str:
    SEP  = "═" * 65
    SEP2 = "─" * 65

    def bar(val, max_val=2.0, width=20):
        filled = int(min(val / max_val, 1.0) * width)
        return "█" * filled + "░" * (width - filled)

    # Dates période
    dates = [t.get("open_time", t.get("close_time", "")) for t in trades if t.get("open_time") or t.get("close_time")]
    period = f"{min(dates)[:10]} → {max(dates)[:10]}" if dates else "Période inconnue"

    # Verdict global
    ok_pf  = m.profit_factor >= 1.25
    ok_dd  = m.max_drawdown_pct <= 20
    ok_tr  = m.n_trades >= 200
    ok_wfe = wfe.get("wfe", 0) >= 0.40
    all_ok = ok_pf and ok_dd and ok_tr

    if all_ok and ok_wfe:
        verdict = "🟢 GO LIVE — tous les critères validés"
    elif all_ok:
        verdict = "🟡 DÉMO 3 MOIS — WFE à surveiller"
    elif ok_pf and ok_dd:
        verdict = "🟡 ACCEPTABLE — augmenter le nombre de trades"
    else:
        verdict = "🔴 RE-OPTIMISER — critères non atteints"

    lines = [
        "",
        SEP,
        f"  ALADDIN PRO V6 — RAPPORT DE BACKTEST",
        SEP,
        f"  Période:   {period}",
        f"  Capital:   ${capital:,.0f}",
        f"  Trades:    {m.n_trades}",
        "",
        f"  {'RÉSULTAT GLOBAL':─<55}",
        f"  Net Profit:       ${m.total_profit:>+10.2f}  ({m.return_pct:+.1f}%)",
        f"  Capital final:    ${m.final_equity:>10.2f}",
        "",
        f"  {'MÉTRIQUES CLÉS':─<55}",
        f"  Profit Factor:    {m.profit_factor:>8.3f}  {'✅' if ok_pf else '❌'}  (> 1.25 requis)",
        f"  Win Rate:         {m.win_rate:>8.1%}",
        f"  Expectancy:       ${m.expectancy:>+9.2f} / trade",
        f"  Avg Win:          ${m.avg_win:>9.2f}",
        f"  Avg Loss:         ${m.avg_loss:>9.2f}",
        f"  Ratio W/L:        {m.avg_win/m.avg_loss:.2f}x" if m.avg_loss > 0 else "  Ratio W/L:        ∞",
        "",
        f"  {'RISQUE':─<55}",
        f"  Max Drawdown:     ${m.max_drawdown:>8.2f} ({m.max_drawdown_pct:.1f}%)  {'✅' if ok_dd else '❌'}  (< 20%)",
        f"  Max Consec. Loss: {m.max_consec_losses:>8}",
        f"  Recovery Factor:  {m.recovery_factor:>8.2f}  {'✅' if m.recovery_factor >= 1.5 else '⚠️'}",
        "",
        f"  {'RATIOS INSTITUTIONNELS':─<55}",
        f"  Sharpe Ratio:     {m.sharpe:>8.2f}  {'✅' if m.sharpe >= 0.8 else '⚠️'}  (> 0.80 requis)",
        f"  Calmar Ratio:     {m.calmar:>8.2f}  {'✅' if m.calmar >= 0.5 else '⚠️'}",
        f"  Durée moy trade:  {m.avg_duration_min:>5.0f} min",
        "",
        f"  {'WALK-FORWARD EFFICIENCY (WFE)':─<55}",
        f"  PF In-Sample:     {wfe.get('pf_is', 0):>8.3f}  ({wfe.get('n_is',0)} trades)",
        f"  PF Out-of-Sample: {wfe.get('pf_oos', 0):>8.3f}  ({wfe.get('n_oos',0)} trades)",
        f"  WFE (OOS/IS):     {wfe.get('wfe', 0):>8.3f}  [{wfe.get('verdict','?')}]  {'✅' if ok_wfe else '⚠️'}",
        "",
    ]

    # Par symbole
    if m.by_symbol:
        lines.append(f"  {'PAR INSTRUMENT':─<55}")
        lines.append(f"  {'Symbole':<10} {'Trades':>6} {'PF':>6} {'WR':>6} {'Total':>10}")
        for sym, s in sorted(m.by_symbol.items(), key=lambda x: -x[1]["total"]):
            lines.append(
                f"  {sym:<10} {s['n']:>6} {s['pf']:>6.2f} {s['wr']:>5.0%} ${s['total']:>+9.2f}"
            )
        lines.append("")

    # Par session
    if m.by_session:
        lines.append(f"  {'PAR SESSION':─<55}")
        for sess, s in sorted(m.by_session.items(), key=lambda x: -x[1]["total"]):
            lines.append(
                f"  {sess:<10} {s['n']:>4} trades  WR:{s['wr']:>4.0%}  ${s['total']:>+9.2f}"
            )
        lines.append("")

    # Mensuel
    if m.monthly_pnl:
        lines.append(f"  {'PNL MENSUEL':─<55}")
        for month, pnl in m.monthly_pnl.items():
            bar_str = bar(abs(pnl), max(abs(v) for v in m.monthly_pnl.values()), 15)
            sign = "+" if pnl >= 0 else ""
            lines.append(f"  {month}  {bar_str}  ${sign}{pnl:.2f}")
        lines.append("")

    # Courbe d'équité (mini ASCII)
    if len(m.equity_curve) > 2:
        lines.append(f"  {'COURBE D\'ÉQUITÉ (ASCII)':─<55}")
        _ascii_equity(m.equity_curve, lines, width=55, height=10)
        lines.append("")

    # Verdict
    lines += [
        SEP,
        f"  VERDICT: {verdict}",
        f"  Trades: {m.n_trades} {'✅' if ok_tr else '❌'} (>200)  |  "
        f"PF: {m.profit_factor:.3f} {'✅' if ok_pf else '❌'}  |  "
        f"MaxDD: {m.max_drawdown_pct:.1f}% {'✅' if ok_dd else '❌'}",
        SEP,
        "",
        "  COMMANDES SUIVANTES:",
        "  python optimizer.py --history trade_log_all.jsonl",
        "  python ml_engine.py --data trade_log_all.jsonl",
        "  python auto_trainer.py --status",
        SEP,
    ]

    return "\n".join(lines)


def _ascii_equity(curve: List[float], lines: List[str], width: int = 55, height: int = 10):
    """Mini graphique ASCII de la courbe d'équité."""
    if len(curve) < 2:
        return
    min_v = min(curve)
    max_v = max(curve)
    rng   = max_v - min_v or 1

    # Sous-échantillonnage
    step  = max(1, len(curve) // width)
    sampled = curve[::step][:width]

    rows = []
    for row in range(height, 0, -1):
        threshold = min_v + (row / height) * rng
        line_char = ""
        for val in sampled:
            if val >= threshold:
                line_char += "█"
            else:
                line_char += " "
        label = f"${threshold:>8.0f}" if row in (1, height // 2, height) else "         "
        rows.append(f"  {label} │{line_char}")

    lines += rows
    lines.append(f"           └{'─' * len(sampled)}")


# ══════════════════════════════════════════════════════════════════
#  CHECKLIST AVANT GO LIVE
# ══════════════════════════════════════════════════════════════════

def print_checklist(m: BacktestMetrics, wfe: Dict):
    SEP = "═" * 65
    items = [
        (m.n_trades >= 200,          f"200+ trades ({m.n_trades} réalisés)"),
        (m.profit_factor >= 1.25,    f"PF > 1.25 ({m.profit_factor:.3f})"),
        (m.max_drawdown_pct <= 20,   f"MaxDD < 20% ({m.max_drawdown_pct:.1f}%)"),
        (m.sharpe >= 0.8,            f"Sharpe > 0.80 ({m.sharpe:.2f})"),
        (wfe.get("wfe", 0) >= 0.40,  f"WFE > 0.40 ({wfe.get('wfe',0):.3f})"),
        (m.recovery_factor >= 1.5,   f"Recovery > 1.50 ({m.recovery_factor:.2f})"),
        (m.max_consec_losses <= 8,   f"Max pertes consec. ≤ 8 ({m.max_consec_losses})"),
        (m.win_rate >= 0.40,         f"Win Rate ≥ 40% ({m.win_rate:.1%})"),
    ]
    print(f"\n{SEP}")
    print("  CHECKLIST GO LIVE")
    print(SEP)
    passed = sum(1 for ok, _ in items if ok)
    for ok, label in items:
        print(f"  {'✅' if ok else '❌'} {label}")
    print(SEP)
    print(f"  Score: {passed}/{len(items)} critères validés")
    if passed == len(items):
        print("  🟢 PRÊT POUR LE DÉPLOIEMENT DÉMO")
    elif passed >= 6:
        print("  🟡 DÉMO RECOMMANDÉE — encore 3 mois de trading démo")
    else:
        print("  🔴 RE-OPTIMISER avant tout déploiement")
    print(SEP)


# ══════════════════════════════════════════════════════════════════
#  EXPORT JSON POUR DASHBOARD
# ══════════════════════════════════════════════════════════════════

def export_summary(m: BacktestMetrics, wfe: Dict, path: str = "backtest_summary.json"):
    summary = {
        "generated":     datetime.now().isoformat(),
        "n_trades":      m.n_trades,
        "win_rate":      round(m.win_rate, 4),
        "profit_factor": round(m.profit_factor, 4),
        "total_profit":  round(m.total_profit, 2),
        "return_pct":    round(m.return_pct, 2),
        "max_drawdown_pct": round(m.max_drawdown_pct, 2),
        "sharpe":        round(m.sharpe, 4),
        "calmar":        round(m.calmar, 4),
        "recovery_factor": round(m.recovery_factor, 4),
        "wfe":           wfe,
        "by_symbol":     m.by_symbol,
        "monthly_pnl":   m.monthly_pnl,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Résumé exporté: {path}")
    return summary


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE CLI
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Aladdin Pro — Backtest Analyzer")
    parser.add_argument("--report",  default=None,   help="Fichier JSONL des trades (ex: trade_log_all.jsonl)")
    parser.add_argument("--capital", type=float, default=1000.0, help="Capital initial ($)")
    parser.add_argument("--split",   default=None,   help="Date de split IS/OOS ex: 2024-01-01")
    parser.add_argument("--export",  default="backtest_summary.json", help="Fichier JSON de sortie")
    parser.add_argument("--demo",    action="store_true", help="Mode démo avec données synthétiques")
    args = parser.parse_args()

    if args.demo or not args.report:
        print("\n[DEMO] Génération d'un historique synthétique (300 trades, 2 ans)...")
        from ml_engine import generate_synthetic_trades
        trades = generate_synthetic_trades(300, seed=99)
        # Simuler des dates sur 2 ans
        from datetime import datetime, timedelta
        import random
        base = datetime(2023, 1, 2, 9, 0)
        for i, t in enumerate(trades):
            open_t = base + timedelta(hours=i * 5.5)
            t["open_time"]  = open_t.strftime("%Y-%m-%d %H:%M:%S")
            t["close_time"] = (open_t + timedelta(minutes=t.get("duration_min", 10))).strftime("%Y-%m-%d %H:%M:%S")
            t["ticket"] = 1000000 + i
    else:
        print(f"\nChargement: {args.report}")
        trades = load_trades(args.report)

    if not trades:
        print("  Aucun trade chargé.")
        return

    print(f"  {len(trades)} trades chargés")

    # Métriques
    m = BacktestMetrics(trades, initial_capital=args.capital)

    # WFE
    split_date = args.split or (
        "2024-01-01" if any("2023" in t.get("open_time","") for t in trades) else None
    )
    wfe = compute_wfe(trades, split_date)

    # Rapport complet
    print(format_report(m, trades, wfe, args.capital))

    # Checklist
    print_checklist(m, wfe)

    # Export JSON
    export_summary(m, wfe, args.export)


if __name__ == "__main__":
    main()
