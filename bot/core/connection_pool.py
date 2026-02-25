import asyncio
import aiohttp
from typing import Dict, Optional, Any

class ConnectionPool:
    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self.session: Optional[aiohttp.ClientSession] = None
        self.connector: Optional[aiohttp.TCPConnector] = None
        # Semaphore not strictly needed if using TCPConnector limit, but good for explicit concurrency control if needed elsewhere
        self.semaphore = asyncio.Semaphore(max_connections) 
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self):
        if not self.session:
            # TCPConnector limits total connections
            self.connector = aiohttp.TCPConnector(limit=self.max_connections)
            self.session = aiohttp.ClientSession(connector=self.connector)
            print("🌐 Connection Pool Started")

    async def stop(self):
        if self.session:
            await self.session.close()
            self.session = None
            print("🛑 Connection Pool Stopped")

    async def fetch_json(self, url: str, params: Dict = None, method: str = "GET", json_body: Dict = None) -> Any:
        """Fetches JSON data using the shared pool."""
        if not self.session:
            await self.start()
            
        async with self.semaphore:
            try:
                if method == "GET":
                    async with self.session.get(url, params=params) as response:
                        response.raise_for_status()
                        return await response.json()
                elif method == "POST":
                    async with self.session.post(url, json=json_body) as response:
                        response.raise_for_status()
                        return await response.json()
            except Exception as e:
                print(f"❌ ConnectionPool Error ({url}): {e}")
                return None
