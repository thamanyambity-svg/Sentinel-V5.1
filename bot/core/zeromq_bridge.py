import zmq
import json
import threading
import time
from typing import Dict, Optional

class HighSpeedBridge:
    def __init__(self, pub_port: int = 5555, rep_port: int = 5556):
        self.context = zmq.Context()
        
        # Publisher for Market Data (1-way streaming)
        # TCP is generally fine for local IPC if configured correctly, but IPC transport is even faster on unix.
        # Sticking to TCP as per user request (tcp://*:5555) for universality.
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://*:{pub_port}")
        
        # Request-Reply for Commands (Bidirectional)
        self.rep_socket = self.context.socket(zmq.REP)
        self.rep_socket.bind(f"tcp://*:{rep_port}")
        
        # Command handler thread
        self.running = True
        self.command_processor = None # external callback
        self.command_thread = None
        
        print(f"🚀 Bridge ZeroMQ Activated [PUB:{pub_port} | REP:{rep_port}]")
    
    def publish_market_data(self, data: Dict):
        """Publishes market data stream."""
        try:
            self.pub_socket.send_json(data)
        except Exception as e:
            print(f"❌ ZMQ Pub Error: {e}")
    
    def set_command_processor(self, func):
        """Sets the callback function to process incoming commands.
        func(command: dict) -> dict (response)
        """
        self.command_processor = func

    def _command_loop(self):
        """Internal loop to handle incoming commands."""
        while self.running:
            try:
                # Blocking receive
                command = self.rep_socket.recv_json()
                
                # Process command
                if self.command_processor:
                    response = self.command_processor(command)
                else:
                    response = {"status": "error", "message": "No processor attached"}
                
                # Send response
                self.rep_socket.send_json(response)
                
            except zmq.ZMQError as e:
                if self.running:
                    print(f"❌ ZMQ Recv Error: {e}")
            except Exception as e:
                print(f"❌ Bridge Command Error: {e}")
                self.rep_socket.send_json({"status": "error", "message": str(e)})

    def start(self):
        """Starts the command handling thread."""
        self.running = True
        self.command_thread = threading.Thread(target=self._command_loop, daemon=True)
        self.command_thread.start()
        print("⚡ High Speed Bridge Listener Started")

    def stop(self):
        """Stops the bridge and cleans up resources."""
        self.running = False
        # Context termination handles socket closing mostly
        self.context.term()
        print("🛑 High Speed Bridge Stopped")

# Example usage/Test
if __name__ == "__main__":
    bridge = HighSpeedBridge()
    
    def echo_processor(cmd):
        print(f"📥 Received: {cmd}")
        return {"status": "ok", "echo": cmd}
    
    bridge.set_command_processor(echo_processor)
    bridge.start()
    
    # Simulate publishing market data
    try:
        i = 0
        while True:
            data = {"symbol": "EURUSD", "price": 1.1000 + (i*0.0001), "ts": time.time()}
            bridge.publish_market_data(data)
            time.sleep(1)
            i += 1
    except KeyboardInterrupt:
        bridge.stop()
