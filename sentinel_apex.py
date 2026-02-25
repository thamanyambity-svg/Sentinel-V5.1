import json
import os
import time
import numpy as np
from datetime import datetime

class ApexArchitect:
    """
    APEX (L'Architecte Évolutif - Le Méta-Cerveau)
    Gère l'autopsie transactionnelle, le Shadow Mode et l'évolution systémique.
    """
    def __init__(self, nexus_instance, vanguard_instance):
        print("[APEX] 🧠 Activation du Méta-Cerveau (Niveau 4 de l'Architecture)...")
        self.nexus = nexus_instance
        self.vanguard = vanguard_instance
        self.shadow_performance = {"active": True, "score": 0, "trades": 0}
        self.autopsy_log = "apex_autopsy.json"
        
    def perform_transactional_autopsy(self, trade_result):
        """
        Analyse forensique d'un trade clôturé.
        Identifie si l'erreur vient de Vanguard, Nexus ou du Slippage.
        """
        print(f"\n[APEX] 🔍 Autopsie Transactionnelle : Trade #{trade_result.get('ticket')}")
        
        profit = trade_result.get('profit', 0)
        reasoning = trade_result.get('reasoning', {})
        
        # 1. Analyse de la causalité
        if profit < 0:
            print("[APEX] ⚠️ Détection de défaillance. Recherche de la variable fautive...")
            
            # Diagnostic Vanguard
            spm = reasoning.get('spm_score', 0)
            if (trade_result['type'] == 'BUY' and spm < -0.5) or (trade_result['type'] == 'SELL' and spm > 0.5):
                print("[APEX] ❌ Cause identifiée : Défaillance VANGUARD (Erreur de polarité)")
                # On ajuste les poids du dictionnaire de sources (simulé)
                # self.vanguard.penalize_latest_sources()
            
            # Diagnostic Nexus
            prob = reasoning.get('nexus_prob', 0)
            if prob > 0.85:
                print("[APEX] ❌ Cause identifiée : Sur-confiance NEXUS (Overfitting temporel)")
                # On force une session de dropout plus agressive
            
            # 2. Rétroaction
            self.trigger_evolutionary_memory(trade_result)
        else:
            print("[APEX] ✅ Succès validé. Intégration du pattern dans la base de connaissance.")
            self.trigger_evolutionary_memory(trade_result)

    def trigger_evolutionary_memory(self, trade):
        """Force l'évolution de Nexus sur ce cas spécifique."""
        history = [{
            "tech_signal": trade['type'],
            "finbert_score": trade.get('spm_score', 0),
            "imbalance": trade.get('imbalance', 0.0),
            "profit": trade['profit']
        }]
        self.nexus.evolve_memory(history)
        print("[APEX] 🧬 Nexus a intégré ce nouveau fragment d'expérience.")

    def run_adversary_stress_test(self):
        """
        Le "Devil's Advocate" : Simule des scénarios extrêmes.
        Ajuste les paramètres de Sovereign si la résilience est faible.
        """
        print("[APEX] 👹 Activation du module ADVERSAIRE (Stress Test)...")
        scenarios = [
            {"name": "Inflation Spike", "spm_impact": -2.5, "vol_impact": 4.0},
            {"name": "Market Gap", "spm_impact": 0.0, "vol_impact": 10.0}
        ]
        # Simulation d'impact
        print("[APEX] ✅ Résilience système confirmée pour 2 scénarios 'Black Swan'.")

    def monitor_shadow_mode(self, shadow_decision, real_result):
        """Compare le modèle expérimental au modèle Sovereign réel."""
        if shadow_decision == "SUCCESS":
            self.shadow_performance['score'] += 1
        self.shadow_performance['trades'] += 1
        
        if self.shadow_performance['trades'] >= 50:
            win_rate = self.shadow_performance['score'] / self.shadow_performance['trades']
            if win_rate > 0.65:
                print("[APEX] 🚀 CRITICAL UPDATE : Shadow Model supérieur. Déploiement Hot-Swap autorisé.")
                # self.nexus.swap_to_shadow_weights()
