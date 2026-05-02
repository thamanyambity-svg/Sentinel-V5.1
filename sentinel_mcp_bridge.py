
import json
import sys
import requests
from typing import Dict, Any

def get_sentinel_data(endpoint: str) -> Dict[str, Any]:
    try:
        response = requests.get(f"http://localhost:5000/api/v1/{endpoint}", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def execute_trade(symbol: str, side: str, volume: float) -> Dict[str, Any]:
    try:
        response = requests.post(
            "http://localhost:5000/api/v1/trade",
            json={"symbol": symbol, "side": side, "volume": volume},
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def main():
    # Simple stdio-based MCP-like protocol for Ruflo integration
    # This is a simplified version for demonstration
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            request = json.loads(line)
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "get_account":
                result = get_sentinel_data("account")
            elif method == "get_decision":
                result = get_sentinel_data("decision")
            elif method == "execute_trade":
                result = execute_trade(
                    params.get("symbol", "GOLD"),
                    params.get("side", "BUY"),
                    params.get("volume", 0.01)
                )
            else:
                result = {"error": "Unknown method"}
            
            print(json.dumps({"jsonrpc": "2.0", "result": result, "id": request.get("id")}))
            sys.stdout.flush()
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.stdout.flush()

if __name__ == "__main__":
    main()
