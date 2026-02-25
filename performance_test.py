import time
import statistics
import numpy as np
import pandas as pd
import threading
import time
import statistics
import numpy as np
import pandas as pd
import threading
from bot.data.smart_cache import SmartCache
import os
import shutil

# Robust imports for optional dependencies
try:
    from bot.core.zeromq_bridge import HighSpeedBridge
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    print("⚠️ ZMQ Bridge unavailable (dependency missing)")

try:
    from bot.analysis.fast_indicators import OptimizedIndicators, fast_rsi
    # Check if numba was actually loaded in fast_indicators
    from bot.analysis.fast_indicators import NUMBA_AVAILABLE
except ImportError:
    NUMBA_AVAILABLE = False
    print("⚠️ Numba unavailable (dependency missing)")

def benchmark_bridge():
    """Teste la latence du bridge"""
    print("\n🚀 [1/3] Benchmarking ZMQ Bridge...")
    
    if not ZMQ_AVAILABLE:
        print("   ❌ SKIPPED: ZMQ not installed")
        return

    try:
        bridge = HighSpeedBridge()
        # Dummy processor
        bridge.set_command_processor(lambda x: x)
        bridge.start()
        
        # Client socket for testing
        import zmq
        context = zmq.Context()
        req = context.socket(zmq.REQ)
        req.connect("tcp://localhost:5556")
        
        times = []
        print("   Running 100 requests...")
        for i in range(100):
            start = time.perf_counter()
            req.send_json({"cmd": "ping"})
            _ = req.recv_json()
            end = time.perf_counter()
            times.append((end - start) * 1000)  # ms
        
        avg_lat = statistics.mean(times)
        max_lat = max(times)
        
        print(f"   ✅ Latence Moyenne: {avg_lat:.3f}ms")
        print(f"   ✅ Latence Max: {max_lat:.3f}ms")
        if avg_lat < 1.0:
            print("   🏆 Ultra-Fast (<1ms) Confirmed!")
        
        bridge.stop()
        req.close()
        context.term()
    except Exception as e:
        print(f"   ❌ Bridge Test Failed: {e}")

def benchmark_indicators():
    """Teste la vitesse des indicateurs"""
    print("\n⚡ [2/3] Benchmarking Numba Indicators...")
    
    if not NUMBA_AVAILABLE:
        print("   ⚠️ Running in compatibility mode (Numba missing). Speedup not guaranteed.")
    
    # Generate large dataset
    N = 100_000

    print(f"   Generating {N} data points...")
    data = np.random.randn(N)
    
    # Warmup Numba (jit compilation)
    print("   Warming up JIT...")
    fast_rsi(data[:100])
    
    start = time.perf_counter()
    iterations = 50
    print(f"   Calculating RSI {iterations} times...")
    for _ in range(iterations):
        fast_rsi(data)
    end = time.perf_counter()
    
    total_time = end - start
    per_op = (total_time / iterations) * 1000 # ms
    
    print(f"   ✅ Total Time: {total_time:.4f}s")
    print(f"   ✅ Time per Op (100k candles): {per_op:.3f}ms")
    
    # Compare with pandas (approx)
    start_pd = time.perf_counter()
    s = pd.Series(data)
    # Simple pandas rolling approach
    delta = s.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    _ = 100 - (100 / (1 + rs))
    end_pd = time.perf_counter()
    pd_time = (end_pd - start_pd) * 1000
    
    print(f"   🆚 Pandas (Single Run): ~{pd_time:.3f}ms")
    speedup = pd_time / per_op
    print(f"   🚀 Speedup: {speedup:.1f}x")

def benchmark_cache():
    print("\n💾 [3/3] Benchmarking Smart Cache...")
    cache = SmartCache(cache_dir="test_cache_bench")
    cache.clear_all()
    
    # Dummy expensive operation
    def expensive_op():
        time.sleep(0.1) # 100ms delay
        return "RESULT"
    
    params = {"a": 1, "b": 2}
    
    # First call (Miss)
    start = time.perf_counter()
    res1 = cache.get_or_compute("TEST", "1m", params, expensive_op)
    end = time.perf_counter()
    miss_time = (end - start) * 1000
    print(f"   ❌ Cache Miss (Expected ~100ms): {miss_time:.3f}ms")
    
    # Second call (Hit)
    start = time.perf_counter()
    res2 = cache.get_or_compute("TEST", "1m", params, expensive_op)
    end = time.perf_counter()
    hit_time = (end - start) * 1000
    print(f"   ✅ Cache Hit: {hit_time:.3f}ms")
    
    gain = miss_time / hit_time if hit_time > 0 else 999
    print(f"   🚀 Acceleration: {gain:.1f}x")
    
    # Cleanup
    shutil.rmtree("test_cache_bench")

if __name__ == "__main__":
    print("🏆 STARTING PHASE 3 PERFORMANCE BENCHMARK 🏆")
    try:
        benchmark_bridge()
        benchmark_indicators()
        benchmark_cache()
        print("\n✨ ALL BENCHMARKS COMPLETED ✨")
    except Exception as e:
        print(f"\n❌ BENCHMARK ERROR: {e}")
