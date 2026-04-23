#!/usr/bin/env python3
"""
WebSocket Server for SENTINEL PREDATOR Mobile App
Streams real-time trading data to mobile clients
Port: 5001
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
import websockets
from websockets.server import WebSocketServerProtocol
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dashboard_manager import DashboardManager
from config_sentinel import API_CONFIG, DATA_FILES

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s | %(name)s: %(message)s'
)
logger = logging.getLogger('websocket_server')

class SentinelWebSocketServer:
    """Real-time WebSocket server for SENTINEL PREDATOR mobile app"""
    
    def __init__(self, host='0.0.0.0', port=5001):
        self.host = host
        self.port = port
        self.dashboard_manager = DashboardManager()
        self.clients = set()
        self.running = False
        logger.info(f"WebSocket Server initialized (listening on {host}:{port})")
    
    async def register_client(self, websocket: WebSocketServerProtocol):
        """Register a new client connection"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
        # Send initial connection confirmation
        await websocket.send(json.dumps({
            "type": "connection",
            "status": "authenticated",
            "timestamp": datetime.now().isoformat(),
            "app": "SENTINEL PREDATOR",
            "version": "1.0.0"
        }))
    
    async def unregister_client(self, websocket: WebSocketServerProtocol):
        """Unregister a client connection"""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
    
    async def broadcast_market_data(self):
        """Broadcast real-time market data to all connected clients"""
        while self.running:
            try:
                # Fetch fresh data
                health = self.dashboard_manager.load_data('health', cache_ttl=2)
                account = self.dashboard_manager.load_data('account', cache_ttl=2)
                positions = self.dashboard_manager.load_data('positions', cache_ttl=2)
                ticks = self.dashboard_manager.load_data('ticks', cache_ttl=1)
                ml_signal = self.dashboard_manager.load_data('ml_signal', cache_ttl=3)
                backtest = self.dashboard_manager.load_data('backtest', cache_ttl=5)
                
                # Prepare payload
                payload = {
                    "type": "market_update",
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        "health": health,
                        "account": account,
                        "positions": positions,
                        "ticks": ticks,
                        "ml_signal": ml_signal,
                        "backtest": backtest
                    }
                }
                
                # Broadcast to all clients
                if self.clients:
                    message = json.dumps(payload)
                    disconnected = set()
                    
                    for client in self.clients:
                        try:
                            await client.send(message)
                        except websockets.exceptions.ConnectionClosed:
                            disconnected.add(client)
                    
                    # Clean up disconnected clients
                    for client in disconnected:
                        await self.unregister_client(client)
                
                # Broadcast every 2 seconds
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error broadcasting market data: {e}")
                await asyncio.sleep(5)
    
    async def handle_client(self, websocket: WebSocketServerProtocol, path):
        """Handle incoming client messages"""
        await self.register_client(websocket)
        
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.process_client_message(websocket, data)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister_client(websocket)
    
    async def process_client_message(self, websocket: WebSocketServerProtocol, data: dict):
        """Process incoming message from client"""
        msg_type = data.get('type')
        
        try:
            if msg_type == 'subscribe':
                # Subscribe to specific data stream
                channel = data.get('channel')
                response = {
                    "type": "subscription",
                    "channel": channel,
                    "status": "subscribed",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))
                logger.info(f"Client subscribed to {channel}")
            
            elif msg_type == 'request_data':
                # On-demand data request
                data_key = data.get('key')
                fresh_data = self.dashboard_manager.load_data(data_key, cache_ttl=0)
                
                response = {
                    "type": "data_response",
                    "key": data_key,
                    "data": fresh_data,
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))
            
            elif msg_type == 'ping':
                # Heartbeat/keep-alive
                response = {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))
            
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        
        except Exception as e:
            logger.error(f"Error processing client message: {e}")
            error_response = {
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            try:
                await websocket.send(json.dumps(error_response))
            except:
                pass
    
    async def start(self):
        """Start the WebSocket server"""
        self.running = True
        
        # Start data broadcaster
        broadcaster = asyncio.create_task(self.broadcast_market_data())
        
        # Start WebSocket server
        async with websockets.serve(self.handle_client, self.host, self.port):
            logger.info(f"✓ WebSocket Server running on ws://{self.host}:{self.port}")
            logger.info("Waiting for client connections...")
            
            try:
                while self.running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("\nShutting down...")
                self.running = False
    
    def run(self):
        """Run the server synchronously"""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("\n✓ Server stopped")


if __name__ == '__main__':
    server = SentinelWebSocketServer(
        host=API_CONFIG.get('WS_HOST', '0.0.0.0'),
        port=API_CONFIG.get('WS_PORT', 5001)
    )
    server.run()
