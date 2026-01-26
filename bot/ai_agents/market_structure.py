"""
Market Structure Agent (Groq Powered)
Performs intelligent technical analysis on raw candle data.
Replaces simple RSI with pattern recognition.
"""
from bot.ai_agents.base_agent import BaseAgent
from typing import Dict, Any, List
import pandas as pd

class MarketStructureAgent(BaseAgent):
    """
    Analyzes price action, market structure, and patterns.
    Uses Groq for high-speed inference.
    """
    
    PROMPT = """
You are an expert Technical Analyst specializing in Price Action.
Analyze the provided OHLC candle data (last 30 candles) for the asset '{asset}'.

CONTEXTUALLY IMPORTANT DATA (GROUND TRUTH):
- Current Price: {current_price}
- Current RSI (14): {rsi}

📊 ANALYSE QUANTIQUE (FILTRE DE KALMAN) :
- Prix "Vrai" Estimé (Sans Bruit) : {q_price}
- Écart (Gap) : {q_gap} 
  (Si Gap > 0 : Le prix de marché est 'Trop Haut' / Surchauffé)
  (Si Gap < 0 : Le prix de marché est 'Trop Bas' / Exagéré à la baisse)
- Vélocité (Vitesse de la tendance) : {q_velocity}
  (Si Vélocité proche de 0 : Le marché stagne, attention aux faux signaux)
  (Si Vélocité > 0.5 ou < -0.5 : Tendance violente confirmée)

🧠 ANALYSE NEURONALE (ORACLE) :
- Prédiction : {oracle_direction} ({oracle_perf}%)
- Prix Cible IA : {oracle_prediction}

### Your Task
Identify the immediate market structure and recurring price patterns based on the provided data and the calculated indicators above. DO NOT INVENT NUMBERS. Use the provided Ground Truth.

TACHE STRATÉGIQUE (MODE ALPHA) :
Utilise le "Gap Quantique" pour valider tes entrées (PRIORITÉ ABSOLUE) :
1. **LOI DE LA VÉLOCITÉ** : Si Vélocité > 0.5 (Expansion), suis la tendance. Si Vélocité proche de 0, favorise le Mean Reversion aux extrêmes (RSI).
2. **LOI DU GAP** : Si Gap > 0 (Surchauffe), cherche uniquement des VENTES. Si Gap < 0 (Sous-évalué), cherche uniquement des ACHATS.
3. **CONFIRMATION** : Si l'Oracle et la Vélocité sont en désaccord, **FAIS CONFIANCE À LA VÉLOCITÉ**. C'est la réalité physique du marché.
4. Décision : BUY, SELL ou WAIT. Soyez impitoyable. Pas de "peut-être".

Look for:
1. **Trend**: Higher Highs/Lows (Bullish) or Lower Highs/Lows (Bearish).
2. **Key Levels**: Support and Resistance zones.
3. **Patterns**: Double Top/Bottom, Head & Shoulders, Engulfing, Pinbars, Liquidity Sweeps.
4. **Volume/Volatility**: Expansion or Contraction.

### Input Data
{candles_text}

### Output Requirements
Return a SINGLE JSON object.
- **signal**: BUY | SELL | WAIT
- **confidence**: 0.0 to 1.0
- **Stop Loss**: Suggested SL level based on structure.

**JSON Schema:**
{{
  "signal": "BUY | SELL | WAIT",
  "trend": "BULLISH | BEARISH | RANGING",
  "pattern": "Name of pattern detected (e.g. 'Bullish Engulfing')",
  "reason": "Concise explanation of price action",
  "key_level": 12345.67, 
  "suggested_sl": 12300.00,
  "confidence": 0.85
}}
"""
    
    def __init__(self):
        super().__init__(
            agent_name="MarketStructure",
            prompt_template=self.PROMPT
        )
    
    def get_expected_schema(self) -> Dict[str, Any]:
        return {
            "signal": "WAIT",
            "trend": "RANGING",
            "pattern": "None",
            "reason": "Initializing",
            "key_level": 0.0,
            "suggested_sl": 0.0,
            "confidence": 0.0
        }
    
    def _format_candles(self, candles: List[Dict]) -> str:
        """Format last 30 candles into a dense text representation"""
        if not candles: return "No Data"
        
        # Take last 20-30 candles
        subset = candles[-30:]
        
        lines = []
        for c in subset:
            # Timestamp (epoch) to readable index or minimal time
            # For efficiency, we just use open/high/low/close
            line = f"O:{c['open']} H:{c['high']} L:{c['low']} C:{c['close']}"
            lines.append(line)
            
        return "\n".join(lines)

    def _build_prompt(self, data: Dict[str, Any]) -> str:
        candles = data.get("candles", [])
        candles_text = self._format_candles(candles)
        
        return self.PROMPT.format(
            asset=data.get("asset", "Unknown"),
            candles_text=candles_text,
            current_price=data.get("current_price", "N/A"),
            rsi=f"{data.get('rsi', 0.0):.2f}",
            q_price=f"{data.get('quantum', {}).get('true_price', 0.0):.2f}",
            q_gap=f"{data.get('quantum', {}).get('gap', 0.0):.2f}",
            q_velocity=f"{data.get('quantum', {}).get('velocity', 0.0):.4f}",
            oracle_prediction=f"{data.get('oracle', {}).get('prediction', 'N/A')}",
            oracle_direction=data.get('oracle', {}).get('direction', 'N/A'),
            oracle_perf=f"{data.get('oracle', {}).get('perf', 0.0):.2f}"
        )

    def _get_fallback_response(self) -> Dict[str, Any]:
        return {
            "signal": "WAIT",
            "trend": "RANGING",
            "pattern": "Error/Timeout",
            "reason": "Agent Failed",
            "confidence": 0.0
        }
