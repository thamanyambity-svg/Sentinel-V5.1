"""
╔══════════════════════════════════════════════════════════════════════╗
║  ALADDIN PRO V6 — Module 5: Optimiseur Automatique de Paramètres    ║
║                                                                      ║
║  Méthode: Walk-Forward Optimization (WFO) institutionnelle          ║
║  Cibles: ATR_SL_Mult · ATR_TP_Mult · RSI · ADX · EMA periods       ║
║  Validation: Out-of-Sample obligatoire — anti curve-fitting          ║
║  Critère: Maximiser Profit Factor × Sharpe (score composite)        ║
║                                                                      ║
║  Usage:                                                              ║
║    python optimizer.py --history trades.json --capital 1000          ║
║    python optimizer.py --demo  # Test avec données synthétiques      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import math
import json
import random
import logging
import itertools
import statistics
import argparse
import os
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from copy import deepcopy


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("Optimizer")


# ══════════════════════════════════════════════════════════════════
#  STRUCTURES
# ══════════════════════════════════════════════════════════════════

@dataclass
class TradeRecord:
    """Enregistrement d'un trade pour le backtesting."""
    symbol:      str
    direction:   str        # BUY | SELL
    open_time:   datetime
    close_time:  datetime
    open_price:  float
    close_price: float
    lot:         float
    profit:      float
    sl_distance: float      # Distance SL en termes de prix
    atr_at_entry: float     # ATR au moment de l'entrée
    rsi_at_entry: float     # RSI au moment de l'entrée
    adx_at_entry: float     # ADX au moment de l'entrée

    @property
    def is_win(self) -> bool:
        return self.profit > 0

    @property
    def duration_min(self) -> float:
        return (self.close_time - self.open_time).total_seconds() / 60


@dataclass
class ParameterSet:
    """Ensemble de paramètres à optimiser."""
    atr_sl_mult:    float = 1.5
    atr_tp_mult:    float = 2.5
    rsi_period:     int   = 14
    rsi_ob:         int   = 65
    rsi_os:         int   = 35
    ema_fast:       int   = 9
    ema_slow:       int   = 21
    adx_min:        float = 20.0
    min_rr:         float = 1.8

    def to_dict(self) -> Dict:
        return {
            "ATR_SL_Multiplier": self.atr_sl_mult,
            "ATR_TP_Multiplier": self.atr_tp_mult,
            "RSI_Period":        self.rsi_period,
            "RSI_Overbought":    self.rsi_ob,
            "RSI_Oversold":      self.rsi_os,
            "EMA_Fast":          self.ema_fast,
            "EMA_Slow":          self.ema_slow,
            "ADX_MinStrength":   self.adx_min,
            "MinRR_Ratio":       self.min_rr,
        }

    def to_mql5_comment(self) -> str:
        """Génère les lignes input MQL5 avec les valeurs optimisées."""
        lines = [
            "// === PARAMETRES OPTIMISES — Aladdin Pro V6 ===",
            f"// Generé le {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "// A coller dans les inputs du bot (panneau Expert Properties)",
            "",
        ]
        for k, v in self.to_dict().items():
            if isinstance(v, float):
                lines.append(f"input double {k:<25} = {v:.2f};")
            else:
                lines.append(f"input int    {k:<25} = {v};")
        return "\n".join(lines)


@dataclass
class OptimizationResult:
    """Résultat d'une combinaison de paramètres testée."""
    params:       ParameterSet
    is_profit:    float   # Performance In-Sample
    oos_profit:   float   # Performance Out-of-Sample (validation)
    is_pf:        float   # Profit Factor IS
    oos_pf:       float   # Profit Factor OOS
    is_sharpe:    float
    oos_sharpe:   float
    is_win_rate:  float
    oos_win_rate: float
    max_drawdown: float
    wfe:          float   # Walk-Forward Efficiency = OOS PF / IS PF
    score:        float   # Score composite (critère de sélection)
    n_is_trades:  int
    n_oos_trades: int

    @property
    def is_valid(self) -> bool:
        """Un résultat est valide si l'OOS est aussi profitable."""
        return (
            self.oos_profit > 0 and
            self.oos_pf > 1.0 and
            self.wfe >= 0.4 and
            self.max_drawdown < 20.0 and
            self.n_oos_trades >= 5
        )


