"""
ALADDIN PRO V6 — log_collector.py
Lit les fichiers JSONL produits par logging_module.mq5
Fonctions: rapport journalier, analyse signaux rejetes, export optimizer

Usage:
  python log_collector.py --watch
  python log_collector.py --report today
  python log_collector.py --report week
  python log_collector.py --signals
  python log_collector.py --export-optimizer
"""
import os, json, time, argparse, statistics
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass, field


# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION (path macOS/Wine adapté)
# ══════════════════════════════════════════════════════════════════

MT5_FILES_DEFAULT = (
    "/Users/macbookpro/Library/Application Support/"
    "net.metaquotes.wine.metatrader5/drive_c/Program Files/"
    "MetaTrader 5/MQL5/Files"
)

class Config:
    MT5_PATH   = Path(os.getenv("MT5_FILES_PATH", MT5_FILES_DEFAULT))
    EXPORT_DIR = Path("./exports")


# ══════════════════════════════════════════════════════════════════
#  LECTURE JSONL
# ══════════════════════════════════════════════════════════════════

def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


# ══════════════════════════════════════════════════════════════════
#  STATISTIQUES
# ══════════════════════════════════════════════════════════════════

REGIME_NAMES = {0: "TREND_UP", 1: "TREND_DOWN", 2: "RANGING", 3: "VOLATILE"}


@dataclass
class Stats:
    total:         int   = 0
    wins:          int   = 0
    losses:        int   = 0
    win_rate:      float = 0
    gross_profit:  float = 0
    gross_loss:    float = 0
    net_profit:    float = 0
    profit_factor: float = 0
    avg_win:       float = 0
    avg_loss:      float = 0
    avg_duration:  float = 0
    avg_rr:        float = 0
    tp_hit_rate:   float = 0
    sl_hit_rate:   float = 0
    be_rate:       float = 0
    trail_rate:    float = 0
    avg_atr:       float = 0
    avg_rsi:       float = 0
    avg_adx:       float = 0
    avg_spread:    float = 0
    by_symbol:     dict  = field(default_factory=dict)
    by_regime:     dict  = field(default_factory=dict)
    by_hour:       dict  = field(default_factory=dict)
    close_reasons: dict  = field(default_factory=dict)


