import os
import json
import logging
import time
import urllib.request
import xml.etree.ElementTree as ET
import ssl
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# Load env
env_path = os.path.join(os.path.dirname(__file__), "../../.env")
load_dotenv(env_path)
load_dotenv(".env") # fallback

# Bypass SSL for RSS
ssl_context = ssl._create_unverified_context()

# Basic logging
logging.basicConfig(level=logging.INFO)

class GoldNewsAgent:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.feeds = [
            "https://www.forexlive.com/feed/news",
            "https://finance.yahoo.com/rss/headline?s=GC=F"
        ]
        self.output_file = "gold_sentiment.json"
        self.logger = logging.getLogger("GoldNewsAgent")
        
    def fetch_rss(self):
        headlines = []
        for url in self.feeds:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                    xml_data = response.read().decode('utf-8')
                    root = ET.fromstring(xml_data)
                    
                    # Try all common paths for headlines
                    for item in root.findall('.//item'):
                        title = item.find('title')
                        if title is not None and title.text:
                            headlines.append(title.text)
                    
                    # Try Atom format entries
                    for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
                        title = entry.find('{http://www.w3.org/2005/Atom}title')
                        if title is not None and title.text:
                            headlines.append(title.text)
                            
            except Exception as e:
                self.logger.error(f"Error fetching RSS {url}: {e}")
        return list(set(headlines))[:15] # Top 15 unique

    def analyze_sentiment(self, headlines):
        if not self.client or not headlines:
            return {"bias": "NEUTRAL", "score": 0, "summary": "No AI key or no headlines found."}
        
        prompt = f"""
        Analyze the following financial headlines for Gold (XAUUSD) market bias.
        Provide a concise response in JSON format with exactly these fields:
        - "bias": "BULLISH", "BEARISH", or "NEUTRAL"
        - "score": a number from -10 to 10
        - "summary": a one-sentence summary of the current primary market driver for Gold.
        
        Headlines:
        {chr(10).join(headlines)}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a senior macro gold trader."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            self.logger.error(f"AI Analysis error: {e}")
            return {"bias": "NEUTRAL", "score": 0, "summary": f"AI Analysis failed: {e}"}

    def fetch_twitter_news(self):
        headlines = []
        bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        if not bearer_token:
            self.logger.warning("No TWITTER_BEARER_TOKEN found. Skipping X/Twitter.")
            return headlines
            
        # URL encode the query: (XAUUSD OR #Gold) -is:retweet lang:en
        url = "https://api.twitter.com/2/tweets/search/recent?query=(XAUUSD%20OR%20%23Gold)%20-is%3Aretweet%20lang%3Aen&max_results=10"
        
        try:
            req = urllib.request.Request(url, headers={
                'Authorization': f'Bearer {bearer_token}',
                'User-Agent': 'v2RecentSearchPython'
            })
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    if "data" in data:
                        for tweet in data["data"]:
                            text = tweet.get("text", "").replace('\n', ' ').strip()
                            if text:
                                headlines.append(f"[X] {text}")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                self.logger.warning("X/Twitter API 403 Forbidden: Your tier might not support search/recent (Free Tier). Skipping.")
            else:
                self.logger.error(f"X/Twitter HTTP Error: {e.code} - {e.reason}")
        except Exception as e:
            self.logger.error(f"Error fetching from X/Twitter: {e}")
            
        return headlines

    def run(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Scanning Gold Market Fundamentals...")
        rss_headlines = self.fetch_rss()
        twitter_headlines = self.fetch_twitter_news()
        
        # Combine headlines
        headlines = twitter_headlines[:5] + rss_headlines[:10]
        
        analysis = self.analyze_sentiment(headlines)
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "headlines": headlines[:5],
            "analysis": analysis
        }
        
        # Write to local file for dashboard
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
            
        print(f"📊 Gold Bias: {analysis['bias']} ({analysis['score']}/10) - {analysis['summary']}")
        return result

if __name__ == "__main__":
    agent = GoldNewsAgent()
    # On change le nom pour matcher l'API
    agent.output_file = "sentiment_analysis.json"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Fundamental Intelligence Daemon started (30m interval)")
    while True:
        try:
            agent.run()
        except Exception as e:
            print(f"Error in daemon: {e}")
        
        # Sleep 30 minutes
        time.sleep(1800)
