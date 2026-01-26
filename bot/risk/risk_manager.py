
import logging
import math

logger = logging.getLogger("BOT")

class RiskManager:
    def __init__(self, max_grid_layers=3, risk_per_trade=0.015, max_daily_loss=0.10):
        """
        RiskManager : Gestionnaire de risque institutionnel.
        max_grid_layers : Nombre max d'étages pour le Safe Grid.
        risk_per_trade : % du capital risqué par trade (Ex: 1.5%).
        max_daily_loss : Seuil de perte journalière (Kill Switch).
        """
        self.max_layers = max_grid_layers
        self.risk_pct = risk_per_trade
        self.max_dd = max_daily_loss
        
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
