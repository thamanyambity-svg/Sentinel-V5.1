import zmq
import json

print("Testing ZMQ Client (Mock MT5)...")
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://127.0.0.1:5555")

# Test 1: PING
payload = json.dumps({"action": "PING"})
print(f"\nSending: {payload}")
socket.send_string(payload)
reply = socket.recv_string()
print(f"Received: {reply}")

# Test 2: REAL SIGNAL (BUY EURUSD)
payload = json.dumps({
    "action": "EVALUATE",
    "asset": "EURUSD",
    "tech_signal": "BUY"
})
print(f"\nSending: {payload}")
socket.send_string(payload)
reply = socket.recv_string()
print(f"Received: {reply}")

# Test 3: REAL SIGNAL (SELL US30)
payload = json.dumps({
    "action": "EVALUATE",
    "asset": "US30",
    "tech_signal": "SELL"
})
print(f"\nSending: {payload}")
socket.send_string(payload)
reply = socket.recv_string()
print(f"Received: {reply}")

print("\nDone testing.")
