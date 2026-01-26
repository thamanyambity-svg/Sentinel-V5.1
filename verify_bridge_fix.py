from bot.bridge.mt5_interface import MT5Bridge
import time

bridge = MT5Bridge()
print("🚀 Sending TEST TRADE (Buy 0.01 -> Auto-adjusted to 0.50)...")

# We send 0.01 to test the auto-adjust logic
success = bridge.send_order("Volatility 100 (1s) Index", "BUY", volume=0.01)

if success:
    print("✅ Command File Created.")
else:
    print("❌ Failed to create command.")
