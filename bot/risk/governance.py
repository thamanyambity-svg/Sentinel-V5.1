import json
import os
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger("GOVERNANCE")

DATA_FILE = "bot/data/daily_stats.json"

class CircuitBreaker:
    def __init__(self, max_loss=-300.0, max_profit=1000.0, cooldown_minutes=30):
        self.max_loss = max_loss
        self.max_profit = max_profit
        self.cooldown_seconds = cooldown_minutes * 60
        self.consecutive_losses = 0
        self.last_loss_time = 0
        self.state = self._load_state()

    def _get_today_str(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load_state(self):
        today = self._get_today_str()
        default_state = {
            "date": today,
            "start_balance": None,
            "current_pnl": 0.0,
            "trades_count": 0,
            "wins": 0,
            "losses": 0
        }
        
        if not os.path.exists(DATA_FILE):
            return default_state

        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                if data.get("date") != today:
                    return default_state # New Day, New Me
                return data
        except Exception:
            return default_state

    def _save_state(self):
        # Ensure dir exists
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(self.state, f, indent=4)

    def update(self, current_balance):
        if current_balance is None or current_balance <= 0:
            return

        # Initialize Start Balance on first run of the day
        if self.state["start_balance"] is None:
            self.state["start_balance"] = current_balance
            logger.info(f"💾 Governance: Daily Start Balance set to {current_balance}$")
            self._save_state()
            return

        # Update PnL
        start_bal = self.state["start_balance"]
        pnl = current_balance - start_bal
        
        # Detect Result (simplified: if PnL changed significanly)
        #Ideally we want per-trade detection, but for Daily Limit, absolute PnL is enough.
        
        self.state["current_pnl"] = round(pnl, 2)
        self._save_state()

    def register_trade_result(self, pnl):
        """ Can be called if we know exact trade outcome """
        if pnl < 0:
            self.consecutive_losses += 1
            self.last_loss_time = time.time()
            self.state["losses"] += 1
            logger.warning(f"📉 Governance: Loss detected ({pnl}$). Streak: {self.consecutive_losses}")
        else:
            self.consecutive_losses = 0
            self.state["wins"] += 1
            
        self.state["trades_count"] += 1
        self._save_state()

    def can_trade(self):
        # 0. Daily Rollover Check
        today = self._get_today_str()
        if self.state["date"] != today:
            logger.info(f"📅 New Day Detected ({today}). Resetting Governance State.")
            self.state = {
                "date": today,
                "start_balance": None,
                "current_pnl": 0.0,
                "trades_count": 0,
                "wins": 0,
                "losses": 0
            }
            self._save_state()

        # 1. Circuit Breaker (Financial)
        pnl = self.state["current_pnl"]
        
        if pnl <= self.max_loss:
            logger.warning(f"🛑 CIRCUIT BREAKER TRIPPED: Daily Loss {pnl}$ exceeds limit {self.max_loss}$")
            return False
            
        if pnl >= self.max_profit:
            logger.warning(f"🎉 TARGET REACHED: Daily Profit {pnl}$ hits target {self.max_profit}$")
            return False

        # 2. Cool Down (Psychological)
        # If 2 consecutive losses, wait X mins
        if self.consecutive_losses >= 2:
            elapsed = time.time() - self.last_loss_time
            remaining = self.cooldown_seconds - elapsed
            if remaining > 0:
                logger.info(f"🧊 COOL DOWN ACTIVE: Waiting {int(remaining/60)}m {int(remaining%60)}s after losses.")
                return False
            else:
                # Reset streak after cooldown
                self.consecutive_losses = 0

        return True

    def get_status(self):
        return f"PnL: {self.state['current_pnl']}$ | Streak: {self.consecutive_losses}L"
