
import pandas as pd
import numpy as np
from hmmlearn.hmm import GaussianHMM
import logging
import sys
import os

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("HMM_LAB")

def load_data(filepath):
    """Load and prepare data for HMM"""
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return None
        
    df = pd.read_csv(filepath)
    # Ensure sorted by time
    df = df.sort_values('epoch').reset_index(drop=True)
    
    # Calculate features
    # 1. Log Returns
    df['close'] = df['close'].astype(float)
    df['returns'] = np.log(df['close'] / df['close'].shift(1))
    
    # 2. Volatility (Rolling Std Dev)
    df['volatility'] = df['returns'].rolling(window=10).std()
    
    # Drop NaNs
    df = df.dropna()
    return df

def train_hmm(df, n_states=3):
    """Train Gaussian HMM on returns and volatility"""
    
    # Prepare training data (X)
    # Using Returns and Volatility as features
    X = df[['returns', 'volatility']].values
    
    # Initialize HMM
    model = GaussianHMM(n_components=n_states, covariance_type="full", n_iter=100, random_state=42)
    
    logger.info(f"🧠 Training HMM with {n_states} hidden states on {len(X)} data points...")
    model.fit(X)
    
    logger.info("✅ Training complete.")
    logger.info(f"Converged: {model.monitor_.converged}")
    
    return model

def analyze_regimes(model, df):
    """Predict states and analyze their properties"""
    X = df[['returns', 'volatility']].values
    hidden_states = model.predict(X)
    
    df['state'] = hidden_states
    
    # Analyze each state
    logger.info("\n📊 ANALYSIS OF MARKET REGIMES:")
    regime_map = {}
    
    for i in range(model.n_components):
        state_data = df[df['state'] == i]
        avg_vol = state_data['volatility'].mean()
        avg_ret = state_data['returns'].mean()
        count = len(state_data)
        
        # Simple heuristic to name regimes based on volatility
        desc = "UNKNOWN"
        if avg_vol < 0.0005: desc = "CALM (Accumulation)"
        elif avg_vol < 0.0015: desc = "NORMAL (Trending)"
        else: desc = "VOLATILE (Crash/Breakout)"
        
        regime_map[i] = desc
        
        logger.info(f"🔹 Regime {i} [{desc}]:")
        logger.info(f"   - Obs: {count} ({count/len(df)*100:.1f}%)")
        logger.info(f"   - Avg Volatility: {avg_vol:.6f}")
        logger.info(f"   - Avg Return: {avg_ret:.6f}")
        
    # Check current state
    last_state = df['state'].iloc[-1]
    logger.info(f"\n🔮 CURRENT MARKET STATUS (Last Candle):")
    logger.info(f"   - State: {last_state} ({regime_map[last_state]})")
    
    return regime_map

if __name__ == "__main__":
    # Path to data
    DATA_FILE = "bot/data/raw/1HZ100V_M1.csv"
    
    logger.info("🔬 SENTINEL V4 LAB : HMM REGIME DETECTION")
    
    df = load_data(DATA_FILE)
    if df is not None:
        model = train_hmm(df)
        analyze_regimes(model, df)
    else:
        logger.error("Could not load data.")
