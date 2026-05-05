"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL AGENTS — base.py  (Architecture 3 Niveaux V7.25)          ║
║                                                                        ║
║  TIER 1 — Ollama qwen2.5:0.5b  → Agents simples (local, ~5-10s)      ║
║  TIER 2 — Groq llama3-8b       → Agents analytiques (cloud, ~1-3s)   ║
║  TIER 3 — Groq llama3-70b      → CIO, Risk, Avocat (cloud, ~2-5s)    ║
║                                                                        ║
║  Raison : Ollama charge les modèles à froid (60-120s).               ║
║  Groq API (GROQ_API_KEY dans .env) = inférence cloud instantanée.    ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL  = "http://127.0.0.1:11434/api/generate"
GROQ_URL    = "https://api.groq.com/openai/v1/chat/completions"
GROQ_KEY    = os.getenv("GROQ_API_KEY", "")

# ── Configuration par Tier ──────────────────────────────────────────────────
TIER_CONFIG = {
    # Local Ollama — agents simples, données brutes
    1: {
        "backend": "ollama",
        "model":   "qwen2.5:0.5b",
        "timeout": 60,
    },
    # Groq Cloud — agents analytiques (llama-3.1-8b-instant = rapide + capable)
    2: {
        "backend": "groq",
        "model":   "llama-3.1-8b-instant",
        "timeout": 30,
    },
    # Groq Cloud — agents critiques (llama-3.3-70b-versatile = meilleur raisonnement actuel)
    3: {
        "backend": "groq",
        "model":   "llama-3.3-70b-versatile",
        "timeout": 60,
    },
}


def _call_ollama(prompt: str, model: str, timeout: int) -> str:
    """Appel au LLM local Ollama."""
    try:
        r = requests.post(OLLAMA_URL, json={
            "model":  model,
            "prompt": prompt,
            "stream": False,
        }, timeout=timeout)
        if r.status_code == 200:
            return r.json().get("response", "").strip()
        return f"[ERREUR OLLAMA HTTP {r.status_code}]"
    except Exception as e:
        return f"[ERREUR OLLAMA: {e}]"


def _call_groq(prompt: str, model: str, timeout: int) -> str:
    """Appel à l'API Groq (OpenAI-compatible)."""
    if not GROQ_KEY:
        return "[ERREUR: GROQ_API_KEY manquant dans .env]"
    try:
        r = requests.post(GROQ_URL, headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type":  "application/json",
        }, json={
            "model":    model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "temperature": 0.3,
        }, timeout=timeout)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return f"[ERREUR GROQ HTTP {r.status_code}: {r.text[:200]}]"
    except Exception as e:
        return f"[ERREUR GROQ: {e}]"


def call_llm(prompt: str, tier: int = 2) -> str:
    """
    Routeur principal des agents.

    tier=1 → Ollama qwen2.5:0.5b   — Comptable, Guardian, Compliance, Liquidité
    tier=2 → Groq llama-3.1-8b     — Macro, Quant, Sentiment, Régime, Shadow...
    tier=3 → Groq llama3-70b       — CIO, Risk Manager, Avocat du Diable
    """
    config  = TIER_CONFIG.get(tier, TIER_CONFIG[2])
    backend = config["backend"]
    model   = config["model"]
    timeout = config["timeout"]

    if backend == "groq":
        return _call_groq(prompt, model, timeout)
    else:
        return _call_ollama(prompt, model, timeout)
