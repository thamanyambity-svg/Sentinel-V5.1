import time
import logging
from typing import Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

# Get logger
logger = logging.getLogger("SENTINEL_MONITOR")

class ResourceMonitor:
    def __init__(self, max_memory_percent=80, max_cpu_percent=90):
        self.max_memory = max_memory_percent
        self.max_cpu = max_cpu_percent
        if not PSUTIL_AVAILABLE:
            logger.warning("⚠️ psutil not found. Resource monitoring is disabled. Install with `pip install psutil`.")
    
    def check_resources(self) -> Tuple[float, float]:
        """
        Checks current system resource usage.
        Returns: (memory_percent, cpu_percent)
        """
        if not PSUTIL_AVAILABLE:
            return 0.0, 0.0

        try:
            # Memory usage
            memory = psutil.virtual_memory().percent
            
            # CPU usage (blocking for 1s to get accurate reading)
            cpu = psutil.cpu_percent(interval=1)
            
            if memory > self.max_memory:
                logger.warning(f"⚠️  ALERTE RAM : {memory}% used (Threshold: {self.max_memory}%)")
            
            if cpu > self.max_cpu:
                logger.warning(f"⚠️  ALERTE CPU : {cpu}% used (Threshold: {self.max_cpu}%)")
            
            return memory, cpu
            
        except Exception as e:
            logger.error(f"❌ Monitor Error: {e}")
            return 0.0, 0.0

    def get_disk_usage(self, path=".") -> float:
        """Checks disk usage percentage for the given path."""
        if not PSUTIL_AVAILABLE:
            return 0.0
            
        try:
            return psutil.disk_usage(path).percent
        except Exception:
            return 0.0

    def comprehensive_health_check(self) -> dict:
        """
        Performs a full system health check.
        Returns a dict with status of each component.
        """
        mem, cpu = self.check_resources()
        disk = self.get_disk_usage()
        
        checks = {
            'cpu_ok': cpu < self.max_cpu,
            'memory_ok': mem < self.max_memory,
            'disk_ok': disk < 90, # 90% threshold for disk
            'cpu_usage': cpu,
            'memory_usage': mem,
            'disk_usage': disk
        }
        
        # Log health summary
        status = "✅ HEALTHY" if all([checks['cpu_ok'], checks['memory_ok'], checks['disk_ok']]) else "⚠️ UNHEALTHY"
        logger.info(f"{status} | CPU: {cpu}% | RAM: {mem}% | Disk: {disk}%")
        
        return checks
