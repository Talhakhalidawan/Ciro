import os
import json
import requests
from ddgs import DDGS
from django.conf import settings
import typing_extensions as typing
from api.ai import ask_ai

# ──────────────────────────────────────────────
# Search functions now accept an optional
# 'location' argument and prepend it to the
# query for truly local results.
# ──────────────────────────────────────────────

def search_youtube(query: str, location: str = "") -> dict:
    if location:
        query = f"{location} {query}"
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
            response = requests.get(url, params=params, timeout=15)
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

    # Fallback to DuckDuckGo
    print("Falling back to DuckDuckGo for YouTube search")
    try:
        with DDGS() as ddgs:
            search_query = f"site:youtube.com {query}"
            for r in ddgs.text(query=search_query, region='pk-en', timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG YouTube search failed: {e}")
        
    return {"platform": "youtube", "results": results}


def search_reddit(query: str, location: str = "") -> dict:
    if location:
        query = f"{location} {query}"
    client_id = getattr(settings, 'REDDIT_CLIENT_ID', None)
    client_secret = getattr(settings, 'REDDIT_CLIENT_SECRET', None)
    results = []
    
    if client_id and client_secret:
        url = f"https://www.reddit.com/search.json?q={query}&sort=new&limit=5"
        headers = {'User-Agent': 'python:ciro_django_app:v1.0 (by /u/developer)'}
        try:
            response = requests.get(url, headers=headers, timeout=15)
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


def search_google(query: str, location: str = "") -> dict:
    if location:
        query = f"{location} {query}"
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
            response = requests.get(url, params=params, timeout=15)
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


# ──────────────────────────────────────────────
# Keyword generator (now location‑aware)
# ──────────────────────────────────────────────

def generate_search_keywords(weather_diff: str, city: str = "", sector: str = "") -> dict:
    """
    Uses Groq/Gemini to create precise, location‑specific search keywords
    in English and authentic Pakistani Roman Urdu (NOT Hindi).
    """
    location_str = ""
    if city and sector:
        location_str = f"{city} {sector}".strip()
    elif city:
        location_str = city
    else:
        location_str = "Pakistan"

    prompt = f"""
    You are a local news search assistant in Pakistan.
    A weather anomaly has been detected in {location_str}.
    Details: {weather_diff}
    
    Generate exactly 2 highly specific, short search keywords (2-3 words each) in English and 2 in Roman Urdu (the way a Pakistani would type in Urdu using English letters).
    Important:
    - The keywords must include the location "{location_str}" wherever possible.
    - Use genuine Pakistani Roman Urdu words (e.g., "garmi" for heat, "baarish" for rain, "sylab" for flood, "aandhi" for storm). Never use Hindi words like "taapmaan" or "prakop".
    
    Return ONLY a JSON object of this shape:
    {{
      "keywords_english": ["string", "string"],
      "keywords_roman_urdu": ["string", "string"]
    }}
    
    No other text.
    """
    
    try:
        response_text = ask_ai(prompt, response_json=True)
        data = json.loads(response_text)
        # Combine and deduplicate
        all_keywords = list(set(data.get("keywords_english", []) + data.get("keywords_roman_urdu", [])))
        if not all_keywords:
            all_keywords = [f"{location_str} weather alert"]
        return {
            "keywords": all_keywords,
            "keywords_english": data.get("keywords_english", []),
            "keywords_roman_urdu": data.get("keywords_roman_urdu", [])
        }
    except Exception as e:
        print(f"Keyword generation failed: {e}")
        return {
            "keywords": [f"{location_str} weather anomaly"],
            "keywords_english": [f"{location_str} weather anomaly"],
            "keywords_roman_urdu": []
        }


# ──────────────────────────────────────────────
# AI Analyzer (simplified, location‑aware)
# ──────────────────────────────────────────────

def analyze_with_ai(weather_diff: str, search_results: dict) -> dict:
    prompt = f"""
    You are a safety assistant for people in Pakistan. A weather anomaly has been reported.

    {weather_diff}

    Additional online reports we found:
    {json.dumps(search_results, indent=2)}

    Based on this, decide if there is a crisis (heatwave, flood, dust storm, smog, etc.) and give a short safety assessment.

    Return a JSON object with exactly these fields:
    {{
      "type": "heatwave|heavy_rainfall|monsoon|flood|cold_wave|fog_smog|dust_storm|severe_wind|safe",
      "severity": "high|medium|low|none",
      "confidence": "high|medium|low",
      "title": "very short crisis title (max 7 words)",
      "details": "brief summary (max 40 words) of what is happening and what it means for that location",
      "safety_advises": ["practical, location‑specific safety tip (max 10 words each)", ...],
      "help_resources": ["Service Name - Number (e.g., Rescue 1122 - 1122)", ...],
      "notification_details": {{
        "type": "weather_alert|info|safe",
        "title": "short push notification title (max 35 chars)",
        "details": "short push notification body (max 80 chars)"
      }}
    }}

    Rules:
    - Use the exact city/sector mentioned in the weather anomaly to give localized advice (e.g., "Avoid Kashmir Highway underpass" instead of "Stay indoors").
    - The "help_resources" must contain real Pakistani emergency numbers: Rescue 1122 - 1122, Police - 15, Motorway Police - 130, NDMA - 1110, PDMA Punjab - 1700. Only list those relevant.
    - If no danger, set type to "safe", severity to "none", and keep other fields minimal.
    - Return ONLY the JSON object. No markdown.
    """
    
    try:
        response_text = ask_ai(prompt, response_json=True)
        return {
            "prompt": prompt,
            "response_json": json.loads(response_text)
        }
    except Exception as e:
        print(f"Groq/Gemini AI failed: {e}")
        return {
            "prompt": prompt,
            "response_json": {
                "type": "safe",
                "severity": "none",
                "confidence": "low",
                "title": "Analysis Failed",
                "details": "Could not reach AI service.",
                "safety_advises": [],
                "help_resources": ["Rescue 1122 - 1122", "Police - 15"],
                "notification_details": {
                    "type": "safe",
                    "title": "Error",
                    "details": "AI analysis failed."
                }
            }
        }