def compute_stats(trades: List[dict]) -> Stats:
    if not trades:
        return Stats()
    s = Stats()
    s.total = len(trades)

    profits    = [t.get("net_profit", t.get("profit", 0)) for t in trades]
    wins_pnl   = [p for p in profits if p > 0]
    losses_pnl = [p for p in profits if p <= 0]

    s.wins          = len(wins_pnl)
    s.losses        = len(losses_pnl)
    s.win_rate      = s.wins / s.total * 100
    s.gross_profit  = sum(wins_pnl)
    s.gross_loss    = abs(sum(losses_pnl))
    s.net_profit    = sum(profits)
    s.profit_factor = s.gross_profit / s.gross_loss if s.gross_loss > 0 else 99.9
    s.avg_win       = statistics.mean(wins_pnl)   if wins_pnl   else 0
    s.avg_loss      = statistics.mean(losses_pnl) if losses_pnl else 0

    durs = [t.get("duration_min", 0) for t in trades if t.get("duration_min", 0) > 0]
    rrs  = [t.get("rr_ratio", 0)     for t in trades if t.get("rr_ratio", 0) > 0]
    s.avg_duration = statistics.mean(durs) if durs else 0
    s.avg_rr       = statistics.mean(rrs)  if rrs  else 0

    s.tp_hit_rate  = sum(1 for t in trades if t.get("hit_tp"))          / s.total * 100
    s.sl_hit_rate  = sum(1 for t in trades if t.get("hit_sl"))          / s.total * 100
    s.be_rate      = sum(1 for t in trades if t.get("be_triggered"))    / s.total * 100
    s.trail_rate   = sum(1 for t in trades if t.get("trail_triggered")) / s.total * 100

    atrs = [t.get("atr_at_entry", 0) for t in trades if t.get("atr_at_entry", 0) > 0]
    rsis = [t.get("rsi_at_entry", 0) for t in trades if t.get("rsi_at_entry", 0) > 0]
    adxs = [t.get("adx_at_entry", 0) for t in trades if t.get("adx_at_entry", 0) > 0]
    sprs = [t.get("spread_entry", 0)  for t in trades if t.get("spread_entry", 0) > 0]
    s.avg_atr    = statistics.mean(atrs) if atrs else 0
    s.avg_rsi    = statistics.mean(rsis) if rsis else 0
    s.avg_adx    = statistics.mean(adxs) if adxs else 0
    s.avg_spread = statistics.mean(sprs) if sprs else 0

    by_sym = defaultdict(list)
    for t in trades:
        by_sym[t.get("symbol", "?")].append(t.get("net_profit", t.get("profit", 0)))
    for sym, pnls in by_sym.items():
        w  = sum(1 for p in pnls if p > 0)
        gw = sum(p for p in pnls if p > 0)
        gl = abs(sum(p for p in pnls if p <= 0))
        s.by_symbol[sym] = {
            "trades":   len(pnls),
            "profit":   round(sum(pnls), 2),
            "win_rate": round(w / len(pnls) * 100, 1),
            "pf":       round(gw / gl, 2) if gl > 0 else 99.9,
        }

    by_reg = defaultdict(list)
    for t in trades:
        by_reg[t.get("regime", -1)].append(t.get("net_profit", t.get("profit", 0)))
    for reg, pnls in by_reg.items():
        w    = sum(1 for p in pnls if p > 0)
        name = REGIME_NAMES.get(reg, f"regime_{reg}")
        s.by_regime[name] = {
            "trades":   len(pnls),
            "profit":   round(sum(pnls), 2),
            "win_rate": round(w / len(pnls) * 100, 1),
        }

    by_h = defaultdict(list)
    for t in trades:
        ot = t.get("open_time", "")
        try:
            h = int(ot[11:13]) if len(ot) >= 13 else -1
        except Exception:
            h = -1
        if h >= 0:
            by_h[h].append(t.get("net_profit", t.get("profit", 0)))
    for hour, pnls in by_h.items():
        w = sum(1 for p in pnls if p > 0)
        s.by_hour[hour] = {
            "trades":   len(pnls),
            "profit":   round(sum(pnls), 2),
            "win_rate": round(w / len(pnls) * 100, 1),
        }

    s.close_reasons = dict(Counter(t.get("close_reason", "?") for t in trades))
    return s


# ══════════════════════════════════════════════════════════════════
#  FORMATAGE RAPPORT
# ══════════════════════════════════════════════════════════════════

