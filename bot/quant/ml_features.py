import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import os
import joblib

# Robust imports for sklearn
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn not found. ML features limited.")

class AdvancedFeatureEngineer:
    def __init__(self, data: pd.DataFrame):
        self.data = data.copy()
        # Sort by date just in case
        if isinstance(self.data.index, pd.DatetimeIndex):
            self.data.sort_index(inplace=True)
    
    def create_features(self) -> pd.DataFrame:
        """Crée des features avancées pour le ML"""
        df = self.data
        
        # Ensure minimal columns exist
        if 'close' not in df.columns:
            return df
            
        # Features de base
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Features de volatilité
        df['volatility_10'] = df['returns'].rolling(10).std()
        df['volatility_30'] = df['returns'].rolling(30).std()
        
        # Features de momentum
        df['momentum_5'] = df['close'] / df['close'].shift(5) - 1
        df['momentum_20'] = df['close'] / df['close'].shift(20) - 1
        
        # Features de mean reversion
        df['zscore_20'] = (df['close'] - df['close'].rolling(20).mean()) / (df['close'].rolling(20).std() + 1e-9)
        
        # Features de volume (si disponible)
        if 'volume' in df.columns:
            df['volume_sma_20'] = df['volume'] / (df['volume'].rolling(20).mean() + 1e-9)
        
        # Features de pattern (candles)
        if 'open' in df.columns and 'high' in df.columns and 'low' in df.columns:
            df['body_size'] = abs(df['close'] - df['open'])
            df['upper_shadow'] = df['high'] - np.maximum(df['open'], df['close'])
            df['lower_shadow'] = np.minimum(df['open'], df['close']) - df['low']
        
        # Target : prédire si le prix va monter dans les 5 prochaines bougies
        # 1 = UP, 0 = DOWN/FLAT
        df['target'] = (df['close'].shift(-5) > df['close']).astype(int)
        
        return df.dropna()
    
    def prepare_data(self, features: List[str], target: str = 'target') -> Tuple[pd.DataFrame, pd.Series]:
        """Prépare les données pour le ML"""
        df = self.create_features()
        
        # Filter only existing features
        valid_features = [f for f in features if f in df.columns]
        
        X = df[valid_features]
        y = df[target]
        return X, y

class MLTradingModel:
    def __init__(self, model_type: str = 'random_forest'):
        self.model_type = model_type
        self.model = None
        
        if not SKLEARN_AVAILABLE:
            return

        if model_type == 'random_forest':
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        elif model_type == 'gradient_boosting':
            self.model = GradientBoostingClassifier(n_estimators=100, random_state=42)
        else:
            raise ValueError("Model type not supported")
    
    def train(self, X: pd.DataFrame, y: pd.Series) -> float:
        """Entraîne le modèle"""
        if not SKLEARN_AVAILABLE or self.model is None:
            print("❌ Cannot train: sklearn missing.")
            return 0.0

        print(f"🧠 Training {self.model_type} on {len(X)} samples...")
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        self.model.fit(X_train, y_train)
        
        # Évaluation
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"📊 Model Accuracy: {accuracy:.4f}")
        # print(classification_report(y_test, y_pred))
        
        return accuracy
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Fait des prédictions (probabilités)"""
        if not SKLEARN_AVAILABLE or self.model is None:
            return np.zeros(len(X))
        
        # Ensure input features match training features order (simple check)
        # In prod, check columns names against self.model.feature_names_in_
        
        return self.model.predict_proba(X)[:, 1]  # Probabilité de classe 1 (UP)
    
    def save_model(self, filename: str):
        """Sauvegarde le modèle"""
        if self.model:
            joblib.dump(self.model, filename)
            print(f"💾 Model saved to {filename}")
    
    def load_model(self, filename: str):
        """Charge un modèle"""
        if os.path.exists(filename):
            self.model = joblib.load(filename)
            print(f"📂 Model loaded from {filename}")
        else:
            print(f"❌ Model file not found: {filename}")

if __name__ == "__main__":
    # Test
    if SKLEARN_AVAILABLE:
        print("🧪 Generating test data for ML...")
        idx = pd.date_range("2023-01-01", periods=1000, freq="H")
        df = pd.DataFrame({
            'open': np.random.randn(1000).cumsum() + 100,
            'high': np.random.randn(1000).cumsum() + 105,
            'low': np.random.randn(1000).cumsum() + 95,
            'close': np.random.randn(1000).cumsum() + 100,
            'volume': np.abs(np.random.randn(1000)) * 1000
        }, index=idx)
        
        engineer = AdvancedFeatureEngineer(df)
        features = ['returns', 'volatility_10', 'momentum_5', 'zscore_20', 'body_size']
        X, y = engineer.prepare_data(features)
        
        ml_model = MLTradingModel('random_forest')
        ml_model.train(X, y)
    else:
        print("⏭️ Skipping ML test (sklearn missing)")