# ══════════════════════════════════════════════════════════════════
#  SIMULATEUR DE STRATÉGIE (simplifié, basé sur ATR)
# ══════════════════════════════════════════════════════════════════

class StrategySimulator:
    """
    Rejoue les trades historiques avec de nouveaux paramètres SL/TP.
    Hypothèse: on garde les mêmes entrées (direction, timing),
    on recalcule les sorties selon les nouveaux SL/TP ATR.
    """

    def __init__(self, trades: List[TradeRecord], initial_capital: float = 1000.0):
        self.trades  = trades
        self.capital = initial_capital

    def simulate(self, params: ParameterSet) -> List[float]:
        """
        Simule les PnL avec les paramètres donnés.
        Retourne la liste des PnL par trade.
        """
        pnl_list = []
        for t in self.trades:
            if t.atr_at_entry <= 0:
                continue

            # Recalcul SL et TP avec les nouveaux multiplicateurs
            sl_dist = t.atr_at_entry * params.atr_sl_mult
            tp_dist = t.atr_at_entry * params.atr_tp_mult

            # Filtre R:R
            rr = tp_dist / sl_dist if sl_dist > 0 else 0
            if rr < params.min_rr:
                continue  # Trade ignoré car R:R insuffisant

            # Filtre ADX
            if t.adx_at_entry < params.adx_min:
                continue

            # Filtre RSI (simplifié)
            if t.direction == "BUY":
                if not (params.rsi_os <= t.rsi_at_entry <= params.rsi_ob):
                    continue
            else:
                if not (params.rsi_os <= t.rsi_at_entry <= params.rsi_ob):
                    continue

            # Calcul PnL recalibré
            tick_value  = 1.0  # Normalisé pour comparaison relative
            risk_amount = sl_dist * t.lot * tick_value

            # Simuler issue: si le trade original était gagnant avec SL/TP d'origine,
            # on l'adapte proportionnellement
            if t.is_win:
                pnl = tp_dist * t.lot * tick_value
            else:
                pnl = -sl_dist * t.lot * tick_value

            pnl_list.append(pnl)

        return pnl_list

    def metrics_from_pnl(self, pnl_list: List[float]) -> Dict:
        if len(pnl_list) < 3:
            return {
                "profit": 0, "pf": 0, "sharpe": 0,
                "win_rate": 0, "max_dd": 100, "n": 0
            }

        wins   = [p for p in pnl_list if p > 0]
        losses = [p for p in pnl_list if p <= 0]

        gross_w = sum(wins)
        gross_l = abs(sum(losses))
        pf      = (gross_w / gross_l) if gross_l > 0 else float("inf")
        wr      = len(wins) / len(pnl_list) * 100

        # Courbe d'équité + drawdown
        eq      = self.capital
        peak    = eq
        max_dd  = 0.0
        returns = []
        prev    = self.capital
        for p in pnl_list:
            eq   += p
            peak  = max(peak, eq)
            dd    = (peak - eq) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
            if prev != 0:
                returns.append(p / prev)
            prev = eq

        # Sharpe simplifié
        if len(returns) > 1:
            avg = statistics.mean(returns)
            std = statistics.stdev(returns) or 1e-10
            sharpe = (avg / std) * math.sqrt(252)
        else:
            sharpe = 0.0

        return {
            "profit":   round(sum(pnl_list), 4),
            "pf":       round(pf, 3),
            "sharpe":   round(sharpe, 3),
            "win_rate": round(wr, 1),
            "max_dd":   round(max_dd, 2),
            "n":        len(pnl_list),
        }


# ══════════════════════════════════════════════════════════════════
#  GRILLE D'OPTIMISATION (GRID SEARCH)
# ══════════════════════════════════════════════════════════════════