def format_trade_report(trades: List[dict], title: str = "RAPPORT") -> str:
    s   = compute_stats(trades)
    SEP = "=" * 58

    def row(k, v):
        return f"  {k:<26}{v}"

    if s.total == 0:
        return f"\n{SEP}\n  {title}\n{SEP}\n  Aucun trade enregistre.\n"

    lines = [
        f"\n{SEP}", f"  {title}", SEP, "",
        "  GENERAUX",
        row("Trades:",        f"{s.total}  ({s.wins}W / {s.losses}L)"),
        row("Win Rate:",      f"{s.win_rate:.1f}%"),
        row("Net Profit:",    f"${s.net_profit:>+.2f}"),
        row("Profit Factor:", f"{s.profit_factor:.3f}"),
        row("Avg Win/Loss:",  f"${s.avg_win:.2f} / ${s.avg_loss:.2f}"),
        row("Avg Duration:",  f"{s.avg_duration:.1f} min"),
        row("Avg R:R:",       f"{s.avg_rr:.2f}"),
        "",
        "  GESTION DE TRADE",
        row("TP hit rate:",   f"{s.tp_hit_rate:.1f}%"),
        row("SL hit rate:",   f"{s.sl_hit_rate:.1f}%"),
        row("Breakeven:",     f"{s.be_rate:.1f}%"),
        row("Trailing:",      f"{s.trail_rate:.1f}%"),
        "",
        "  INDICATEURS ENTREE (moyennes)",
        row("ATR:",           f"{s.avg_atr:.5f}"),
        row("RSI:",           f"{s.avg_rsi:.1f}"),
        row("ADX:",           f"{s.avg_adx:.1f}"),
        row("Spread:",        f"{s.avg_spread:.0f} pts"),
        "",
        "  RAISONS CLOTURE",
    ]
    for reason, cnt in sorted(s.close_reasons.items(), key=lambda x: -x[1]):
        lines.append(f"    {reason:<16}  {cnt:>4} ({cnt / s.total * 100:.1f}%)")

    lines += ["", "  PAR SYMBOLE"]
    for sym, d in sorted(s.by_symbol.items(), key=lambda x: -x[1]["profit"]):
        lines.append(
            f"  {sym:<10} {d['trades']:>4}t  WR:{d['win_rate']:.0f}%"
            f"  P:${d['profit']:>+7.2f}  PF:{d['pf']:.2f}"
        )

    lines += ["", "  PAR REGIME"]
    for name, d in sorted(s.by_regime.items(), key=lambda x: -x[1]["profit"]):
        lines.append(
            f"  {name:<14} {d['trades']:>4}t"
            f"  WR:{d['win_rate']:.0f}%  P:${d['profit']:>+7.2f}"
        )

    if s.by_hour:
        best3  = sorted(s.by_hour.items(), key=lambda x: -x[1]["profit"])[:3]
        worst3 = sorted(s.by_hour.items(), key=lambda x:  x[1]["profit"])[:3]
        lines += ["", "  TOP 3 HEURES UTC (profit)"]
        for h, d in best3:
            lines.append(f"  {h:02d}h  {d['trades']}t  P:${d['profit']:>+7.2f}  WR:{d['win_rate']:.0f}%")
        lines += ["", "  PIRES 3 HEURES UTC"]
        for h, d in worst3:
            lines.append(f"  {h:02d}h  {d['trades']}t  P:${d['profit']:>+7.2f}  WR:{d['win_rate']:.0f}%")

    lines.append(SEP)
    return "\n".join(str(l) for l in lines)


def format_signal_report(signals: List[dict]) -> str:
    if not signals:
        return "  Aucun signal rejete trouve."
    SEP       = "=" * 58
    total     = len(signals)
    by_reason = Counter(s.get("reason", "?") for s in signals)
    by_sym    = Counter(s.get("sym",    "?") for s in signals)
    rsi_vals  = [s["rsi"]    for s in signals if s.get("rsi",    0) > 0]
    adx_vals  = [s["adx"]    for s in signals if s.get("adx",    0) > 0]
    spr_vals  = [s["spread"] for s in signals if s.get("spread", 0) > 0]

    lines = [
        f"\n{SEP}",
        "  SIGNAUX REJETES — Analyse Diagnostique",
        SEP,
        f"  Total rejets: {total}", "",
        "  CAUSES (frequence):",
    ]
    for reason, cnt in by_reason.most_common():
        pct = cnt / total * 100
        bar = "█" * int(pct / 4)
        lines.append(f"  {reason:<22}  {cnt:>5} ({pct:>5.1f}%)  {bar}")

    lines += ["", "  PAR SYMBOLE:"]
    for sym, cnt in by_sym.most_common():
        lines.append(f"  {sym:<12}  {cnt:>5} ({cnt / total * 100:>5.1f}%)")

    if rsi_vals:
        lines += ["", "  INDICATEURS AU MOMENT DU REJET:"]
        lines.append(f"  RSI moyen:    {statistics.mean(rsi_vals):.1f}")
        if adx_vals:
            lines.append(f"  ADX moyen:    {statistics.mean(adx_vals):.1f}")
        if spr_vals:
            lines.append(f"  Spread moyen: {statistics.mean(spr_vals):.0f} pts")

    lines += ["", "  INSIGHTS AUTOMATIQUES:"]
    if by_reason.get("SPREAD_HIGH", 0) / total > 0.30:
        lines.append("  >> +30% spread — augmenter MaxSpread dans le bot")
    if by_reason.get("ADX_LOW",    0) / total > 0.25:
        lines.append("  >> +25% ADX faible — normal session asiatique")
    if by_reason.get("RR_LOW",     0) / total > 0.20:
        lines.append("  >> +20% R:R insuffisant — ajuster ATR_TP_Mult")
    if by_reason.get("NEWS_BLOCK", 0) / total > 0.15:
        lines.append("  >> +15% news block — normal NFP/FOMC/CPI")

    lines.append(SEP)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  MODE WATCH (terminal en temps réel)
