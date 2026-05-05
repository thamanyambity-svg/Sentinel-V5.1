import os
import json
import time
import math
import logging
from datetime import datetime, timedelta
from pathlib import Path
from bot.risk.config import *

logger = logging.getLogger("RISK_OS")

class RiskOS:
    """
    Risk Operating System (Institutional Grade)
    Upgraded with: Explainable Health, Drawdown Breakers, Edge Decay, and Risk-of-Ruin.
    """
    
    def __init__(self, data_path="bot/risk/risk_state.json"):
        self.data_path = data_path
        self.history_file = "trade_history.json"
        self.mt5_dir = Path("/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
        self.status_file = self.mt5_dir / "status.json"
        
        # Internal State
        self.state = {
            "health_score": 100,
            "health_decomposition": {
                "expectancy": 0,
                "regime": 0,
                "exposure": 0,
                "correlation": 0,
                "drawdown": 0
            },
            "regime": "NORMAL",
            "open_risk_pct": 0.0,
            "risk_used_pct": 0.0,
            "expectancy_r": 0.0,
            "win_rate": 0.0,
            "risk_of_ruin": 0.0,
            "kelly_fraction": 0.0,
            "drawdown_r": 0.0,
            "execution_quality": {
                "fill_quality": 100,
                "spread_stress": "low",
                "slippage_drift": "normal"
            },
            "status": "🟢 FULL ON",
            "breakers": {
                "daily_dd": False,
                "edge_decay": False,
                "chaos": False
            },
            "setup_performance": {},
            "last_update": ""
        }
        self.stress_journal = "logs/risk_stress_journal.log"
        os.makedirs("logs", exist_ok=True)

    def log_stress_event(self, event_type, details):
        """Logs critical risk events to the Stress Journal (Prop-Desk Gold Mine)."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{ts}] {event_type.upper()} | {details}\n"
        with open(self.stress_journal, 'a') as f:
            f.write(entry)
        logger.warning(f"⚠️ RISK STRESS EVENT: {event_type} - {details}")
        
    def update(self, bridge_positions=None, account_info=None, atr_ratios=None):
        try:
            # 1. Update Exposure
            self._update_exposure(bridge_positions, account_info)
            
            # 2. Update Expectancy & Edge Decay
            self._update_expectancy()
            
            # 3. Update Regime
            self._update_regime(atr_ratios)
            
            # 4. Check Breakers (Drawdown)
            self._check_breakers()
            
            # 5. Compute Health Score (Explainable)
            self._compute_health()
            
            # 6. Risk of Ruin & Kelly
            self._update_advanced_metrics()
            
            self.state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_state()
            
            return self.state
        except Exception as e:
            logger.error(f"❌ RiskOS Update Error: {e}")
            return self.state

    def _update_exposure(self, positions, account):
        if not positions:
            self.state["open_risk_pct"] = 0.0
            self.state["risk_used_pct"] = 0.0
            return

        total_risk_val = 0.0
        for pos in positions:
            # Assume 0.75% per trade if SL exists
            total_risk_val += BASE_TRADE_RISK_PCT
            
        self.state["open_risk_pct"] = round(total_risk_val * 100, 2)
        self.state["risk_used_pct"] = round((total_risk_val / MAX_TOTAL_RISK_PCT) * 100, 1)

    def _update_expectancy(self):
        if not os.path.exists(self.history_file): return
            
        try:
            with open(self.history_file, 'r') as f:
                history_data = json.load(f)
            
            # Support both list directly or a dict with "trades" key
            history = history_data.get("trades", []) if isinstance(history_data, dict) else history_data
            
            if not history: return
                
            recent = history[-ROLLING_WINDOW:]
            wins = [t for t in recent if float(t.get('pnl', t.get('profit', 0))) > 0]
            
            wr = len(wins) / len(recent) if recent else 0
            self.state["win_rate"] = round(wr * 100, 1)
            
            # Normalized expectancy (placeholder for actual R calculation)
            # In a real system, we'd divide profit by initial risk amount
            edge = (wr * 1.5) - ((1 - wr) * 1.0)
            self.state["expectancy_r"] = round(edge, 2)
            
            # Edge Decay Breaker
            if edge < MIN_ROLLING_EXPECTANCY_R and len(recent) >= 10:
                self.state["breakers"]["edge_decay"] = True
            else:
                self.state["breakers"]["edge_decay"] = False

            # Setup Performance (Mock for now, would parse 'strategy' from history)
            self.state["setup_performance"] = {
                "MEAN_REVERSION": round(edge * 0.8, 2),
                "MOMENTUM": round(edge * 1.2, 2)
            }
            
        except Exception as e:
            logger.warning(f"Expectancy calc failed: {e}")

    def _update_regime(self, atr_ratios):
        if not atr_ratios: return
        avg_ratio = sum(atr_ratios.values()) / len(atr_ratios)
        
        old_chaos = self.state["breakers"]["chaos"]
        
        if avg_ratio < REGIME_DEAD_THRESHOLD: 
            self.state["regime"] = "DEAD"
            self.state["breakers"]["chaos"] = False
        elif avg_ratio > REGIME_CHAOS_THRESHOLD: 
            self.state["regime"] = "CHAOS"
            self.state["breakers"]["chaos"] = True
        else: 
            self.state["regime"] = "NORMAL"
            self.state["breakers"]["chaos"] = False

        if self.state["breakers"]["chaos"] and not old_chaos:
            self.log_stress_event("CHAOS_HALT", f"ATR Ratio {avg_ratio:.2f} exceeded threshold {REGIME_CHAOS_THRESHOLD}")

    def _check_breakers(self):
        # Daily Drawdown (Simple mock, should check daily PnL)
        # self.state["drawdown_r"] = current_daily_loss / risk_unit
        old_dd = self.state["breakers"]["daily_dd"]
        
        if self.state["drawdown_r"] > DAILY_DD_HALT_R:
            self.state["breakers"]["daily_dd"] = True
            if not old_dd:
                self.log_stress_event("DD_BREAKER", f"Daily Drawdown {self.state['drawdown_r']}R reached")
        else:
            self.state["breakers"]["daily_dd"] = False
            
        # Overall Status
        if self.state["breakers"]["chaos"]: self.state["status"] = "🔴 NO TRADE (CHAOS)"
        elif self.state["breakers"]["daily_dd"]: self.state["status"] = "🔴 NO TRADE (DAILY DD)"
        elif self.state["breakers"]["edge_decay"]: self.state["status"] = "🟡 CAUTION (EDGE DECAY)"
        elif self.state["regime"] == "DEAD": self.state["status"] = "🟡 NO TRADE (DEAD)"
        else: self.state["status"] = "🟢 FULL ON"

    def _compute_health(self):
        decomp = self.state["health_decomposition"]
        
        # 1. Expectancy (30 pts)
        e = self.state["expectancy_r"]
        decomp["expectancy"] = HEALTH_WEIGHTS["expectancy"] if e > 0.2 else (20 if e > 0 else 5)
        
        # 2. Regime (25 pts)
        r = self.state["regime"]
        decomp["regime"] = HEALTH_WEIGHTS["regime"] if r == "NORMAL" else (15 if r == "EXPANSION" else 5)
        
        # 3. Exposure (20 pts)
        exp = self.state["open_risk_pct"]
        decomp["exposure"] = HEALTH_WEIGHTS["exposure"] if exp < 1.5 else (10 if exp < 2.0 else 0)
        
        # 4. Correlation (15 pts - Mock)
        decomp["correlation"] = 15 # Placeholder
        
        # 5. Drawdown (10 pts)
        dd = self.state["drawdown_r"]
        decomp["drawdown"] = HEALTH_WEIGHTS["drawdown"] if dd < 1.0 else (5 if dd < 2.0 else 0)
        
        self.state["health_score"] = sum(decomp.values())

    def _update_advanced_metrics(self):
        # Risk of Ruin (Simplified)
        # RoR = ((1-edge)/(1+edge))^units_to_ruin
        edge = max(0.01, self.state["expectancy_r"] / 1.5) # Normalized 0-1
        units = 50 # 50R stop out
        self.state["risk_of_ruin"] = round(pow((1 - edge)/(1 + edge), units) * 100, 2)
        
        # Kelly Fraction (f = edge / odds)
        # Assuming odds 1.5:1
        self.state["kelly_fraction"] = round(edge / 1.5, 3)

        # Execution Quality Mock
        # In real usage, this would compare entry_price vs requested_price
        self.state["execution_quality"] = {
            "fill_quality": 95 if self.state["regime"] == "NORMAL" else 70,
            "spread_stress": "high" if self.state["regime"] == "CHAOS" else "low",
            "slippage_drift": "normal"
        }

    def _save_state(self):
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        with open(self.data_path, 'w') as f:
            json.dump(self.state, f, indent=4)

risk_os = RiskOS()
