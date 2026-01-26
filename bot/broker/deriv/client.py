import asyncio
import json
import logging
import websockets
import os
import ssl
import certifi

logger = logging.getLogger("DERIV")

class DerivClient:
    def __init__(self):
        self.app_id = os.getenv("DERIV_APP_ID", "1089")
        self.token = os.getenv("DERIV_API_TOKEN")
        self.ws = None
        self.connected = False
        self.lock = asyncio.Lock()
        self.connect_lock = asyncio.Lock()
        self.ping_task = None

    async def connect(self):
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        uri = f"wss://ws.binaryws.com/websockets/v3?app_id={self.app_id}"
        try:
            self.ws = await asyncio.wait_for(websockets.connect(uri, ssl=ssl_context, open_timeout=40), timeout=45)
            await self.ws.send(json.dumps({"authorize": self.token}))
            res = await asyncio.wait_for(self.ws.recv(), timeout=15)
            data = json.loads(res)
            if "error" in data: raise RuntimeError(data['error'].get('message'))
            self.connected = True
            logger.info("✅ Deriv Connecté")
            if self.ping_task: 
                self.ping_task.cancel()
            self.ping_task = asyncio.create_task(self._ping_loop())
            return data
        except Exception as e:
            self.connected = False
            raise e

    async def ensure_connected(self):
        if not self.ws or not self.connected:
            async with self.connect_lock:
                # Double check after acquiring lock
                if self.ws and self.connected:
                    return True
                try:
                    await self.connect()
                    return True
                except Exception as e:
                    logger.error(f"❌ Reconnection failed: {e}")
                    return False
        return True

    async def send(self, payload: dict) -> dict:
        try:
            if not await self.ensure_connected():
                raise ConnectionError("Failed to ensure connection")

            async with self.lock:
                await self.ws.send(json.dumps(payload))
                res = await asyncio.wait_for(self.ws.recv(), timeout=20)
                return json.loads(res)
        except Exception as e:
            logger.error(f"WebSocket Communication Error: {e}")
            self.connected = False
            self.ws = None
            raise e

    async def get_balance(self):
        try:
            res = await self.send({"balance": 1})
            return res.get("balance")
        except: return None

    async def get_last_transaction(self):
        """
        Fetch the last transaction from the statement.
        """
        try:
            req = {
                "statement": 1,
                "description": 1,
                "limit": 1
            }
            res = await self.send(req)
            if "statement" in res and "transactions" in res["statement"]:
                txs = res["statement"]["transactions"]
                if txs:
                    return txs[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching last transaction: {e}")
            return None

    async def get_contract_status(self, contract_id):
        """
        Check the status of a specific contract.
        """
        try:
            req = {
                "proposal_open_contract": 1,
                "contract_id": contract_id
            }
            res = await self.send(req)
            if "proposal_open_contract" in res:
                return res["proposal_open_contract"]
            return None
        except Exception as e:
            logger.error(f"Error fetching contract status: {e}")
            return None

    async def get_portfolio(self):
        """
        Fetch the list of all open positions (portfolio).
        """
        try:
            res = await self.send({"portfolio": 1})
            return res
        except Exception as e:
            logger.error(f"Error fetching portfolio: {e}")
            return None

    async def sell_contract(self, contract_id, price=0):
        """
        Sell a contract at the current market price.
        """
        try:
            req = {
                "sell": contract_id,
                "price": price
            }
            res = await self.send(req)
            return res
        except Exception as e:
            logger.error(f"Error selling contract {contract_id}: {e}")
            return {"error": str(e)}

    async def _ping_loop(self):
        while self.connected:
            try:
                await asyncio.sleep(25)
                if self.connected:
                    await self.send({"ping": 1})
            except Exception as e:
                logger.debug(f"Ping loop stopped: {e}")
                break

    async def close(self):
        if self.ping_task:
            self.ping_task.cancel()
        if self.ws:
            await self.ws.close()
            self.connected = False
