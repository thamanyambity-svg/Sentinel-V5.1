from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import asyncio
import os
from bot.data.database import DatabaseManager
from bot.core.monitor import ResourceMonitor

app = FastAPI(title="Sentinel Admin API", version="5.2")

# Dependencies
# In a real app, these would be initialized singly and passed via dependency injection
db_manager = DatabaseManager() 
monitor = ResourceMonitor()

class TradeRequest(BaseModel):
    symbol: str
    direction: str
    volume: float
    duration: str = "1m"

class BotStatus(BaseModel):
    status: str
    uptime_hours: float
    cpu_usage: float
    memory_usage: float
    active_positions: int

@app.get("/")
async def root():
    return {"message": "Sentinel V5.2 API is Online"}

@app.get("/status", response_model=BotStatus)
async def get_status():
    """Statut actuel du bot"""
    try:
        mem, cpu = monitor.check_resources()
        # Mock uptime for now, or fetch from a shared state
        return {
            "status": "running",
            "uptime_hours": 0.0, # detailed stats would come from shared memory or DB
            "cpu_usage": cpu,
            "memory_usage": mem,
            "active_positions": 0 # Would fetch from bot_state.json or DB
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trades/execute")
async def execute_trade(trade: TradeRequest):
    """Exécute un trade manuel (vers ZMQ Bridge par exemple)"""
    # Here we would send a command to the ZMQ bridge
    # For now, we mock the success
    print(f"📥 API Command: Execute {trade.direction} on {trade.symbol}")
    return {"status": "queued", "trade": trade}

@app.get("/performance")
async def get_performance(period: str = "all"):
    """Performance globale"""
    stats = db_manager.get_performance_summary()
    return stats

def start_api():
    """Helper to run via python script"""
    uvicorn.run(app, host="0.0.0.0", port=8080)

if __name__ == "__main__":
    start_api()
