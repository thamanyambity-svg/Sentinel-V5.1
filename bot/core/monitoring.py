from prometheus_client import start_http_server, Counter, Gauge, Histogram
import time
import threading

# Robust import for psutil
try:
    import psutil
except ImportError:
    psutil = None

class TradingMetrics:
    def __init__(self, port=8000):
        self.port = port
        
        # Compteurs
        self.trades_total = Counter('sentinel_trades_total', 'Total trades', ['symbol', 'result'])
        self.api_requests = Counter('sentinel_api_requests_total', 'API requests', ['endpoint'])
        self.errors_total = Counter('sentinel_errors_total', 'Total errors', ['type'])
        
        # Jauges
        self.active_positions = Gauge('sentinel_active_positions', 'Current active positions')
        self.account_balance = Gauge('sentinel_account_balance', 'Account balance')
        self.cpu_usage = Gauge('sentinel_cpu_usage_percent', 'CPU usage percent')
        self.memory_usage = Gauge('sentinel_memory_usage_percent', 'Memory usage percent')
        
        # Histogrammes
        self.trade_latency = Histogram('sentinel_trade_latency_seconds', 'Trade execution latency')
        self.api_latency = Histogram('sentinel_api_latency_seconds', 'API response latency')
        
        # Background Updater
        self.running = False
        self.thread = None

    def start(self):
        """Starts Prometheus HTTP server"""
        try:
            start_http_server(self.port)
            self.running = True
            self.thread = threading.Thread(target=self._update_loop, daemon=True)
            self.thread.start()
            print(f"📊 Prometheus Metrics Server started on port {self.port}")
        except Exception as e:
            print(f"❌ Failed to start metrics server: {e}")

    def _update_loop(self):
        """Updates system stats periodically"""
        while self.running:
            try:
                if psutil:
                    self.cpu_usage.set(psutil.cpu_percent())
                    self.memory_usage.set(psutil.virtual_memory().percent)
            except Exception:
                pass
            time.sleep(15)

    def record_trade(self, symbol: str, result: str, latency: float = 0.0):
        self.trades_total.labels(symbol=symbol, result=result).inc()
        if latency > 0:
            self.trade_latency.observe(latency)
            
    def record_error(self, error_type: str):
        self.errors_total.labels(type=error_type).inc()

# Global instance for easy import
metrics = TradingMetrics()

if __name__ == "__main__":
    metrics.start()
    while True:
        metrics.record_trade("EURUSD", "WIN", 0.5)
        time.sleep(5)
