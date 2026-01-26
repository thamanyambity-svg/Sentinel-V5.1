
import logging
import os
import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger("QUANT_PREDICTOR")

class QuantPredictor:
    """
    The Oracle Agent.
    Loads trained MLP models and provides real-time price predictions.
    """
    def __init__(self, model_dir="bot/models"):
        self.model_dir = model_dir
        self.models = {}
        self.scalers = {}
        self.assets = ["R_100", "R_75", "R_50", "1HZ100V", "1HZ10V"]
        self.lookback = 60
        
        self._load_brains()
        
    def _load_brains(self):
        """Load .pkl models and scalers for all assets."""
        for asset in self.assets:
            model_path = os.path.join(self.model_dir, f"{asset}_mlp.pkl")
            scaler_path = os.path.join(self.model_dir, f"{asset}_scaler.pkl")
            
            if os.path.exists(model_path) and os.path.exists(scaler_path):
                try:
                    self.models[asset] = joblib.load(model_path)
                    self.scalers[asset] = joblib.load(scaler_path)
                    logger.info(f"🧠 {asset} Oracle active.")
                except Exception as e:
                    logger.error(f"❌ Failed to load brain for {asset}: {e}")
            else:
                logger.warning(f"⚠️ No brain found for {asset} (Expected at {model_path})")

    def predict(self, asset, candles):
        """
        Predict the next close price using the Neural Network.
        """
        if asset not in self.models:
            return None
            
        try:
            # 1. Prepare Data (Last 60 candles)
            # Ensure we have enough data
            if len(candles) < self.lookback:
                return None
                
            # Extract closes
            closes = [float(c['close']) for c in candles[-self.lookback:]]
            values = np.array(closes).reshape(-1, 1)
            
            # 2. Scale
            scaler = self.scalers[asset]
            scaled_values = scaler.transform(values)
            
            # 3. Reshape for Model (1 sample, 60 features)
            # The model expects input shape (n_samples, n_features) where n_features=lookback
            # Our trainer used sequences: X.append(scaled_data[i-lookback:i, 0])
            # So input should be a 1D array of 60 items
            input_seq = scaled_values.flatten().reshape(1, -1)
            
            # 4. Predict
            predicted_scaled = self.models[asset].predict(input_seq)
            
            # 5. Inverse Scale
            predicted_price = scaler.inverse_transform(predicted_scaled.reshape(-1, 1))
            
            return float(predicted_price[0][0])
            
        except Exception as e:
            logger.error(f"🔮 Prediction error for {asset}: {e}")
            return None
