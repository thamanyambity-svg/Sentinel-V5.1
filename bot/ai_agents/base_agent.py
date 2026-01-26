"""
Base Agent Class for AI Governance
Enforces deterministic, JSON-only, veto-based analysis
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any
import os
import threading

logger = logging.getLogger("AI_AGENT")

# Global synchronization for AI API calls (OpenAI 3 RPM Limit)
AI_SERIAL_LOCK = threading.Lock()
LAST_AI_EXECUTION_TIME = 0.0

class BaseAgent(ABC):
    """
    Abstract base class for all AI agents.
    Enforces:
    - JSON-only I/O
    - Deterministic analysis
    - Veto-only power (can block, never authorize)
    - Conservative bias (when in doubt, protect capital)
    """
    
    SYSTEM_RULES = """
You are an analytical risk assistant.
You must not predict markets, prices, or future direction.
You must not suggest trades, entries, exits, or position sizes.
You must only analyze the provided data and return a structured JSON.
If data is insufficient or inconsistent, return a blocking signal.
Be conservative. When in doubt, favor capital protection.
"""
    
    def __init__(self, agent_name: str, prompt_template: str):
        self.agent_name = agent_name
        self.prompt_template = prompt_template
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.xai_key = os.getenv("XAI_API_KEY")
        self.deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.timeout_ms = int(os.getenv("AI_TIMEOUT_MS", "30000"))  # Increased to 30s for stability
        # LOUD DEBUG
        print(f"DEBUG: Agent [{self.agent_name}] Keys: OpenAI={bool(self.openai_key)}, DeepSeek={bool(self.deepseek_key)}, xAI={bool(self.xai_key)}, Groq={bool(self.groq_key)}")

    
    @abstractmethod
    def get_expected_schema(self) -> Dict[str, Any]:
        """Define the expected JSON output schema"""
        pass
    
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pure function: data in → decision out
        
        Args:
            data: Market/risk data as dict
            
        Returns:
            Structured JSON decision
        """
        try:
            # Build prompt
            prompt = self._build_prompt(data)
            
            # Call LLM
            response = self._call_llm(prompt)
            logger.info(f"[{self.agent_name}] Raw LLM Response: {response[:200]}...") # Debug log
            
            # Parse and validate JSON
            result = self._parse_response(response)
            logger.info(f"[{self.agent_name}] Parsed Type: {type(result)}")

            
            # Validate schema
            self._validate_schema(result)
            
            logger.info(f"[{self.agent_name}] Analysis complete: {result}")
            return result
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error: {e}")
            if 'response' in locals():
                logger.error(f"[{self.agent_name}] Failed Response Content: {response}")
            # Fallback: block on error
            return self._get_fallback_response()
    
    def _build_prompt(self, data: Dict[str, Any]) -> str:
        """Build the full prompt with system rules + data"""
        data_json = json.dumps(data, indent=2)
        return f"{self.SYSTEM_RULES}\n\n{self.prompt_template}\n\nInput data:\n{data_json}"

    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM API (OpenAI -> DeepSeek -> xAI -> Groq)
        Thread-safe throttling for Free Tier (3 RPM Limit)
        """
        import time
        global LAST_AI_EXECUTION_TIME

        with AI_SERIAL_LOCK:
            now = time.time()
            elapsed = now - LAST_AI_EXECUTION_TIME
            if elapsed < 22: # ~2.7 RPM safety margin
                sleep_time = 22 - elapsed
                logger.info(f"[{self.agent_name}] Serializing AI: sleeping {sleep_time:.1f}s...")
                time.sleep(sleep_time)
            
            # Timestamp updated BEFORE the call to reserve the slot
            LAST_AI_EXECUTION_TIME = time.time()

        # 0. Try OpenAI (Primary Choice for Stability)
        if self.openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_key)
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini", # Optimized for speed/cost
                    messages=[
                        {"role": "system", "content": self.SYSTEM_RULES},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    max_tokens=512,
                    response_format={"type": "json_object"}
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"[{self.agent_name}] OpenAI Call Failed: {e}. Falling back...")

        # 1. Try DeepSeek (OpenAI compatible)
        if self.deepseek_key:
            try:
                from openai import OpenAI
                client = OpenAI(
                    api_key=self.deepseek_key,
                    base_url="https://api.deepseek.com"
                )
                
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": self.SYSTEM_RULES},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    max_tokens=512,
                    response_format={"type": "json_object"}
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"[{self.agent_name}] DeepSeek Call Failed: {e}. Falling back...")

        # 2. Try Grok (xAI)
        if self.xai_key:
            try:
                from openai import OpenAI
                client = OpenAI(
                    api_key=self.xai_key,
                    base_url="https://api.x.ai/v1"
                )
                
                response = client.chat.completions.create(
                    model="grok-beta",
                    messages=[
                        {"role": "system", "content": self.SYSTEM_RULES},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    max_tokens=1024,
                    response_format={"type": "json_object"}
                )
                return response.choices[0].message.content

            except Exception as e:
                err_msg = str(e).lower()
                if "429" in err_msg or "rate" in err_msg or "quota" in err_msg:
                    logger.warning("🕒 [ECO-MODE] xAI Quota Reached. High Latency Cooling (60s)...")
                    time.sleep(60)
                
                logger.error(f"[{self.agent_name}] xAI Call Failed: {e}. Falling back...")

        # 3. Try Groq
        if self.groq_key:
            logger.info(f"[{self.agent_name}] 🚀 Attempting Groq (llama-3.1-8b-instant)...")
            try:
                from groq import Groq
                client = Groq(api_key=self.groq_key)
                
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": self.SYSTEM_RULES},
                        {"role": "user", "content": prompt}
                    ],
                    model="llama-3.1-8b-instant", # Use smaller model for better quota availability
                    temperature=0.0,
                    max_tokens=1024,
                    response_format={"type": "json_object"}
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                logger.error(f"❌ [{self.agent_name}] Groq Call Failed: {e}")

        # 4. Final Fallback to Mock
        logger.warning(f"[{self.agent_name}] No working AI Provider found. Returning MOCK.")
        return json.dumps(self.get_expected_schema())
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response as JSON"""
        try:
            # Clean Markdown if present
            clean_response = response.strip()
            
            # Find first { and last } to handle surrounding text
            start_idx = clean_response.find('{')
            end_idx = clean_response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                clean_response = clean_response[start_idx : end_idx + 1]
            
            return json.loads(clean_response)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.agent_name}] Invalid JSON: {e} | Content: {response}")
            raise
    
    def _validate_schema(self, result: Dict[str, Any]):
        """Validate that result matches expected schema"""
        expected = self.get_expected_schema()
        for key in expected.keys():
            if key not in result:
                raise ValueError(f"Missing required field: {key}")
    
    @abstractmethod
    def _get_fallback_response(self) -> Dict[str, Any]:
        """Return conservative fallback on error"""
        pass
