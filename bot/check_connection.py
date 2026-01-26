import asyncio
import os
import sys

# Add current directory to path to allow imports
sys.path.append(os.getcwd())

from bot.config import runtime # Loads .env
from bot.broker.deriv.client import DerivClient

async def check():
    print("--- VÉRIFICATION CONNEXION DERIV ---")
    
    token = os.getenv("DERIV_API_TOKEN")
    print(f"1. Lecture Token: {'OK' if token and 'your_deriv' not in token else 'ERREUR (Token par défaut détecté)'}")
    
    if not token or 'your_deriv' in token:
        print(">>> ACTION REQUISE : Modifiez le fichier bot/.env avec votre vrai token.")
        return

    client = DerivClient()
    print("2. Tentative de connexion...")
    try:
        await client.connect()
        print("3. Connexion WebSocket: RÉUSSIE ✅")
        
        balance = await client.get_balance()
        if balance:
            print(f"   Compte: {balance.get('loginid', 'N/A')}")
            print(f"   Solde: {balance['balance']} {balance['currency']}")
            print("--- TOUT EST OK ---")
        else:
            print("4. Authentification: ÉCHOUÉE ❌ (Vérifiez que le token est valide)")
            
        await client.close()
            
    except Exception as e:
        print(f"ERREUR CRITIQUE: {e}")

if __name__ == "__main__":
    asyncio.run(check())
