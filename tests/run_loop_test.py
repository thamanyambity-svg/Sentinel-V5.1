import time
from bot.workflow.orchestrator import run_orchestrator

for i in range(5):
    res = run_orchestrator()
    print(f"[{i}] →", res)
    time.sleep(1)
