import os
import json
import requests
import google.generativeai as genai
from duckduckgo_search import DDGS
from datetime import datetime

# --- CONFIGURATION ---
try:
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
    DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
except KeyError:
    print("Error: Secrets not found. Make sure GEMINI_API_KEY and DISCORD_WEBHOOK_URL are set in GitHub Settings.")
    exit(1)

HISTORY_FILE = "data/history.json"

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

def get_latest_news():
    """
    Uses DuckDuckGo (Free) to find the absolute latest news/posts.
    """
    print("Searching for latest Trump/Iran news...")
    try:
        results = DDGS().text("Donald Trump Truth Social Iran nuclear deal latest news", max_results=5)
        # Combine the search snippets into one block of text for the AI to read
        if results:
            news_summary = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
            return news_summary
        return ""
    except Exception as e:
        print(f"Search failed: {e}")
        return ""

def analyze_with_gemini(news_text):
    """
    Feeds the search results to Gemini for high-level financial analysis.
    """
    if not news_text:
        return {"found_new_update": False}

    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""
    You are an expert geopolitical financial analyst (GoldSentinel).
    
    HERE IS THE LATEST RAW NEWS/SEARCH DATA:
    {news_text}
    
    INSTRUCTIONS:
    1. specific focus: Look for ANY new (last 24h) statement by Donald Trump or US/Iran officials regarding the "Iran Nuclear Deal" or "War".
    2. If the news is old, irrelevant, or just generic summaries, return "found_new_update": false.
    3. If there is RELEVANT, BREAKING news, analyze it:
       - SENTIMENT: "Hawkish" (War/Threats) or "Doveish" (Diplomacy/Deal).
       - GOLD_FORECAST: 
         * "Bullish" (Price UP) if sentiment is Hawkish/Uncertainty.
         * "Bearish" (Price DOWN/Crash) if sentiment is Doveish/Peace Deal.
    
    RETURN ONLY RAW JSON (No markdown):
    {{
        "found_new_update": true,
        "source_text": "A brief 1-sentence summary of the specific event/post.",
        "timestamp": "{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "sentiment": "Hawkish/Doveish/Neutral",
        "gold_forecast": "Bullish/Bearish",
        "reasoning": "A short explanation of why gold will move this way."
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"AI Analysis failed: {e}")
        return {"found_new_update": False}

def send_alert(data):
    # Color: Red (Bearish/Drop) = 15158332, Green (Bullish/Rise) = 3066993
    color = 15158332 if "Bearish" in data.get('gold_forecast', '') else 3066993
    
    embed = {
        "title": "🚨 GoldSentinel Alert",
        "description": data.get('source_text'),
        "color": color,
        "fields": [
            {"name": "Sentiment", "value": data.get('sentiment', 'N/A'), "inline": True},
            {"name": "Gold Forecast", "value": data.get('gold_forecast', 'N/A'), "inline": True},
            {"name": "Reasoning", "value": data.get('reasoning', 'N/A')}
        ],
        "footer": {"text": "Powered by Gemini 2.0 & GitHub Actions"}
    }

    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        print("Alert sent to Discord.")
    except Exception as e:
        print(f"Discord Alert Failed: {e}")

def main():
    # 1. Search Web
    news_data = get_latest_news()
    
    # 2. Analyze with AI
    analysis = analyze_with_gemini(news_data)
    
    # 3. Process Result
    if analysis.get("found_new_update"):
        # Load History
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    history = json.load(f)
            except:
                history = []
        
        # Check for duplicates
        # NOTE: For Test Mode, we DISABLE the duplicate check so it fires every time
        # In real mode, you would uncomment the next line
        # last_summary = history[0]['source_text'] if history else ""
        
        # if analysis['source_text'] != last_summary: (Disabled for test)
        if True: 
            print(f"New update found: {analysis['source_text']}")
            send_alert(analysis)
            
            # Save to database
            history.insert(0, analysis)
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history[:50], f, indent=2)
    else:
        print("No significant new updates found.")

if __name__ == "__main__":
    main()