# ══════════════════════════════════════════════════════════════════

def watch_mode(cfg: Config):
    print("\n  Surveillance active — Ctrl+C pour quitter\n")
    try:
        while True:
            os.system("clear")
            print(f"  ALADDIN PRO — Log Monitor  [{datetime.now().strftime('%H:%M:%S')}]")
            print("  " + "=" * 55)

            sess_recs = read_jsonl(cfg.MT5_PATH / "session_history.jsonl")
            if sess_recs:
                sess = sess_recs[-1]
                pnl  = sess.get("session_pnl", 0)
                print(f"  Balance:  ${sess.get('balance', 0):.2f}  |  PnL: ${pnl:>+.2f}")
                print(f"  Trades:   {sess.get('daily_trades', 0)}"
                      f"  W:{sess.get('day_wins', 0)} L:{sess.get('day_losses', 0)}"
                      f"  PF:{sess.get('pf', 0):.2f}  WR:{sess.get('wr', 0):.1f}%")
                print(f"  DD:       {sess.get('drawdown_pct', 0):.2f}%"
                      f"  Bot: {'ON' if sess.get('trading') else 'OFF'}"
                      f"  ConsecL:{sess.get('consec_loss', 0)}")
                sp = sess.get("spreads", {})
                if sp:
                    print("  Spreads: " + "  ".join(f"{k}:{v}" for k, v in sp.items()))
            else:
                print("  En attente des donnees MT5...")

            eq_recs = read_jsonl(cfg.MT5_PATH / "equity_curve.jsonl")
            if len(eq_recs) >= 2:
                f0 = eq_recs[-10]["equity"] if len(eq_recs) >= 10 else eq_recs[0]["equity"]
                fl = eq_recs[-1]["equity"]
                tr = "↑" if fl > f0 else ("↓" if fl < f0 else "→")
                print(f"\n  Equity: {tr}  {f0:.2f} → {fl:.2f}")

            today      = date.today().strftime("%Y-%m-%d")
            day_trades = read_jsonl(cfg.MT5_PATH / f"trade_log_{today}.jsonl")
            if day_trades:
                print(f"\n  Derniers trades ({len(day_trades)} aujourd'hui):")
                for t in day_trades[-5:]:
                    pnl = t.get("net_profit", t.get("profit", 0))
                    print(f"  {'✓' if pnl > 0 else '✗'} {t.get('symbol', '?'):<10}"
                          f"  {t.get('direction', '?'):<5}  ${pnl:>+6.2f}"
                          f"  {t.get('duration_min', 0)}min  [{t.get('close_reason', '?')}]")

            sig_recs = read_jsonl(cfg.MT5_PATH / "signal_log.jsonl")
            if sig_recs:
                print(f"\n  Derniers rejets:")
                for s in sig_recs[-5:]:
                    print(f"  -- {s.get('sym', '?'):<10}"
                          f"  {s.get('reason', '?'):<20}"
                          f"  RSI:{s.get('rsi', 0):.1f}"
                          f"  ADX:{s.get('adx', 0):.1f}"
                          f"  Sprd:{s.get('spread', 0):.0f}")
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("\n  Arret.")


