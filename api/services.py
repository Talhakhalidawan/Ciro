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
                        "snippet": item["snippet"]["description"]
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


def search_x(query: str, location: str = "") -> dict:
    if location:
        query = f"{location} {query}"
    results = []
    print("Querying DuckDuckGo for X (Twitter) search")
    try:
        with DDGS() as ddgs:
            search_query = f"site:x.com OR site:twitter.com {query}"
            for r in ddgs.text(query=search_query, region='pk-en', timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG X search failed: {e}")
    return {"platform": "x", "results": results}


def search_facebook(query: str, location: str = "") -> dict:
    if location:
        query = f"{location} {query}"
    results = []
    print("Querying DuckDuckGo for Facebook search")
    try:
        with DDGS() as ddgs:
            search_query = f"site:facebook.com {query}"
            for r in ddgs.text(query=search_query, region='pk-en', timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG Facebook search failed: {e}")
    return {"platform": "facebook", "results": results}


def search_tiktok(query: str, location: str = "") -> dict:
    if location:
        query = f"{location} {query}"
    results = []
    print("Querying DuckDuckGo for TikTok search")
    try:
        with DDGS() as ddgs:
            search_query = f"site:tiktok.com {query}"
            for r in ddgs.text(query=search_query, region='pk-en', timelimit='d', max_results=5):
                results.append({"title": r.get("title"), "snippet": r.get("body")})
    except Exception as e:
        print(f"DDG TikTok search failed: {e}")
    return {"platform": "tiktok", "results": results}


# ──────────────────────────────────────────────
# Keyword generator (now location‑aware)
# ──────────────────────────────────────────────

def generate_search_keywords(weather_diff: str, city: str = "", sector: str = "") -> dict:
    """
    Uses Groq/Gemini to create precise, location‑specific search queries
    in English and authentic Pakistani Roman Urdu (NOT Hindi) to search the internet
    to verify/confirm if there's actually a crisis or something bad happening.
    """
    location_str = ""
    if city and sector:
        location_str = f"{city} {sector}".strip()
    elif city:
        location_str = city
    else:
        location_str = "Pakistan"

    prompt = f"""
    You are a safety assistant in Pakistan. Here is some weather data for {location_str}:
    {weather_diff}
    
    I think there's something unusual/bad that I should warn or report the user about.
    For confirmation, I want you to make precise keywords/queries I can search on DuckDuckGo to verify if there is actually something bad happening right now in {location_str}.
    
    Generate exactly 2 highly specific, short search queries (2-3 words each) in English and 2 in Roman Urdu (the way a Pakistani would type in Urdu using English letters).
    
    Important rules:
    - The queries must be highly specific to {location_str} and weather events so they do not return old or unrelated posts. Keep it focused and includes the location.
    - Use genuine Pakistani Roman Urdu words
    - Absolutely DO NOT use Hindi words like "taapmaan".
    
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

def analyze_with_ai(weather_diff: str, search_results: dict, traffic_incidents: list = None) -> dict:
    traffic_section = ""
    if traffic_incidents:
        traffic_section = f"\n    Active road incidents detected by TomTom nearby:\n    {json.dumps(traffic_incidents, indent=2)}\n"

    prompt = f"""
    You are a safety assistant for people in Pakistan. An environmental anomaly has been reported.

    {weather_diff}
{traffic_section}
    Additional online reports we found:
    {json.dumps(search_results, indent=2)}

    Based on this, decide if there is a crisis (heatwave, flood, dust storm, smog, road accident, road blockage, etc.) and give a short safety assessment.

    Return a JSON object with exactly these fields:
    {{
      "type": "heatwave|heavy_rainfall|monsoon|flood|cold_wave|fog_smog|dust_storm|severe_wind|road_incident|safe",
      "severity": "high|medium|low|none",
      "confidence": "high|medium|low",
      "title": "very short crisis title (max 7 words)",
      "details": "brief summary (max 40 words) of what is happening and what it means for that location",
      "safety_advises": ["practical, location-specific safety tip (max 10 words each)", ...],
      "help_resources": ["Service Name - Number (e.g., Rescue 1122 - 1122)", ...],
      "notification_details": {{
        "type": "weather_alert|info|safe",
        "title": "short push notification title (max 35 chars)",
        "details": "short push notification body (max 80 chars)"
      }}
    }}

    Rules:
    - Use the exact city/sector mentioned in the weather anomaly to give localized advice (e.g., "Avoid Kashmir Highway underpass" instead of "Stay indoors").
    - The "help_resources" MUST contain only real, verified Pakistani emergency numbers. Select exclusively from this list:
      * Police Emergency - 15
      * Rescue 1122 - 1122
      * Edhi Ambulance - 115
      * Fire Brigade - 16
      * Police Women Helpline - 1815
      * IGP Complaint Helpline - 1787
      * NDMA - 051-111-157-157
      * KP Tourism Helpline - 1422
      Only list those helplines that are directly relevant to the detected weather crisis. Absolutely DO NOT invent or return any other helpline name or number under any circumstances.
    - If no danger, set type to "safe", severity to "none", and keep other fields minimal.
    - Return ONLY the JSON object. No markdown.
    """
    
    try:
        response_text = ask_ai(prompt, response_json=True)
        response_json = json.loads(response_text)
        
        # Standardize the emergency helplines programmatically to prevent any AI hallucination or false formatting
        helplines_map = {
            "rescue 1122": "Rescue 1122 - 1122",
            "1122": "Rescue 1122 - 1122",
            "police emergency": "Police Emergency - 15",
            "police": "Police Emergency - 15",
            "15": "Police Emergency - 15",
            "edhi": "Edhi Ambulance - 115",
            "115": "Edhi Ambulance - 115",
            "fire brigade": "Fire Brigade - 16",
            "16": "Fire Brigade - 16",
            "women helpline": "Police Women Helpline - 1815",
            "1815": "Police Women Helpline - 1815",
            "igp complaint": "IGP Complaint Helpline - 1787",
            "1787": "IGP Complaint Helpline - 1787",
            "national disaster": "NDMA - 051-111-157-157",
            "ndma": "NDMA - 051-111-157-157",
            "051-111-157-157": "NDMA - 051-111-157-157",
            "tourism helpline": "KP Tourism Helpline - 1422",
            "1422": "KP Tourism Helpline - 1422"
        }
        cleaned_helplines = []
        for resource in response_json.get("help_resources", []):
            resource_lower = resource.lower()
            matched = False
            for key, val in helplines_map.items():
                if key in resource_lower:
                    if val not in cleaned_helplines:
                        cleaned_helplines.append(val)
                    matched = True
                    break
            if not matched and resource:
                cleaned_helplines.append(resource)
                
        # Fallback to Rescue 1122 if none provided for a crisis
        if response_json.get("type", "safe") != "safe" and not cleaned_helplines:
            cleaned_helplines.append("Rescue 1122 - 1122")
            
        response_json["help_resources"] = cleaned_helplines
        
        return {
            "prompt": prompt,
            "response_json": response_json
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