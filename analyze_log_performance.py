
import re

LOG_FILE = "bot_output.log"

def analyze():
    orders = 0
    buys = 0
    sells = 0
    balances = []
    
    with open(LOG_FILE, 'r') as f:
        for line in f:
            # Count Orders
            if "Order Deposited" in line:
                orders += 1
                if "BUY" in line: buys += 1
                if "SELL" in line: sells += 1
            
            # Track Balance (MT5 or Options)
            # Log format: 🛡️ [RISK] 1HZ10V | Balance: 6555.06$ ...
            # AND Periodic Report balances if available
            balance_match = re.search(r"Balance:\s*([\d\.]+)\$", line)
            if balance_match:
                balances.append(float(balance_match.group(1)))

    if not balances:
        print("No Balance logs found.")
        return

    start_balance = balances[0]
    end_balance = balances[-1]
    pnl = end_balance - start_balance
    
    print(f"--- PERFORMANCE REPORT ---")
    print(f"Total Orders: {orders}")
    print(f"BUYs: {buys} | SELLs: {sells}")
    print(f"Start Balance: ${start_balance:.2f}")
    print(f"End Balance:   ${end_balance:.2f}")
    print(f"PnL Session:   ${pnl:.2f}")
    print(f"--------------------------")

if __name__ == "__main__":
    analyze()
