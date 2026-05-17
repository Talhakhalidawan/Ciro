import os
import json
import requests
import google.generativeai as genai
from duckduckgo_search import DDGS
from django.conf import settings
import typing_extensions as typing

def search_youtube(query: str) -> dict:
    api_key = getattr(settings, 'YOUTUBE_API_KEY', None)
    results = []
    
    if api_key:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": f"Pakistan {query}",
            "type": "video",
            "order": "date",
            "maxResults": 5,
            "key": api_key
        }
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", []):
                    results.append({
                        "title": item["snippet"]["title"],
                        "description": item["snippet"]["description"]
                    })
                return {"platform": "youtube", "results": results}
        except Exception as e:
            print(f"YouTube API failed: {e}")

    # Fallback to DuckDuckGo Search
    print("Falling back to DuckDuckGo for YouTube search")
    try:
        with DDGS() as ddgs:
            search_query = f"site:youtube.com Pakistan {query}"
            for r in ddgs.text(keywords=search_query, timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG YouTube search failed: {e}")
        
    return {"platform": "youtube", "results": results}

def search_reddit(query: str) -> dict:
    client_id = getattr(settings, 'REDDIT_CLIENT_ID', None)
    client_secret = getattr(settings, 'REDDIT_CLIENT_SECRET', None)
    results = []
    
    if client_id and client_secret:
        # Simplistic reddit API search without auth if possible, or basic auth
        # Usually Reddit requires OAuth, but public endpoints might work with a custom user agent.
        # This is a placeholder for actual OAuth flow. We'll use public JSON endpoint.
        url = f"https://www.reddit.com/search.json?q={query}&sort=new&limit=5"
        headers = {'User-Agent': 'python:ciro_django_app:v1.0 (by /u/developer)'}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", {}).get("children", []):
                    results.append({
                        "title": item["data"]["title"],
                        "subreddit": item["data"]["subreddit"]
                    })
                return {"platform": "reddit", "results": results}
        except Exception as e:
            print(f"Reddit API failed: {e}")

    # Fallback
    print("Falling back to DuckDuckGo for Reddit search")
    try:
        with DDGS() as ddgs:
            search_query = f"site:reddit.com {query}"
            for r in ddgs.text(keywords=search_query, timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG Reddit search failed: {e}")
        
    return {"platform": "reddit", "results": results}

def search_telegram(query: str) -> dict:
    # Telegram doesn't have a simple public search API for messages without a bot/user client.
    # We will rely exclusively on DuckDuckGo fallback for web-indexed Telegram channels.
    results = []
    print("Using DuckDuckGo for Telegram search (no public HTTP search API available without auth)")
    try:
        with DDGS() as ddgs:
            search_query = f"site:t.me {query}"
            for r in ddgs.text(keywords=search_query, timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG Telegram search failed: {e}")
        
    return {"platform": "telegram", "results": results}

def search_google(query: str) -> dict:
    api_key = getattr(settings, 'GOOGLE_API_KEY', None)
    cx = getattr(settings, 'GOOGLE_CX', None)
    results = []
    
    if api_key and cx:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": 5
        }
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", []):
                    results.append({"title": item["title"], "snippet": item["snippet"]})
                return {"platform": "google", "results": results}
        except Exception as e:
            print(f"Google API failed: {e}")

    # Fallback to general DuckDuckGo Search
    print("Falling back to general DuckDuckGo search")
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(keywords=query, timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG search failed: {e}")
        
    return {"platform": "google", "results": results}

def analyze_with_ai(weather_diff: str, search_results: dict) -> dict:
    """
    Uses Gemini to analyze the weather difference and recent news.
    Returns a structured dictionary.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        return {"error": "GEMINI_API_KEY not configured."}
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")
    
    prompt = f"""
    You are an intelligent safety analysis assistant.
    The user's local weather has experienced a sudden, unusual change.
    Here is the summary of the weather change:
    {weather_diff}
    
    To gather more context, we performed parallel searches across multiple platforms.
    Here are the results:
    {json.dumps(search_results, indent=2)}
    
    Based on this data, assess if there is a dangerous situation (e.g., flood, storm, riot due to power outage, etc.).
    You MUST respond with a JSON object exactly matching this schema:
    {{
      "type": "alert|info|safe",
      "severity": "high|medium|low|none",
      "confidence": "high|medium|low",
      "title": "String",
      "details": "String (max 100 words)",
      "safety_advises": ["String", "String"],
      "help_resources": ["String", "String"],
      "notification_details": {{
        "type": "String",
        "title": "String (short)",
        "details": "String"
      }}
    }}
    
    If nothing seems dangerous, you can set type to "safe" and severity to "none".
    Respond ONLY with the JSON object, nothing else. No markdown formatting blocks around it.
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            )
        )
        # Parse the response as JSON
        # Note: we used response_mime_type="application/json", so the text is guaranteed to be JSON
        return {
            "prompt": prompt,
            "response_json": json.loads(response.text)
        }
    except Exception as e:
        print(f"Gemini API failed: {e}")
        return {
            "prompt": prompt,
            "response_json": {
                "type": "safe",
                "severity": "none",
                "confidence": "low",
                "title": "Analysis Failed",
                "details": "Failed to reach AI service.",
                "safety_advises": [],
                "help_resources": [],
                "notification_details": {"type": "info", "title": "Error", "details": "AI analysis failed."}
            }
        }