# ══════════════════════════════════════════════════════════════════
#  EXPORT POUR OPTIMIZER
# ══════════════════════════════════════════════════════════════════

def export_for_optimizer(cfg: Config, capital: float):
    trades = read_jsonl(cfg.MT5_PATH / "trade_log_all.jsonl")
    if not trades:
        print("Aucun trade trouve.")
        return
    converted = []
    for t in trades:
        try:
            ot = t.get("open_time", "")
            ct = t.get("close_time", "")
            for fmt in ["%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    ot = datetime.strptime(ot, fmt).isoformat()
                    ct = datetime.strptime(ct, fmt).isoformat()
                    break
                except Exception:
                    pass
            converted.append({
                "symbol":        t.get("symbol", ""),
                "direction":     t.get("direction", ""),
                "open_time":     ot,
                "close_time":    ct,
                "open_price":    float(t.get("open_price",  0)),
                "close_price":   float(t.get("close_price", 0)),
                "lot":           float(t.get("lot",         0.01)),
                "profit":        float(t.get("net_profit",  t.get("profit", 0))),
                "sl_distance":   float(t.get("sl_distance", 0)),
                "atr_at_entry":  float(t.get("atr_at_entry", 0)),
                "rsi_at_entry":  float(t.get("rsi_at_entry", 50)),
                "adx_at_entry":  float(t.get("adx_at_entry", 20)),
            })
        except Exception:
            continue

    cfg.EXPORT_DIR.mkdir(exist_ok=True)
    out = cfg.EXPORT_DIR / "optimizer_input.json"
    with open(out, "w") as f:
        json.dump({
            "generated":    datetime.now().isoformat(),
            "capital":      capital,
            "total_trades": len(converted),
            "trades":       converted,
        }, f, indent=2)
    print(f"\n  {len(converted)} trades exportes → {out}")
    print(f"  Commande: python optimizer.py --history {out} --capital {capital}")


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTREE
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Aladdin Pro Log Collector")
    parser.add_argument("--mt5-path",         default=None)
    parser.add_argument("--watch",            action="store_true")
    parser.add_argument("--report",           choices=["today", "week"])
    parser.add_argument("--signals",          action="store_true")
    parser.add_argument("--export-optimizer", action="store_true")
    parser.add_argument("--capital",          type=float, default=1000.0)
    args = parser.parse_args()

    cfg = Config()
    if args.mt5_path:
        cfg.MT5_PATH = Path(args.mt5_path)

    if args.watch:
        watch_mode(cfg)
    elif args.report == "today":
        today  = date.today().strftime("%Y-%m-%d")
        trades = read_jsonl(cfg.MT5_PATH / f"trade_log_{today}.jsonl")
        print(format_trade_report(trades, f"RAPPORT JOURNALIER — {today}"))
    elif args.report == "week":
        all_trades = []
        for i in range(7):
            d = (date.today() - timedelta(days=i)).strftime("%Y-%m-%d")
            all_trades.extend(read_jsonl(cfg.MT5_PATH / f"trade_log_{d}.jsonl"))
        print(format_trade_report(all_trades, "RAPPORT HEBDOMADAIRE"))
    elif args.signals:
        sigs = read_jsonl(cfg.MT5_PATH / "signal_log.jsonl")
        print(format_signal_report(sigs))
    elif args.export_optimizer:
        export_for_optimizer(cfg, args.capital)
    else:
        # Rapport par défaut: aujourd'hui + rejets
        today  = date.today().strftime("%Y-%m-%d")
        trades = read_jsonl(cfg.MT5_PATH / f"trade_log_{today}.jsonl")
        print(format_trade_report(trades, f"RAPPORT DU JOUR — {today}"))
        sigs = read_jsonl(cfg.MT5_PATH / "signal_log.jsonl")
        print(format_signal_report(sigs[-200:]))


if __name__ == "__main__":
    main()