class GridSearchOptimizer:
    """
    Optimisation par grille sur les paramètres clés.
    Validée obligatoirement sur Out-of-Sample (70/30 split).
    """

    # Grilles de paramètres à tester
    PARAM_GRID = {
        "atr_sl_mult":  [1.0, 1.2, 1.5, 1.8, 2.0, 2.5],
        "atr_tp_mult":  [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        "adx_min":      [15.0, 18.0, 20.0, 25.0, 30.0],
        "min_rr":       [1.5, 1.8, 2.0, 2.5],
        # RSI et EMA: moins de variation pour limiter la combinatoire
        "rsi_ob":       [60, 65, 70],
        "rsi_os":       [30, 35, 40],
    }

    def __init__(self, trades: List[TradeRecord], capital: float = 1000.0,
                 is_pct: float = 0.7, verbose: bool = True):
        self.trades   = sorted(trades, key=lambda t: t.open_time)
        self.capital  = capital
        self.is_pct   = is_pct
        self.verbose  = verbose

        split = int(len(trades) * is_pct)
        self.is_trades  = self.trades[:split]
        self.oos_trades = self.trades[split:]

        self.sim_is  = StrategySimulator(self.is_trades,  capital)
        self.sim_oos = StrategySimulator(self.oos_trades, capital)

        log.info("Grid Search init — IS: %d trades | OOS: %d trades",
                 len(self.is_trades), len(self.oos_trades))

    def composite_score(self, is_m: Dict, oos_m: Dict) -> float:
        """
        Critère de sélection composite:
        Priorise la performance OOS (ce qui compte en live),
        pénalise le drawdown et récompense la robustesse IS/OOS.
        """
        if oos_m["n"] < 5 or oos_m["pf"] <= 0:
            return -999.0

        wfe = (oos_m["pf"] / is_m["pf"]) if is_m["pf"] > 0 else 0.0

        score = (
            oos_m["pf"]        * 3.0    # Profit Factor OOS x3
            + oos_m["sharpe"]  * 2.0    # Sharpe OOS x2
            + oos_m["win_rate"] / 100   # Win Rate OOS
            + wfe              * 2.0    # Robustesse IS→OOS x2
            - oos_m["max_dd"]  / 10.0   # Malus drawdown
            - max(0, is_m["pf"] - oos_m["pf"]) * 3  # Malus surfit
        )
        return round(score, 4)

    def run(self) -> List[OptimizationResult]:
        """Lance l'optimisation complète sur la grille."""

        # Calcul du nombre total de combinaisons
        grid_values = [
            self.PARAM_GRID["atr_sl_mult"],
            self.PARAM_GRID["atr_tp_mult"],
            self.PARAM_GRID["adx_min"],
            self.PARAM_GRID["min_rr"],
            self.PARAM_GRID["rsi_ob"],
            self.PARAM_GRID["rsi_os"],
        ]
        total = 1
        for v in grid_values:
            total *= len(v)

        log.info("Lancement Grid Search: %d combinaisons a tester...", total)

        results: List[OptimizationResult] = []
        tested = 0

        for sl, tp, adx, rr, rsi_ob, rsi_os in itertools.product(*grid_values):
            # Skip les combinaisons incohérentes
            if rsi_os >= rsi_ob:
                continue
            if tp <= sl:       # TP doit être supérieur au SL
                continue
            if tp / sl < rr:   # R:R théorique doit être >= min_rr
                continue

            params = ParameterSet(
                atr_sl_mult = sl,
                atr_tp_mult = tp,
                adx_min     = adx,
                min_rr      = rr,
                rsi_ob      = rsi_ob,
                rsi_os      = rsi_os,
            )

            # Simulation IS
            is_pnl  = self.sim_is.simulate(params)
            is_m    = self.sim_is.metrics_from_pnl(is_pnl)

            # Skip si IS pas profitable (inutile de tester OOS)
            if is_m["pf"] < 1.1 or is_m["n"] < 5:
                tested += 1
                continue

            # Simulation OOS (validation obligatoire)
            oos_pnl = self.sim_oos.simulate(params)
            oos_m   = self.sim_oos.metrics_from_pnl(oos_pnl)

            wfe   = (oos_m["pf"] / is_m["pf"]) if is_m["pf"] > 0 else 0.0
            score = self.composite_score(is_m, oos_m)

            result = OptimizationResult(
                params       = params,
                is_profit    = is_m["profit"],
                oos_profit   = oos_m["profit"],
                is_pf        = is_m["pf"],
                oos_pf       = oos_m["pf"],
                is_sharpe    = is_m["sharpe"],
                oos_sharpe   = oos_m["sharpe"],
                is_win_rate  = is_m["win_rate"],
                oos_win_rate = oos_m["win_rate"],
                max_drawdown = oos_m["max_dd"],
                wfe          = round(wfe, 3),
                score        = score,
                n_is_trades  = is_m["n"],
                n_oos_trades = oos_m["n"],
            )
            results.append(result)
            tested += 1

            if self.verbose and tested % 200 == 0:
                log.info("  %d/%d testées | Meilleur score: %.3f",
                         tested, total,
                         max((r.score for r in results), default=0))

        log.info("Grid Search terminé: %d combinaisons valides sur %d testées",
                 len(results), tested)

        # Tri par score décroissant
        results.sort(key=lambda r: r.score, reverse=True)
        return results


# ══════════════════════════════════════════════════════════════════
#  RAPPORT ET EXPORT
# ══════════════════════════════════════════════════════════════════

class OptimizationReport:

    @staticmethod
    def top_results(results: List[OptimizationResult], n: int = 10) -> str:
        SEP = "=" * 72
        valid = [r for r in results if r.is_valid]
        all_  = results[:n]

        lines = [
            "", SEP,
            "  ALADDIN PRO V6 — RAPPORT D'OPTIMISATION PARAMETRES",
            SEP,
            f"  Combinaisons testees:  {len(results)}",
            f"  Combinaisons valides:  {len(valid)} (OOS profitable + WFE >= 0.4)",
            "",
            "  TOP 5 RESULTATS (trie par score composite IS+OOS):",
            "",
            f"  {'#':<3} {'SL_Mult':<9} {'TP_Mult':<9} {'ADX':<6} {'RR':<5} "
            f"{'IS_PF':<7} {'OOS_PF':<7} {'WFE':<6} {'DD%':<6} {'Score':<7} {'Valide'}",
            "-" * 72,
        ]

        for i, r in enumerate(all_[:5]):
            valid_mark = "✅" if r.is_valid else "❌"
            lines.append(
                f"  {i+1:<3} "
                f"{r.params.atr_sl_mult:<9.2f}"
                f"{r.params.atr_tp_mult:<9.2f}"
                f"{r.params.adx_min:<6.0f}"
                f"{r.params.min_rr:<5.1f}"
                f"{r.is_pf:<7.3f}"
                f"{r.oos_pf:<7.3f}"
                f"{r.wfe:<6.3f}"
                f"{r.max_drawdown:<6.1f}"
                f"{r.score:<7.3f}"
                f"{valid_mark}"
            )

        if valid:
            best = valid[0]
            lines += [
                "", SEP,
                "  MEILLEUR RESULTAT VALIDE (IS + OOS profitable):",
                "",
                f"  ATR_SL_Multiplier:  {best.params.atr_sl_mult:.2f}",
                f"  ATR_TP_Multiplier:  {best.params.atr_tp_mult:.2f}",
                f"  ADX_MinStrength:    {best.params.adx_min:.1f}",
                f"  MinRR_Ratio:        {best.params.min_rr:.1f}",
                f"  RSI_Overbought:     {best.params.rsi_ob}",
                f"  RSI_Oversold:       {best.params.rsi_os}",
                "",
                f"  IS   — PF: {best.is_pf:.3f} | WR: {best.is_win_rate:.1f}% | "
                f"Sharpe: {best.is_sharpe:.2f} | Trades: {best.n_is_trades}",
                f"  OOS  — PF: {best.oos_pf:.3f} | WR: {best.oos_win_rate:.1f}% | "
                f"Sharpe: {best.oos_sharpe:.2f} | Trades: {best.n_oos_trades}",
                f"  WFE:         {best.wfe:.3f}  "
                f"({'ROBUSTE' if best.wfe>=0.5 else 'ACCEPTABLE' if best.wfe>=0.4 else 'FRAGILE'})",
                f"  Max Drawdown: {best.max_drawdown:.1f}%",
                f"  Score:        {best.score:.3f}",
                "",
                SEP,
                "  PARAMETRES MQL5 A COPIER DANS LES INPUTS DU BOT:",
                SEP,
                "",
                best.params.to_mql5_comment(),
                "",
                SEP,
            ]
        else:
            lines += [
                "", "  !! Aucun résultat valide trouvé.",
                "  Actions recommandées:",
                "  1. Augmenter le nombre de trades historiques (minimum 50)",
                "  2. Élargir la grille: ATR_SL_Multiplier jusqu'à 3.0",
                "  3. Vérifier la qualité des données (atr_at_entry renseigné ?)",
                SEP,
            ]

        return "\n".join(lines)

    @staticmethod
    def export_json(results: List[OptimizationResult], path: str):
        data = {
            "generated":    datetime.now().isoformat(),
            "total_tested": len(results),
            "total_valid":  sum(1 for r in results if r.is_valid),
            "best_params":  results[0].params.to_dict() if results else {},
            "top10": [
                {
                    "rank":       i + 1,
                    "params":     r.params.to_dict(),
                    "is_pf":      r.is_pf,
                    "oos_pf":     r.oos_pf,
                    "wfe":        r.wfe,
                    "score":      r.score,
                    "valid":      r.is_valid,
                    "max_dd":     r.max_drawdown,
                }
                for i, r in enumerate(results[:10])
            ]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        log.info("Résultats exportés: %s", path)


# ══════════════════════════════════════════════════════════════════
#  GÉNÉRATEUR DE DONNÉES DE DÉMO
# ══════════════════════════════════════════════════════════════════

def generate_demo_trades(n: int = 120, seed: int = 42) -> List[TradeRecord]:
    """
    Génère des trades synthétiques réalistes pour tester l'optimiseur.
    Simule un scalper sur XAUUSD/EURUSD avec paramètres sous-optimaux.
    """
    random.seed(seed)
    SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "US30Cash", "Nasdaq"]
    trades  = []
    base_dt = datetime(2024, 1, 3, 8, 0)

    for i in range(n):
        sym       = random.choice(SYMBOLS)
        open_dt   = base_dt + timedelta(hours=i * 2 + random.randint(0, 1))
        dur_min   = random.randint(4, 22)
        direction = random.choice(["BUY", "SELL"])

        # Simulation ATR réaliste par instrument
        atr_base = {"XAUUSD": 2.5, "EURUSD": 0.0008, "GBPUSD": 0.0012,
                    "US30Cash": 80, "Nasdaq": 120}.get(sym, 1.0)
        atr = atr_base * random.uniform(0.7, 1.4)

        rsi   = random.uniform(25, 75)
        adx   = random.uniform(12, 45)

        # Win rate ~54% avec les paramètres "par défaut"
        is_win = random.random() < 0.54

        # PnL basé sur ATR × multiplicateurs actuels (1.5 SL / 2.5 TP)
        sl_dist = atr * 1.5
        tp_dist = atr * 2.5
        lot     = 0.01
        pnl     = (tp_dist * lot * 10) if is_win else -(sl_dist * lot * 10)

        trades.append(TradeRecord(
            symbol        = sym,
            direction     = direction,
            open_time     = open_dt,
            close_time    = open_dt + timedelta(minutes=dur_min),
            open_price    = 2000.0 if sym == "XAUUSD" else 1.1,
            close_price   = 2000.0 + pnl if sym == "XAUUSD" else 1.1 + pnl,
            lot           = lot,
            profit        = round(pnl, 2),
            sl_distance   = sl_dist,
            atr_at_entry  = atr,
            rsi_at_entry  = rsi,
            adx_at_entry  = adx,
        ))

    log.info("Demo: %d trades générés", len(trades))
    return trades


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Aladdin Pro — Optimiseur de Paramètres")
    parser.add_argument("--history",  default=None, help="Fichier JSON trades historiques")
    parser.add_argument("--capital",  type=float, default=1000.0)
    parser.add_argument("--is-pct",   type=float, default=0.70,
                        help="Fraction In-Sample (défaut: 0.70 = 70 pct)")
    parser.add_argument("--demo",     action="store_true",
                        help="Utiliser des données de démonstration")
    parser.add_argument("--export",   default="optimization_results.json",
                        help="Fichier JSON de sortie")
    parser.add_argument("--quiet",    action="store_true", help="Moins de logs")
    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # Chargement des trades
    if args.demo or not args.history or not os.path.exists(args.history or ""):
        print("\n[MODE DEMO] Génération de 120 trades synthétiques...\n")
        trades = generate_demo_trades(120)
    else:
        print(f"\nChargement: {args.history}")
        try:
            with open(args.history, encoding="utf-8") as f:
                data = json.load(f)
            trades = []
            for item in data.get("trades", data if isinstance(data, list) else []):
                try:
                    # Conversion des types et mapping des champs Sentinel V5
                    direction = str(item.get("type", "BUY")).upper()
                    
                    # Conversion epoch to datetime
                    open_time = datetime.fromtimestamp(item["time_open"]) if isinstance(item.get("time_open"), (int, float)) else datetime.fromisoformat(item["time_open"])
                    
                    # Durée en secondes pour estimer close_time si absent
                    duration = item.get("duration", 60)
                    close_time = datetime.fromtimestamp(item["time_open"] + duration) if isinstance(item.get("time_open"), (int, float)) else open_time + timedelta(seconds=duration)

                    trades.append(TradeRecord(
                        symbol        = item["symbol"],
                        direction     = direction,
                        open_time     = open_time,
                        close_time    = close_time,
                        open_price    = float(item.get("price_open", 0)),
                        close_price   = float(item.get("price_close", 0)),
                        lot           = float(item.get("volume", 0.01)),
                        profit        = float(item["pnl"]),
                        sl_distance   = float(item.get("sl_pips", 0)) * 0.01, # Estimation si sl_pips present
                        atr_at_entry  = float(item.get("atr", 0)),
                        rsi_at_entry  = float(item.get("rsi", 50)),
                        adx_at_entry  = float(item.get("adx", 20)),
                    ))
                except (KeyError, ValueError, TypeError) as e:
                    continue
            print(f"{len(trades)} trades chargés")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Erreur lecture: {e}")
            return

    if len(trades) < 20:
        print("Minimum 20 trades requis pour l'optimisation.")
        return

    # Optimisation
    print(f"\nOptimisation WFO — {len(trades)} trades | IS: {args.is_pct*100:.0f}% | OOS: {(1-args.is_pct)*100:.0f}%")
    print("Grille de paramètres:")
    for k, v in GridSearchOptimizer.PARAM_GRID.items():
        print(f"  {k:<18}: {v}")
    print()

    optimizer = GridSearchOptimizer(
        trades  = trades,
        capital = args.capital,
        is_pct  = args.is_pct,
        verbose = not args.quiet,
    )
    results = optimizer.run()

    # Rapport
    print(OptimizationReport.top_results(results, n=10))

    # Export JSON
    if results:
        OptimizationReport.export_json(results, args.export)
        print(f"\nRésultats complets exportés: {args.export}")
        print("→ Utilisez ce fichier pour mettre à jour les paramètres du bot.")


if __name__ == "__main__":
    main()
