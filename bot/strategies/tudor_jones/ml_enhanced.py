# strategies/tudor_jones/ml_enhanced.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib
from typing import Dict, List, Tuple, Optional
import logging
import os

class TudorJonesMLEnhancer:
    def __init__(self, market_data: pd.DataFrame, economic_data: Optional[pd.DataFrame] = None):
        self.market_data = market_data
        self.economic_data = economic_data
        self.models = {}
        self.scalers = {}
        self.logger = logging.getLogger("TUDOR_ML")
        
    def create_tudor_features(self) -> pd.DataFrame:
        """Crée des features spécifiques à la philosophie de Tudor Jones"""
        df = self.market_data.copy()
        
        # Features de base
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Features de momentum (Tudor Jones aime le momentum)
        for period in [1, 3, 5, 10, 20]:
            df[f'momentum_{period}d'] = df['close'] / df['close'].shift(period) - 1
        
        # Features de volatilité
        df['volatility_10d'] = df['returns'].rolling(10).std()
        df['volatility_30d'] = df['returns'].rolling(30).std()
        df['volatility_ratio'] = df['volatility_10d'] / df['volatility_30d']
        
        # Features de range (Tudor Jones surveille les ranges)
        df['range_10d'] = (df['high'].rolling(10).max() - df['low'].rolling(10).min()) / df['close']
        df['range_position'] = (df['close'] - df['low'].rolling(10).min()) / (df['high'].rolling(10).max() - df['low'].rolling(10).min())
        
        # Features de volume
        df['volume_sma_20'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20']
        df['volume_spike'] = (df['volume'] > df['volume_sma_20'] * 2).astype(int)
        
        # Features de capitulation (spécifique Tudor Jones)
        df['large_down_day'] = (df['returns'] < -0.03).astype(int)  # -3%
        df['capitulation_signal'] = df['large_down_day'].rolling(3).sum()  # 3 jours de capitulation
        
        # Features de réversal
        df['doji_pattern'] = self._detect_doji(df)
        df['hammer_pattern'] = self._detect_hammer(df)
        df['engulfing_pattern'] = self._detect_engulfing(df)
        
        # Features de tendance
        df['sma_10'] = df['close'].rolling(10).mean()
        df['sma_30'] = df['close'].rolling(30).mean()
        df['sma_50'] = df['close'].rolling(50).mean()
        df['trend_strength'] = (df['sma_10'] - df['sma_50']) / df['sma_50']
        
        # Features cycliques
        df['day_of_week'] = df.index.dayofweek
        df['month_of_year'] = df.index.month
        df['quarter'] = df.index.quarter
        
        return df.dropna()
    
    def _detect_doji(self, df: pd.DataFrame) -> pd.Series:
        """Détecte les patterns doji"""
        body_size = abs(df['close'] - df['open'])
        total_range = df['high'] - df['low']
        doji = (body_size / total_range < 0.1).astype(int)
        return doji
    
    def _detect_hammer(self, df: pd.DataFrame) -> pd.Series:
        """Détecte les patterns hammer"""
        body_size = abs(df['close'] - df['open'])
        total_range = df['high'] - df['low']
        upper_shadow = df['high'] - np.maximum(df['open'], df['close'])
        lower_shadow = np.minimum(df['open'], df['close']) - df['low']
        
        hammer = ((body_size / total_range < 0.3) &  # Petit corps
                 (lower_shadow > body_size * 2) &  # Longue ombre basse
                 (upper_shadow < body_size * 0.5)).astype(int)  # Petite ombre haute
        return hammer
    
    def _detect_engulfing(self, df: pd.DataFrame) -> pd.Series:
        """Détecte les patterns engulfing"""
        prev_body = abs(df['close'].shift(1) - df['open'].shift(1))
        curr_body = abs(df['close'] - df['open'])
        
        prev_close = df['close'].shift(1)
        prev_open = df['open'].shift(1)
        curr_close = df['close']
        curr_open = df['open']
        
        bullish_engulfing = ((prev_close < prev_open) &  # Bougie rouge précédente
                           (curr_close > curr_open) &  # Bougie verte actuelle
                           (curr_close > prev_open) &  # Clôture au-dessus de l'ouverture précédente
                           (curr_open < prev_close) &  # Ouverture en dessous de la clôture précédente
                           (curr_body > prev_body)).astype(int)
        
        bearish_engulfing = ((prev_close > prev_open) &  # Bougie verte précédente
                           (curr_close < curr_open) &  # Bougie rouge actuelle
                           (curr_close < prev_open) &  # Clôture en dessous de l'ouverture précédente
                           (curr_open > prev_close) &  # Ouverture au-dessus de la clôture précédente
                           (curr_body > prev_body)).astype(int)
        
        return bullish_engulfing | bearish_engulfing
    
    def prepare_training_data(self, lookahead_periods: List[int] = [1, 3, 5, 10]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prépare les données pour l'entraînement ML"""
        features_df = self.create_tudor_features()
        
        # Créer les labels pour différentes périodes
        labels_dfs = {}
        for period in lookahead_periods:
            future_returns = features_df['close'].pct_change(period).shift(-period)
            labels = (future_returns > 0).astype(int)  # 1 si hausse, 0 sinon
            labels_dfs[f'label_{period}d'] = labels
        
        # Combiner features et labels
        combined_df = features_df.copy()
        for period in lookahead_periods:
            combined_df = combined_df.join(labels_dfs[f'label_{period}d'])
        
        combined_df = combined_df.dropna()
        
        # Séparer features et labels
        feature_columns = [col for col in combined_df.columns if not col.startswith('label_')]
        label_columns = [col for col in combined_df.columns if col.startswith('label_')]
        
        X = combined_df[feature_columns]
        y = combined_df[label_columns]
        
        return X, y
    
    def train_tudor_models(self, model_types: List[str] = ['rf', 'gb', 'mlp']):
        """Entraîne plusieurs modèles ML selon la philosophie Tudor Jones"""
        X, y = self.prepare_training_data()
        
        # Normaliser les features
        scaler = RobustScaler()  # Robuste aux outliers
        X_scaled = scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
        
        for model_type in model_types:
            self.logger.info(f"Training {model_type.upper()} model...")
            
            for period in [1, 3, 5, 10]:
                label_col = f'label_{period}d'
                
                # Créer et entraîner le modèle
                if model_type == 'rf':
                    model = RandomForestClassifier(
                        n_estimators=200,
                        max_depth=10,
                        min_samples_split=20,
                        min_samples_leaf=10,
                        random_state=42
                    )
                elif model_type == 'gb':
                    model = GradientBoostingClassifier(
                        n_estimators=200,
                        max_depth=8,
                        learning_rate=0.1,
                        min_samples_split=20,
                        random_state=42
                    )
                elif model_type == 'mlp':
                    model = MLPClassifier(
                        hidden_layer_sizes=(100, 50),
                        max_iter=500,
                        random_state=42,
                        early_stopping=True,
                        validation_fraction=0.2
                    )
                
                # Entraîner le modèle
                model.fit(X_scaled, y[label_col])
                
                # Validation croisée temporelle
                tscv = TimeSeriesSplit(n_splits=5)
                scores = cross_val_score(model, X_scaled, y[label_col], cv=tscv, scoring='f1')
                
                # Sauvegarder le modèle
                model_name = f"{model_type}_{period}d"
                self.models[model_name] = {
                    'model': model,
                    'scaler': scaler,
                    'features': X.columns.tolist(),
                    'cv_score': scores.mean(),
                    'cv_std': scores.std()
                }
                
                self.logger.info(f"{model_name} - CV F1 Score: {scores.mean():.3f} (+/- {scores.std() * 2:.3f})")
        
        # Sauvegarder tous les modèles
        self.save_models()
    
    def predict_tudor_signals(self, current_data: pd.DataFrame) -> Dict[str, Dict]:
        """Génère des signaux de trading ML enrichis"""
        predictions = {}
        
        # Préparer les features actuelles
        # NOTE: Assumes current_data contains enough history to generate features
        try:
             # In a real scenario, we might need more history. Here we assume we pass enough data
             features_df = self.create_tudor_features()
             current_features = features_df.iloc[-1:] # Dernière ligne
        except Exception as e:
            self.logger.error(f"Error creating features: {e}")
            return {}

        
        for model_name, model_info in self.models.items():
            model = model_info['model']
            scaler = model_info['scaler']
            features = model_info['features']
            
            # Normaliser en utilisant le scaler entraîné
            try:
                # Align features
                X_current = current_features[features]
                X_current_scaled = scaler.transform(X_current)
                
                # Prédire
                proba = model.predict_proba(X_current_scaled)[0]
                
                # Extraire la probabilité de hausse
                if len(proba) == 2:
                    buy_proba = proba[1]  # Probabilité de classe 1 (hausse)
                else:
                    buy_proba = proba[0] # Should not happen if binary classifier
                
                # Déterminer le type de stratégie
                model_type, period = model_name.split('_')
                period_val = int(period[:-1])  # Enlever le 'd'
                
                predictions[f'{model_type}_{period}d'] = {
                    'buy_probability': buy_proba,
                    'confidence': max(buy_proba, 1 - buy_proba),
                    'strategy_type': model_type,
                    'lookahead_period': period_val,
                    'signal_strength': abs(buy_proba - 0.5) * 2  # 0 à 1
                }
            except Exception as e:
                self.logger.error(f"Prediction error for {model_name}: {e}")
        
        return predictions
    
    def save_models(self):
        """Sauvegarde tous les modèles ML"""
        import os
        if not os.path.exists('tudor_ml_models'):
            os.makedirs('tudor_ml_models')

        for model_name, model_info in self.models.items():
            filename = f'tudor_ml_models/{model_name}.pkl'
            joblib.dump(model_info, filename)
        self.logger.info("All ML models saved")
    
    def load_models(self):
        """Charge tous les modèles ML"""
        import os
        
        if not os.path.exists('tudor_ml_models'):
            # If directory doesn't exist, just return comfortably
            self.logger.warning("tudor_ml_models directory not found. No models loaded.")
            return
        
        loaded_count = 0
        for filename in os.listdir('tudor_ml_models'):
            if filename.endswith('.pkl'):
                model_name = filename[:-4]  # Enlever .pkl
                try:
                    model_info = joblib.load(f'tudor_ml_models/{filename}')
                    self.models[model_name] = model_info
                    loaded_count += 1
                except Exception as e:
                     self.logger.error(f"Failed to load {filename}: {e}")

        
        self.logger.info(f"Loaded {loaded_count} ML models")
