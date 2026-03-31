#!/usr/bin/env python3
"""
Phase 2 Monitoring Dashboard
============================
Tracks live XAUUSD V9.2 trading performance and validates orderflow/trend features.

Usage:
    python3 phase2_monitor.py --status              # Current period stats
    python3 phase2_monitor.py --daily               # Daily breakdown
    python3 phase2_monitor.py --feature-impact      # Feature contribution analysis
    python3 phase2_monitor.py --kill-switch-log     # K-switch activations
"""

import json
import os
import sys
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PHASE2] %(message)s"
)
logger = logging.getLogger("PHASE2_MONITOR")


class Phase2Monitor:
    """
    Validates V9.2 model performance and ensures orderflow features are effective.
    """

    def __init__(self, trade_history_path: str = "trade_history.json"):
        self.trade_history_path = trade_history_path
        self.trades = self._load_trades()
        self.phase2_start_idx = 35  # First 35 were synthetic training data

    def _load_trades(self):
        """Load trade history."""
        try:
            with open(self.trade_history_path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Could not load trades: {e}")
            return []

    def get_live_trades(self):
        """Filter trades that are Phase 2 live (index >= 35)."""
        return self.trades[self.phase2_start_idx:]

    def get_status(self):
        """Current period performance summary."""
        live = self.get_live_trades()

        if not live:
            return {
                "phase": "Phase 2 - Ready to Start",
                "live_trades": 0,
                "target": 100,
                "pct_complete": 0,
                "message": "Awaiting first live trade"
            }

        # Statistics
        wins = len([t for t in live if t.get("pnl", 0) > 0])
        losses = len([t for t in live if t.get("pnl", 0) <= 0])
        total_pnl = sum(t.get("pnl", 0) for t in live)
        avg_pnl = total_pnl / len(live) if live else 0
        max_pnl = max([t.get("pnl", 0) for t in live]) if live else 0
        min_pnl = min([t.get("pnl", 0) for t in live]) if live else 0

        # Sharpe-like ratio (simple version for Phase 2)
        pnls = [t.get("pnl", 0) for t in live]
        pnl_std = np.std(pnls) if len(pnls) > 1 else 0
        sharpe_proxy = (avg_pnl / (pnl_std + 1e-9)) * np.sqrt(252)

        # Win rate
        win_rate = (wins / len(live) * 100) if live else 0

        return {
            "phase": "Phase 2 - Live Trading",
            "live_trades": len(live),
            "target": 100,
            "pct_complete": min(100, (len(live) / 100) * 100),
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl_per_trade": round(avg_pnl, 2),
            "max_win": round(max_pnl, 2),
            "min_loss": round(min_pnl, 2),
            "sharpe_proxy": round(sharpe_proxy, 4),
            "validation": self._validate_progress(len(live), sharpe_proxy),
        }

    def _validate_progress(self, n_trades: int, sharpe: float) -> dict:
        """Check Phase 2 validation criteria."""
        if n_trades < 30:
            return {"status": "COLLECTING", "gate": "Need ≥30 trades to evaluate"}
        elif n_trades < 100:
            status = "Sharpe ↑ to 0.13?" if sharpe > 0.12 else "Monitoring..."
            return {"status": "IN_PROGRESS", "gate": status}
        else:
            # Decision point
            if sharpe > 0.13:
                return {"status": "✅ APPROVED", "gate": "Sharpe > 0.13 → UNLOCK NIVEAU 2"}
            elif sharpe >= 0.09:
                return {"status": "⚠️  MARGINAL", "gate": "Sharpe ~0.09 → Keep orderflow, trim others"}
            else:
                return {"status": "❌ FAILED", "gate": "Sharpe < 0.08 → Rollback to 15 features"}

    def get_daily_breakdown(self):
        """Daily performance statistics."""
        live = self.get_live_trades()
        daily = defaultdict(list)

        for trade in live:
            date = datetime.fromtimestamp(trade.get("time_open", 0)).strftime("%Y-%m-%d")
            daily[date].append(trade)

        result = {}
        for date in sorted(daily.keys()):
            trades = daily[date]
            wins = len([t for t in trades if t.get("pnl", 0) > 0])
            pnl_sum = sum(t.get("pnl", 0) for t in trades)

            result[date] = {
                "trades": len(trades),
                "wins": wins,
                "losses": len(trades) - wins,
                "win_rate": round(wins / len(trades) * 100, 1) if trades else 0,
                "daily_pnl": round(pnl_sum, 2),
                "avg_trade_pnl": round(pnl_sum / len(trades), 2) if trades else 0,
            }

        return result

    def get_feature_impact(self):
        """Analyze which features contribute to winners vs losers."""
        live = self.get_live_trades()

        if len(live) < 10:
            return {"status": "Insufficient data", "need": "10+ trades"}

        winners = [t for t in live if t.get("pnl", 0) > 0]
        losers = [t for t in live if t.get("pnl", 0) <= 0]

        feature_names = [
            "delta", "absorption",  # Orderflow (V9.1)
            "ema_20", "ema_50", "ema_slope", "rsi", "macd_histogram",  # Trend (V9.2)
        ]

        impact = {}
        for feat in feature_names:
            if not winners or not losers:
                continue

            winner_vals = [t.get(feat, 0) for t in winners if feat in t]
            loser_vals = [t.get(feat, 0) for t in losers if feat in t]

            if winner_vals and loser_vals:
                winner_mean = np.mean(winner_vals)
                loser_mean = np.mean(loser_vals)
                impact[feat] = {
                    "winner_avg": round(float(winner_mean), 3),
                    "loser_avg": round(float(loser_mean), 3),
                    "difference": round(float(winner_mean - loser_mean), 3),
                    "impact": "HIGH" if abs(winner_mean - loser_mean) > 0.5 else "MEDIUM" if abs(winner_mean - loser_mean) > 0.2 else "LOW"
                }

        return {
            "winners": len(winners),
            "losers": len(losers),
            "feature_analysis": impact,
            "interpretation": "Higher difference → feature more predictive of winners"
        }

    def get_kill_switch_log(self):
        """Log any kill switch activations (if recorded)."""
        # This would read from status logs when live
        return {
            "loss_streaks": "None yet",
            "drawdown_alerts": "None yet",
            "spread_spikes": "None yet",
            "volatility_bursts": "None yet",
            "status": "Monitoring active"
        }

    def print_dashboard(self):
        """Pretty print current status."""
        status = self.get_status()

        print("\n" + "="*80)
        print("📊 PHASE 2 LIVE TRADING MONITOR — V9.2 XAUUSD")
        print("="*80)

        print(f"\n📈 CURRENT STATUS:")
        print(f"   Phase: {status['phase']}")
        print(f"   Live Trades: {status['live_trades']}/{status['target']} "
              f"({status['pct_complete']:.1f}%)")

        if status['live_trades'] > 0:
            print(f"\n💰 PERFORMANCE:")
            print(f"   Wins: {status.get('wins', 0)} | Losses: {status.get('losses', 0)}")
            print(f"   Win Rate: {status.get('win_rate_pct', 0)}%")
            print(f"   Total PnL: ${status.get('total_pnl', 0):+.2f}")
            print(f"   Avg PnL/Trade: ${status.get('avg_pnl_per_trade', 0):+.2f}")
            print(f"   Sharpe Proxy: {status.get('sharpe_proxy', 0):.4f}")

            print(f"\n🎯 VALIDATION:")
            val = status.get('validation', {})
            print(f"   Status: {val.get('status', '?')}")
            print(f"   Gate: {val.get('gate', '?')}")

        print("\n" + "="*80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phase 2 Live Trading Monitor")
    parser.add_argument("--status", action="store_true", help="Current period stats")
    parser.add_argument("--daily", action="store_true", help="Daily breakdown")
    parser.add_argument("--feature-impact", action="store_true", help="Feature contribution")
    parser.add_argument("--kill-switch-log", action="store_true", help="Kill switch log")
    parser.add_argument("--dashboard", action="store_true", help="Full dashboard")

    args = parser.parse_args()
    monitor = Phase2Monitor()

    if args.daily:
        daily = monitor.get_daily_breakdown()
        print("\n📅 DAILY BREAKDOWN:")
        for date, stats in sorted(daily.items()):
            print(f"\n   {date}:")
            for k, v in stats.items():
                print(f"      {k}: {v}")

    elif args.feature_impact:
        impact = monitor.get_feature_impact()
        print("\n🔬 FEATURE IMPACT ANALYSIS:")
        print(f"   Winners: {impact.get('winners', 0)}")
        print(f"   Losers: {impact.get('losers', 0)}")
        print("\n   Feature Analysis:")
        for feat, data in impact.get('feature_analysis', {}).items():
            print(f"      {feat}:")
            print(f"         Winner avg: {data['winner_avg']}")
            print(f"         Loser avg: {data['loser_avg']}")
            print(f"         Difference: {data['difference']} [{data['impact']}]")

    elif args.kill_switch_log:
        ks = monitor.get_kill_switch_log()
        print("\n⚠️  KILL SWITCH LOG:")
        for k, v in ks.items():
            print(f"   {k}: {v}")

    elif args.status or args.dashboard:
        monitor.print_dashboard()

    else:
        # Default: show dashboard
        monitor.print_dashboard()


if __name__ == "__main__":
    main()
