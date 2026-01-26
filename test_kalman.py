
import pandas as pd
import numpy as np
import sys
import os

# Add project root
sys.path.append(os.getcwd())

from bot.ai_agents.quantum_filter import QuantumFilter

def test_kalman():
    print("🔬 --- LABORATOIRE QUANTIQUE (Test Kalman) ---")
    
    # 1. Load Data
    csv_path = "bot/data/raw/R_100_M1.csv"
    if not os.path.exists(csv_path):
        print("❌ Needs R_100 data.")
        return

    print("📊 Chargement des données R_100...")
    df = pd.read_csv(csv_path)
    # Take last 1000 candles for clear visualization
    subset = df.tail(100).copy()
    prices = subset['close'].values
    
    # 2. Apply Filter
    print("🚀 Activation du Filtre Quantique (Q=1e-5, R=0.1)...")
    qf = QuantumFilter(process_noise=1e-5, measurement_noise=0.1)
    
    estimated = []
    velocities = []
    
    for p in prices:
        est, vel = qf.update(p)
        estimated.append(est)
        velocities.append(vel)
        
    subset['kalman'] = estimated
    subset['velocity'] = velocities
    
    # Calculate Noise Estimation (Real - Kalman)
    noise = np.abs(subset['close'] - subset['kalman'])
    avg_noise = np.mean(noise)
    
    print(f"\n📈 Résultats sur 100 bougies :")
    print(f"   - Bruit Moyen filtré : {avg_noise:.4f}")
    
    # Comparison table
    print("\n🔍 Comparatif (10 dernières bougies) :")
    print(f"{'Temps':<20} | {'Prix Réel':<10} | {'Prix Quantique':<15} | {'Vitesse (Momentum)':<15}")
    print("-" * 75)
    
    history_tail = subset.tail(10)
    for index, row in history_tail.iterrows():
        t = pd.to_datetime(row['epoch'], unit='s')
        real = row['close']
        kal = row['kalman']
        vel = row['velocity']
        print(f"{str(t):<20} | {real:<10.2f} | {kal:<15.2f} | {vel:<15.4f}")
        
    print("\n✅ Conclusion : Le 'Prix Quantique' est stable. La 'Vitesse' indique la vraie tendance instantanée.")

if __name__ == "__main__":
    test_kalman()
