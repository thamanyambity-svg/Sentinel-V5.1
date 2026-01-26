import time
from bot.config.runtime import set_active_broker
from bot.monitor.health import get_health

set_active_broker("deriv")
print("H0:", get_health())
time.sleep(6)
print("H1:", get_health())
