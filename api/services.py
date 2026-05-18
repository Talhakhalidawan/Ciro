import os
import json
import requests
import google.generativeai as genai
from ddgs import DDGS
from django.conf import settings
import typing_extensions as typing

def search_youtube(query: str) -> dict:
    api_key = getattr(settings, 'YOUTUBE_API_KEY', None)
    results = []
    
    if api_key:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
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
            search_query = f"site:youtube.com {query}"
            for r in ddgs.text(query=search_query, region='pk-en', timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG YouTube search failed: {e}")
        
    return {"platform": "youtube", "results": results}

def search_reddit(query: str) -> dict:
    client_id = getattr(settings, 'REDDIT_CLIENT_ID', None)
    client_secret = getattr(settings, 'REDDIT_CLIENT_SECRET', None)
    results = []
    
    if client_id and client_secret:
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
            for r in ddgs.text(query=search_query, region='pk-en', timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG Reddit search failed: {e}")
        
    return {"platform": "reddit", "results": results}

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
            for r in ddgs.text(query=query, region='pk-en', timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG search failed: {e}")
        
    return {"platform": "google", "results": results}

def generate_search_keywords(weather_diff: str) -> dict:
    """
    Uses Gemini to generate highly specific search keywords based on a detected weather anomaly.
    Generates English and Roman Urdu keywords, optimized for searching news in Pakistan.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        return {"keywords": ["weather anomaly Pakistan"]}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    
    prompt = f"""
    The local weather in Pakistan has experienced a sudden, unusual change.
    Anomaly Details: {weather_diff}
    
    You need to generate precise, highly-relevant, short search keywords (2-3 words each) to find recent social media posts, news, videos, or announcements about this situation.
    Provide keywords in both English and Roman Urdu (e.g., "garmi alert", "sylab rawalpindi", "aandhi storm").
    
    You MUST respond with a JSON object matching this schema:
    {{
      "keywords_english": ["string", "string"],
      "keywords_roman_urdu": ["string", "string"]
    }}
    
    Provide exactly 2 keywords per category, keeping them short, clean, and highly specific to the anomaly in Pakistan.
    Respond ONLY with the JSON object, nothing else. No markdown formatting.
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            )
        )
        data = json.loads(response.text)
        # Combine the lists and remove duplicates
        all_keywords = list(set(data.get("keywords_english", []) + data.get("keywords_roman_urdu", [])))
        if not all_keywords:
            all_keywords = ["weather anomaly Pakistan"]
        return {
            "keywords": all_keywords,
            "keywords_english": data.get("keywords_english", []),
            "keywords_roman_urdu": data.get("keywords_roman_urdu", [])
        }
    except Exception as e:
        print(f"Error generating search keywords: {e}")
        return {
            "keywords": ["weather anomaly Pakistan"],
            "keywords_english": [],
            "keywords_roman_urdu": []
        }

def analyze_with_ai(weather_diff: str, search_results: dict) -> dict:
    """
    Uses Gemini to analyze the weather difference and recent news.
    Returns a structured dictionary.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        return {"error": "GEMINI_API_KEY not configured."}
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    
    prompt = f"""
    You are an intelligent safety analysis assistant specialized in Pakistan.
    The weather has changed suddenly.
    
    Situation: {weather_diff}
    
    Search reports:
    {json.dumps(search_results, indent=2)}
    
    Analyze the situation and determine if there is an active crisis (e.g. heatwave, flood, dust storm, smog, etc.). 
    Provide highly localized advice considering the user's specific city/sector if mentioned in the situation (e.g., "Avoid Kashmir Highway underpass" instead of "Stay indoors").
    
    You MUST respond with a JSON object exactly matching this schema:
    {{
      "type": "heatwave|heavy_rainfall|monsoon|flood|cold_wave|fog_smog|dust_storm|severe_wind|safe",
      "severity": "high|medium|low|none",
      "confidence": "high|medium|low",
      "title": "String (Short summary, max 7 words)",
      "details": "String (Very brief summary of the situation, max 40 words)",
      "safety_advises": ["String (Practical localized safety advice)", "String"],
      "help_resources": ["String (Format: '[Service Name] - [Number]', e.g., 'Rescue 1122 - 1122')"],
      "notification_details": {{
        "type": "weather_alert|info|safe",
        "title": "String (Short title for mobile notification, max 35 chars)",
        "details": "String (Concise body for mobile notification, max 80 chars)"
      }}
    }}
    
    Rules:
    - If nothing seems dangerous, set type to "safe" and severity to "none".
    - "help_resources" must list direct emergency numbers (e.g., "Rescue 1122 - 1122", "Police 15 - 15", "NDMA - 1110").
    - Respond ONLY with the JSON object, nothing else. No markdown formatting.
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            )
        )
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
                "help_resources": ["Rescue 1122 1122", "Police 15"],
                "notification_details": {
                    "type": "safe", 
                    "title": "Error",
                    "details": "AI analysis failed."
                }
            }
        }
