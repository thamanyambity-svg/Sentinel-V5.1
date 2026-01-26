#!/usr/bin/env python3
"""
Test Script: Validate $3 Minimum Trade Volume Constraint
"""
import sys
import os
sys.path.append(os.path.abspath('.'))

from bot.bridge.mt5_interface import MT5Bridge

def test_minimum_volume():
    bridge = MT5Bridge()
    
    print("=" * 60)
    print("🧪 TESTING $3 MINIMUM VOLUME CONSTRAINT")
    print("=" * 60)
    
    # Test 1: Should REJECT (< $3)
    print("\n📋 Test 1: Volume 0.01 on Volatility 100 (~$5)")
    print("   Expected: PASS (0.01 * 500 = $5)")
    result1 = bridge.send_order("1HZ100V", "BUY", volume=0.01)
    print(f"   Result: {'✅ PASSED' if result1 else '❌ FAILED'}\n")
    
    # Test 2: Should REJECT (< $3)
    print("📋 Test 2: Volume 0.02 on Volatility 100 (~$10)")
    print("   Expected: PASS (0.02 * 500 = $10)")
    result2 = bridge.send_order("1HZ100V", "SELL", volume=0.02)
    print(f"   Result: {'✅ PASSED' if result2 else '❌ FAILED'}\n")
    
    # Test 3: Should REJECT (< $3) - Micro volume
    print("📋 Test 3: Volume 0.005 on Volatility 100 (~$2.50)")
    print("   Expected: REJECT (0.005 * 500 = $2.50 < $3)")
    result3 = bridge.send_order("1HZ100V", "BUY", volume=0.005)
    print(f"   Result: {'✅ REJECTED' if not result3 else '❌ SHOULD HAVE BEEN REJECTED'}\n")
    
    # Test 4: Edge case
    print("📋 Test 4: Volume 0.006 on Volatility 100 (~$3)")
    print("   Expected: PASS (0.006 * 500 = $3.00)")
    result4 = bridge.send_order("1HZ100V", "SELL", volume=0.006)
    print(f"   Result: {'✅ PASSED' if result4 else '❌ FAILED'}\n")
    
    print("=" * 60)
    print("🎯 TEST SUMMARY")
    print("=" * 60)
    tests_passed = sum([result1, result2, not result3, result4])
    print(f"Passed: {tests_passed}/4")
    print(f"Status: {'✅ ALL TESTS PASSED' if tests_passed == 4 else '⚠️ SOME TESTS FAILED'}")
    print("\n⚠️ NOTE: Check MT5 'Command' folder for .json files")
    print("   Only Test 1, 2, and 4 should have generated files.")
    print("   Test 3 should NOT have created a file (rejected).")

if __name__ == "__main__":
    test_minimum_volume()
