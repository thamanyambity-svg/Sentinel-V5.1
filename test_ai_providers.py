import os
import json
import logging
from dotenv import load_dotenv
from openai import OpenAI

# Load env
env_path = "/Users/macbookpro/Downloads/bot_project/bot/.env"
load_dotenv(env_path, override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AI_TEST")

def test_openai():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("❌ OpenAI Key missing")
        return
    
    print(f"Testing OpenAI with key: {key[:10]}...")
    try:
        client = OpenAI(api_key=key)
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Return a JSON: {'status': 'ok'}"}],
            response_format={"type": "json_object"}
        )
        print(f"✅ OpenAI Success: {res.choices[0].message.content}")
    except Exception as e:
        print(f"❌ OpenAI Failed: {e}")

def test_deepseek():
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        print("❌ DeepSeek Key missing")
        return
    
    print(f"Testing DeepSeek with key: {key[:10]}...")
    try:
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Return a JSON: {'status': 'ok'}"}],
            response_format={"type": "json_object"}
        )
        print(f"✅ DeepSeek Success: {res.choices[0].message.content}")
    except Exception as e:
        print(f"❌ DeepSeek Failed: {e}")

if __name__ == "__main__":
    test_openai()
    print("-" * 20)
    test_deepseek()
