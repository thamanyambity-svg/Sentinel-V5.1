from tradingview_ta import TA_Handler, Interval, Exchange

print("--- TESTING TRADINGVIEW-TA (EXTENDED) ---")

combinations = [
    # Attempt 1: Standard
    {"symbol": "R_100", "screener": "cfd", "exchange": "DERIV"},
    # Attempt 2: Full Name
    {"symbol": "VOLATILITY100INDEX", "screener": "cfd", "exchange": "DERIV"},
    # Attempt 3: Forex screener?
    {"symbol": "R_100", "screener": "forex", "exchange": "DERIV"},
    # Attempt 4: Binary screener? (unlikely)
    # Attempt 5: 1HZ (Tick)
    {"symbol": "1HZ100V", "screener": "cfd", "exchange": "DERIV"},
    # Attempt 6: Just 'R_100' without exchange (sometimes auto-detects)
    {"symbol": "R_100", "screener": "cfd", "exchange": ""},
]

for c in combinations:
    print(f"\nTesting: {c['symbol']} | {c['screener']} | {c['exchange']}")
    try:
        handler = TA_Handler(
            symbol=c["symbol"],
            screener=c["screener"],
            exchange=c["exchange"],
            interval=Interval.INTERVAL_1_MINUTE
        )
        analysis = handler.get_analysis()
        if analysis:
            print(f"✅ SUCCESS! Price: {analysis.indicators['close']}")
            print(f"Summary: {analysis.summary}")
            break
    except Exception as e:
        print(f"❌ Failed: {e}")
