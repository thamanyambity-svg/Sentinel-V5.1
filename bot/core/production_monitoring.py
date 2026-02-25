import time
from typing import Dict, List, Optional
import logging

# Email libs (simulated for now)
# import smtplib
# from email.mime.text import MIMEText

class ProductionMonitor:
    def __init__(self):
        self.logger = logging.getLogger("PROD_MONITOR")
        self.alert_cooldown = {}  # Store timestamp of last alert per type
        self.cooldown_time = 300  # 5 minutes
        
        # Configurable Thresholds
        self.max_drawdown_limit = 20.0 # %
        self.max_daily_loss = 1000.0   # Currency
        self.max_daily_trades = 1000   # Frequency cap

        print("🚨 Production Monitor Initialized")

    def check_critical_metrics(self, metrics: Dict) -> List[str]:
        """Vérifie si les métriques dépassent les seuils critiques."""
        alerts = []
        
        # 1. Drawdown Check
        dd = metrics.get('max_drawdown', 0.0)
        if dd > self.max_drawdown_limit:
            alerts.append(f"CRITICAL: Max drawdown {dd}% > {self.max_drawdown_limit}%")
        
        # 2. Frequent Trading Check (Runaway bot protection)
        trades = metrics.get('daily_trades', 0)
        if trades > self.max_daily_trades:
            alerts.append(f"WARNING: High trading frequency ({trades} > {self.max_daily_trades})")
        
        # 3. Daily Loss Check
        pnl = metrics.get('daily_pnl', 0.0)
        if pnl < -self.max_daily_loss:
            alerts.append(f"CRITICAL: Daily loss {pnl} < -{self.max_daily_loss}")

        return alerts
    
    def send_email_alert(self, alert_msg: str):
        """Simulate sending an email alert."""
        # Check cooldown
        last_sent = self.alert_cooldown.get(alert_msg, 0)
        if time.time() - last_sent < self.cooldown_time:
            # Suppress alert
            return

        self.alert_cooldown[alert_msg] = time.time()
        
        # Simulation
        print(f"📧 [EMAIL SENT] Subject: 🚨 Sentinel Alert\nBody: {alert_msg}")
        self.logger.warning(f"ALERT SENT: {alert_msg}")

        # Real Implementation Stub:
        # msg = MIMEText(f"Sentinel Alert: {alert_msg}")
        # msg['Subject'] = f"🚨 Sentinel Alert"
        # msg['From'] = "bot@sentinel.com"
        # msg['To'] = "admin@sentinel.com"
        # send_via_smtp(msg)

    def continuous_monitoring_loop(self, metrics_provider_func, interval=60):
        """Monitor loop to be run in a separate thread."""
        while True:
            try:
                # Fetch metrics from the provider (e.g. DB or shared memory)
                metrics = metrics_provider_func()
                
                alerts = self.check_critical_metrics(metrics)
                for alert in alerts:
                    self.send_email_alert(alert)
                
            except Exception as e:
                print(f"❌ Monitoring loop error: {e}")
            
            time.sleep(interval)

if __name__ == "__main__":
    # Test
    mon = ProductionMonitor()
    
    # Critical metrics
    test_metrics_bad = {
        'max_drawdown': 25.0,
        'daily_trades': 1500,
        'daily_pnl': -2000.0
    }
    
    print("\nChecking Bad Metrics:")
    alerts = mon.check_critical_metrics(test_metrics_bad)
    for a in alerts:
        mon.send_email_alert(a)
    
    print("\nChecking Cooldown (Should be empty):")
    # Immediate retry should be blocked by cooldown
    for a in alerts:
        mon.send_email_alert(a)
