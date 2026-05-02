import requests

MODEL = "tinyllama"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

def call_llm(prompt: str, timeout: int = 120) -> str:
    """Envoie un prompt au LLM local Ollama et retourne la réponse."""
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }, timeout=timeout)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        return f"[ERREUR HTTP {response.status_code}]"
    except Exception as e:
        return f"[ERREUR CONNEXION OLLAMA: {e}]"
