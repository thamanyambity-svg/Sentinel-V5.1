import time
from bot.workflow.orchestrator import run_orchestrator
from bot.state.runtime import mark_heartbeat, mark_execution


def start_scheduler(interval=5):
    print("🫀 Scheduler actif (heartbeat)")

    while True:
        try:
            mark_heartbeat()
            result = run_orchestrator()
            if result:
                mark_execution()
                print("✅ Trade exécuté :", result)
        except Exception as e:
            print("❌ Scheduler error :", e)

        time.sleep(interval)
