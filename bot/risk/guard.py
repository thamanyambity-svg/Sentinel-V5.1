from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger("RISK_GUARD")

class MultiLevelKillSwitch:
    """
    MultiLevelKillSwitch: Gestionnaire de drawdown institutionnel.
    Protège contre les pertes journalières, de session et les grappes de pertes (clusters).
    """

    def __init__(self, daily_limit=0.02, session_limit=0.03, global_limit=0.10):
        self.daily_limit_pct = daily_limit    # 2%
        self.session_limit_pct = session_limit # 3%
        self.global_limit_pct = global_limit  # 10%
        
        self.session_start_time = datetime.now(timezone.utc)
        self.regime_losses = {} # cluster guard per regime

    def is_allowed(self, trades, stats, current_regime):
        """
        Vérification globale de toutes les couches de sécurité.
        """
        if not trades:
            return True, "Initial state - Allowed"

        # 1. HARD STOP (Global Drawdown >= 9.5%)
        equity_dd = stats.get("global_drawdown", 0)
        if equity_dd >= 0.095:
            return False, "HARD STOP: Global Drawdown threshold reached (9.5%)"

        # 2. Daily Kill-Switch (24h > 2%)
        if self._is_daily_limit_reached(trades):
            return False, "DAILY HALT: 2% loss reached in 24h"

        # 3. Session Kill-Switch (Session > 3%)
        if self._is_session_limit_reached(trades):
            return False, "SESSION HALT: 3% loss reached this session"

        # 4. Cluster-Loss Guard
        if self.is_cluster_limit_reached(trades, current_regime):
            return False, f"CLUSTER GUARD: Too many consecutive losses in {current_regime}"

        # 5. Consecutive SL Overall (Cooldown 12h)
        if self._is_cooldown_active(trades):
            return False, "COOLDOWN: 4 consecutive SL - Waiting 12h"

        return True, "Risk limits OK"

    def _is_daily_limit_reached(self, trades):
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        day_pnl = sum(t["pnl"] for t in trades if self._parse_ts(t["timestamp"]) > yesterday)
        # Note: simplistic PnL sum, should ideally be % of start-of-day balance
        return day_pnl < -2.0 # Placeholder for 2% calculation

    def _is_session_limit_reached(self, trades):
        session_pnl = sum(t["pnl"] for t in trades if self._parse_ts(t["timestamp"]) > self.session_start_time)
        return session_pnl < -3.0 # Placeholder

    def is_cluster_limit_reached(self, trades, regime):
        """
        Halt if 3 consecutive losses in the same regime.
        """
        regime_trades = [t for t in trades if t.get("regime") == regime]
        if len(regime_trades) < 3:
            return False
        
        last_three = regime_trades[-3:]
        if all(t["pnl"] < 0 for t in last_three):
            logger.warning(f"⚠️ Cluster loss detected in {regime}")
            return True
        return False

    def _is_cooldown_active(self, trades):
        if len(trades) < 4:
            return False
        
        last_four = trades[-4:]
        if all(t["pnl"] < 0 for t in last_four):
            last_sl_time = self._parse_ts(last_four[-1]["timestamp"])
            if datetime.now(timezone.utc) - last_sl_time < timedelta(hours=12):
                return True
        return False

    def _parse_ts(self, ts):
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts)
            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        elif isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return ts
