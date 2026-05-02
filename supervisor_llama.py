import requests
import json
from datetime import datetime

# Couleurs pour le terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def get_sentinel_data():
    """Récupère les données du compte depuis l'API Sentinel"""
    try:
        response = requests.get('http://127.0.0.1:5000/api/v1/account', timeout=5)
        if response.status_code == 200:
            return response.json().get('data', {})
        return None
    except Exception as e:
        print(f"{Colors.FAIL}Erreur de connexion à Sentinel: {e}{Colors.ENDC}")
        return None

def ask_llama3_supervisor(account_data):
    """Envoie les données au LLM local (Ollama) pour analyse"""
    
    prompt = f"""Tu es le Superviseur de Risque d'un système de trading algorithmique institutionnel appelé 'Sentinel'.
Ton rôle est d'analyser l'état actuel du compte et de donner une recommandation claire sur la sécurité du système.

Voici les données en direct du compte de trading (MT5) :
- Capital (Balance) : {account_data.get('balance')} $
- Drawdown actuel : {account_data.get('drawdown')} %
- Positions ouvertes : {account_data.get('positions_count')}
- Trading Automatique : {'Activé' if account_data.get('trading_enabled') else 'Désactivé'}

Fais une analyse très courte, professionnelle et stricte (en français). 
Conclus en disant si le système est autorisé à prendre de nouveaux trades. Ne fais pas de mise en garde générique, sois précis."""

    payload = {
        "model": "tinyllama",
        "prompt": prompt,
        "stream": False
    }

    print(f"\n{Colors.OKCYAN}{Colors.BOLD}🔍 Interrogation du Superviseur Llama 3 en cours...{Colors.ENDC}\n")
    
    try:
        response = requests.post('http://127.0.0.1:11434/api/generate', json=payload, timeout=600)
        if response.status_code == 200:
            return response.json().get('response', '')
        return "Erreur du modèle."
    except Exception as e:
        return f"Erreur de connexion à Ollama: {e}"

if __name__ == "__main__":
    print(f"{Colors.BOLD}{Colors.WARNING}======================================={Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.WARNING}    SENTINEL AI SUPERVISOR (LLAMA 3)   {Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.WARNING}======================================={Colors.ENDC}")
    
    # 1. Fetch data
    data = get_sentinel_data()
    if not data:
        print("Impossible de contacter l'API Sentinel. Vérifie que api_server.py tourne.")
        exit(1)
        
    print(f"{Colors.OKGREEN}✓ Données MT5 récupérées avec succès.{Colors.ENDC}")
    
    # 2. Analyze with Llama 3
    analysis = ask_llama3_supervisor(data)
    
    # 3. Print Output
    print(f"{Colors.BOLD}🤖 RAPPORT DU SUPERVISEUR :{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{analysis}{Colors.ENDC}")
    print("\n")
