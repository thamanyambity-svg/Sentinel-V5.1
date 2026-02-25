import torch
import torch.nn as nn
import torch.optim as optim
import json
import os
import numpy as np
from datetime import datetime

class NexusDeepCore(nn.Module):
    """
    Architecture LSTM/Deep-Q inspired pour NEXUS.
    Incorpore du Dropout pour prévenir l'Overfitting (Sur-apprentissage).
    """
    def __init__(self, input_dim=3, hidden_dim=64):
        super(NexusDeepCore, self).__init__()
        # Couche d'entrée dense adaptée pour 3 features [Tech, SPM, Imbalance]
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        # Couche LSTM pour la mémoire séquentielle
        self.lstm = nn.LSTM(hidden_dim, hidden_dim // 2, batch_first=True)
        # Couche de sortie avec Dropout
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(hidden_dim // 2, 1)
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, x):
        # x shape: (batch, seq, features)
        x = torch.relu(self.fc1(x))
        lstm_out, _ = self.lstm(x)
        # On prend le dernier état de la séquence
        x = lstm_out[:, -1, :]
        x = self.dropout(x)
        x = self.fc2(x)
        return self.sigmoid(x)

class NexusArchitect:
    """
    NEXUS (Module de Prédiction Adaptative & Gestion du Risque)
    Héberge le moteur Deep RL et la Détection de Régime de Marché.
    """
    def __init__(self):
        print("[NEXUS] 🧬 Activation du Moteur Deep RL (Liquidity Aware)...")
        self.model_path = "nexus_quantum_weights.pth"
        self.network = NexusDeepCore(input_dim=3) # Utilise maintenant 3 dimensions
        self.optimizer = optim.Adam(self.network.parameters(), lr=0.002)
        self.criterion = nn.BCELoss()
        self.accuracy_history = []
        
        if os.path.exists(self.model_path):
            try:
                self.network.load_state_dict(torch.load(self.model_path))
                print("[NEXUS] ✅ Poids Quantiques chargés. Analyseurs LSTM synchronisés.")
            except:
                print("[NEXUS] ⚠️ Anciens poids incompatibles (Passage à 3D). Réinitialisation.")

    def detect_market_regime(self, volatility, trend_strength):
        """Classification en 3 états : Trend, Range, ou Chaos."""
        if volatility > 2.5: return "CHAOS (HIGH VOLATILITY)"
        if abs(trend_strength) > 0.7: return "STRONG TREND"
        return "CONSOLIDATION (RANGE)"

    def solve_kill_switch(self):
        """Protocole Anti-Erreur : Interdiction de trading si l'IA perd sa précision.
        GRACE PERIOD : On attend 20 trades pour laisser le nouveau modèle 3D s'exprimer.
        """
        if len(self.accuracy_history) > 20: 
            recent_acc = np.mean(self.accuracy_history[-10:])
            if recent_acc < 0.45: # Seuil légèrement baissé pour la phase d'apprentissage
                print("[NEXUS] 🚨 KILL SWITCH ACTIVÉ : Précision critique (<45%). Mode Observation.")
                return True
        return False

    def predict_quantum_success(self, tech_signal, spm_score, imbalance=0.0):
        """Inférence Deep Learning avec 3 entrées [Tech, SPM, Imbalance]."""
        self.network.eval()
        t_val = 1.0 if tech_signal == "BUY" else -1.0
        
        # Format pour LSTM (Batch=1, Seq=1, Features=3)
        input_tensor = torch.FloatTensor([[[t_val, spm_score, imbalance]]])
        with torch.no_grad():
            prob = self.network(input_tensor).item()
        return prob

    def evolve_memory(self, trade_history):
        """Entraînement par Renforcement (Fine-tuning de la mémoire LSTM)."""
        if not trade_history: return
        self.network.train()
        
        inputs = []
        targets = []
        for t in trade_history:
            t_input = 1.0 if t['tech_signal'] == 'BUY' else -1.0
            inputs.append([[t_input, t['finbert_score'], t.get('imbalance', 0.0)]])
            targets.append([1.0 if t['profit'] > 0 else 0.0])
            self.accuracy_history.append(1.0 if t['profit'] > 0 else 0.0)

        X = torch.FloatTensor(inputs)
        y = torch.FloatTensor(targets)

        for _ in range(200):
            self.optimizer.zero_grad()
            pred = self.network(X)
            loss = self.criterion(pred, y)
            loss.backward()
            self.optimizer.step()
            
        torch.save(self.network.state_dict(), self.model_path)
        print(f"[NEXUS] 📉 Optimisation terminée. Erreur résiduelle : {loss.item():.5f}")

if __name__ == "__main__":
    n = NexusArchitect()
    print(f"Probabilité Nexus : {n.predict_quantum_success('BUY', 0.8)*100:.1f}%")
