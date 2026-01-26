
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel
import os
import uvicorn
import json
import time

# Configuration
SECRET_TOKEN = os.getenv("WEBHOOK_SECRET", "changeme_123")
SIGNAL_DIR = "bot/signals_queue"

app = FastAPI()

# Ensure signal directory exists
os.makedirs(SIGNAL_DIR, exist_ok=True)

class TradingViewSignal(BaseModel):
    asset: str           # e.g., "1HZ10V" or "BTCUSD"
    action: str          # "BUY" or "SELL"
    # Optional fields
    sl: float = 0.0      # Explicit SL price
    tp: float = 0.0      # Explicit TP price
    risk: str = "NORMAL" # "HIGH", "Sniper"
    comment: str = ""

@app.post("/webhook")
async def receive_signal(signal: TradingViewSignal, x_webhook_secret: str = Header(None)):
    # 1. Security Check
    if x_webhook_secret != SECRET_TOKEN:
        # Also check query param if header missing (optional flexibility)
        raise HTTPException(status_code=401, detail="Invalid Secret Token")

    # 2. Process Signal
    timestamp = int(time.time() * 1000)
    filename = f"{SIGNAL_DIR}/tv_signal_{timestamp}.json"
    
    payload = signal.dict()
    payload["timestamp"] = timestamp
    payload["source"] = "TradingView"

    # 3. Write to Queue (File)
    with open(filename, "w") as f:
        json.dump(payload, f)

    print(f"📨 WEBHOOK: Signal received for {signal.asset} -> {filename}")
    return {"status": "ok", "id": timestamp}

@app.get("/health")
def health_check():
    return {"status": "active"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
