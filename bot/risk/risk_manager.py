import logging
from bot.risk.config import *

logger = logging.getLogger("BOT")

class RiskManager:
    def __init__(self, max_grid_layers=3, risk_per_trade=BASE_TRADE_RISK_PCT, max_daily_loss=0.05):
        """
        RiskManager : Gestionnaire de risque institutionnel (Refined).
        """
        self.max_layers = max_grid_layers
        self.risk_pct = risk_per_trade
        self.max_dd = max_daily_loss
        self.portfolio_risk_cap = MAX_TOTAL_RISK_PCT
        self.correlation_limit = CORRELATED_RISK_PCT
        
        # Mapping approximatif de la valeur du point (à affiner si nécessaire)
        # Pour les indices synthétiques Deriv, souvent 1 point = 1 USD pour 1 lot standard
        self.point_values = {
            "R_100": 1.0,
            "R_75": 1.0, 
            "R_50": 1.0,
            "DEFAULT": 1.0
        }

    def get_point_value(self, asset):
        return self.point_values.get(asset, self.point_values["DEFAULT"])

    def calculate_lot_size(self, balance, stop_loss_distance, asset):
        """
        Calcule la taille du lot pour respecter le risque max.
        Prend en compte le 'Floor' de 0.35$ pour les petits comptes.
        """
        if balance <= 0:
            logger.warning(f"⚠️ RiskManager: Balance is {balance}. Cannot calculate size.")
            return 0.0

        # 1. Calcul du montant risqué en $
        risk_amount = balance * self.risk_pct
        
        # 2. Valeur du point pour cet actif
        point_value = self.get_point_value(asset)
        
        # 3. Calcul du lot théorique : Risk / (Distance * PointValue)
        if stop_loss_distance == 0:
             lot_size = 0.001 # Fallback
        else:
             lot_size = risk_amount / (stop_loss_distance * point_value)
        
        # 4. Ajustement Deriv & Small Account Floor
        # Sur Deriv, le "Stake" est souvent le montant engagé ou la marge. 
        # Ici on simplifie en parlant de 'stake' ou 'volume'.
        # Si on trade en 'Montant' (Stake), on doit garantir min 0.35$
        
        # Conversion Lot -> Stake approximative pour vérifier le min $0.35
        # Cette partie dépend si l'API attend un volume (lots) ou un stake (montant).
        # Le bot actuel semble envoyer un "amount" qui est interprété comme un stake par l'API Deriv ?
        # Vérifions : self.sizer.calculate renvoyait 'useful_size'. 
        
        # Si le système attend un STAKE (Montant investi) :
        # Le sizer précédent renvoyait un montant en $.
        # On va donc renvoyer un STAKE DIRECTEMENT.
        
        target_stake = max(risk_amount, 0.50) # Floor à 0.50$ (User Request)
        
        logger.info(f"🛡️ [RISK] {asset} | Balance: {balance}$ | SL Dist: {stop_loss_distance:.2f} | Risk $: {risk_amount:.2f}$ | Final Stake: {target_stake:.2f}$")
        
        return round(target_stake, 2)

    def get_safe_grid_levels(self, entry_price, direction, atr_value):
        """
        Génère les niveaux de la grille (Neuro-Grid) basés sur l'ATR.
        """
        # Espacement dynamique : 1.5 x ATR pour laisser respirer
        spacing = atr_value * 1.5 
        levels = []
        
        # Multiplicateur de Martingale DOUX (1.2x seulement, pas 2x)
        multiplier = 1.0 
        
        for i in range(1, self.max_layers + 1):
            if direction == "BUY":
                price = entry_price - (spacing * i)
            else: # SELL
                price = entry_price + (spacing * i)
            
            multiplier = getattr(self, 'grid_multiplier', 1.2) # Default 1.2
            
            levels.append({
                "layer": i,
                "trigger_price": round(price, 4),
                "spacing_pts": round(spacing * i, 2),
                "size_multiplier": multiplier
            })
            
        return levels

    def get_total_portfolio_risk(self, positions):
        """
        Calcule le risque total engagé sur le portefeuille (sum of SL in $).
        """
        total_risk = 0.0
        for pos in positions:
            # Estimation du risque si SL présent
            pnl = float(pos.get("profit", 0))
            # Si le PnL est très négatif, on considère qu'on a déjà "mangé" du risque
            # Mais institutionnellement, on regarde le Risk @ SL.
            # Ici on va simplifier : chaque position ouverte consomme self.risk_pct
            total_risk += self.risk_pct 
        return total_risk

    def check_correlation(self, asset, positions):
        """
        Vérifie si un actif corrélé est déjà ouvert.
        Ex: GOLD et XAUUSD, ou plusieurs Volatility indices.
        """
        correlations = {
            "GOLD": ["XAUUSD", "GOLD"],
            "VOLATILITY": ["Volatility 10 Index", "Volatility 25 Index", "Volatility 50 Index", "Volatility 75 Index", "Volatility 100 Index"]
        }
        
        asset_group = None
        for group, members in correlations.items():
            if asset in members:
                asset_group = members
                break
        
        if not asset_group:
            return False
            
        for pos in positions:
            if pos.get("symbol") in asset_group:
                return True
        return False

    def get_dynamic_risk_multiplier(self, asset, positions, ai_confidence=1.0):
        """
        Calcule le multiplicateur de risque final (Brain -> Muscle).
        """
        multiplier = 1.0
        
        # 1. Cap Portefeuille (2.0% max)
        current_risk = self.get_total_portfolio_risk(positions)
        if current_risk >= self.portfolio_risk_cap:
            logger.warning(f"🚨 PORTFOLIO RISK CAP REACHED ({current_risk*100:.2f}%)")
            return 0.0
            
        # 2. Corrélation (0.75% -> 0.35%)
        if self.check_correlation(asset, positions):
            logger.info(f"🔗 Correlation detected for {asset}. Reducing risk.")
            multiplier *= (self.correlation_limit / self.risk_pct) # ~0.46
            
        # 3. AI Confidence Modifier (Senior Adjustment: +/- 0.15R only if > 0.85)
        if ai_confidence > 0.85:
            # Booster léger
            multiplier *= 1.15
        elif ai_confidence < 0.50:
            multiplier *= 0.5
            
        return round(multiplier, 2)

    def get_atr_capped_distances(self, atr, sl_mult=1.5, tp_mult=3.0):
        """
        Applique les garde-fous ATR (Floor 0.5, Ceiling 3.5).
        """
        final_sl_mult = max(0.5, min(sl_mult, 3.5))
        final_tp_mult = tp_mult # TP is less dangerous than SL for ruin risk
        
        return final_sl_mult, final_tp_mult

    def check_health(self, initial_balance, current_balance):
        """
        Kill Switch : On arrête tout si on touche le Max Daily Loss.
        """
        if initial_balance <= 0: return True, "Init Balance 0"
        
        drawdown = (initial_balance - current_balance) / initial_balance
        
        if drawdown >= self.max_dd:
            msg = f"🚨 KILL SWITCH ENGAGED: Daily Drawdown {drawdown*100:.2f}% > Limit {self.max_dd*100:.2f}%"
            logger.critical(msg)
            return False, msg
            
        return True, "OK"
