import json
import requests
from ddgs import DDGS
from django.conf import settings
from api.ai import ask_ai

# ─────────────────────────────────────────────────────────────────────────────
# Low-level search helpers
# Each function accepts a single, already-complete query string and returns
# {"platform": str, "query": str, "results": [{"title": str, "snippet": str}]}
# Results are cleaned of '#' to prevent markdown/LLM hashing issues.
# ─────────────────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    return (text or "").replace("#", "").strip()


def _ddgs_search(site_filter: str, query: str, max_results: int = 5) -> list:
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(
                query=f"{site_filter} {query}",
                region='pk-en',
                timelimit='d',
                max_results=max_results
            ):
                title   = _clean(r.get("title", ""))
                snippet = _clean(r.get("body", ""))
                if title or snippet:
                    results.append({"title": title, "snippet": snippet})
    except Exception as e:
        print(f"DDG search failed ({site_filter}): {e}")
    return results


def search_youtube(query: str) -> dict:
    results = []
    api_key = getattr(settings, 'YOUTUBE_API_KEY', None)
    if api_key:
        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={"part": "snippet", "q": query, "type": "video",
                        "order": "date", "maxResults": 5, "key": api_key},
                timeout=15
            )
            if r.status_code == 200:
                for item in r.json().get("items", []):
                    s = item.get("snippet", {})
                    results.append({
                        "title":   _clean(s.get("title", "")),
                        "snippet": _clean(s.get("description", ""))
                    })
                return {"platform": "youtube", "query": query, "results": results}
        except Exception as e:
            print(f"YouTube API failed: {e}")
    # Fallback
    results = _ddgs_search("site:youtube.com", query)
    return {"platform": "youtube", "query": query, "results": results}


def search_x(query: str) -> dict:
    results = _ddgs_search("site:x.com OR site:twitter.com", query)
    return {"platform": "x", "query": query, "results": results}


def search_facebook(query: str) -> dict:
    results = _ddgs_search("site:facebook.com", query)
    return {"platform": "facebook", "query": query, "results": results}


def search_tiktok(query: str) -> dict:
    results = _ddgs_search("site:tiktok.com", query)
    return {"platform": "tiktok", "query": query, "results": results}


_PLATFORM_FN = {
    "youtube":  search_youtube,
    "x":        search_x,
    "facebook": search_facebook,
    "tiktok":   search_tiktok,
}

# ─────────────────────────────────────────────────────────────────────────────
# Smart per-platform search
# Tries ranked queries in order until it finds ≥ min_results useful results
# or exhausts the list.
# Returns {"platform": str, "query_used": str, "results": [...]}
# ─────────────────────────────────────────────────────────────────────────────

def _is_useful(results: list, min_results: int = 2) -> bool:
    """A result set is 'useful' if it has ≥ min_results items with real text."""
    meaningful = [
        r for r in results
        if len(r.get("title", "") + r.get("snippet", "")) > 20
    ]
    return len(meaningful) >= min_results


def smart_search_platform(platform: str, ranked_queries: list, min_results: int = 2) -> dict:
    """
    Tries each query in ranked_queries for the given platform.
    Returns the first set that is 'useful', or the best set found.
    """
    search_fn = _PLATFORM_FN.get(platform)
    if not search_fn:
        return {"platform": platform, "query_used": "", "results": []}

    best = {"platform": platform, "query_used": "", "results": []}

    for query in ranked_queries:
        res = search_fn(query)
        results = res.get("results", [])
        print(f"  [{platform}] query='{query}' → {len(results)} result(s)")
        if len(results) > len(best["results"]):
            best = {"platform": platform, "query_used": query, "results": results}
        if _is_useful(results, min_results):
            print(f"  [{platform}] ✓ Good results — stopping keyword iteration")
            return {"platform": platform, "query_used": query, "results": results}

    return best


# ─────────────────────────────────────────────────────────────────────────────
# Ranked keyword generator
# Asks AI to produce a priority-ordered list of search queries (best → worst)
# ─────────────────────────────────────────────────────────────────────────────

def generate_ranked_queries(weather_diff: str, city: str = "") -> list:
    """
    Returns a ranked list of search query strings, from most specific/useful
    to least. Each query is self-contained (already includes location).
    """
    location_str = city if city else "Pakistan"

    prompt = f"""
You are a safety assistant in Pakistan. Here is an anomaly that was detected near {location_str}:
{weather_diff}

I need to verify if this is really happening by searching the internet. Give me a ranked list of
search queries I can type into DuckDuckGo — sorted from MOST SPECIFIC and useful to LEAST useful.

Rules:
- Each query must be self-contained and include the location ({location_str}) where relevant.
- Mix English and Roman Urdu (Pakistani style, not Hindi). Roman Urdu words: garmi, toofan, baarish, sylab, aandhi, mosam, hadsa, sarak band, aag.
- Queries should be short (3-6 words), focused, and NOT so broad that they return old or unrelated results.
- Generate between 5 and 8 queries total.
- Sort them: most specific and timely first, most general last.

Return ONLY a JSON array of strings. No other text. Example:
["Islamabad heatwave today", "Islamabad garmi alert", "Islamabad temperature spike", ...]
"""

    try:
        response_text = ask_ai(prompt, response_json=True)
        queries = json.loads(response_text)
        if isinstance(queries, list) and queries:
            # Ensure strings only
            return [str(q) for q in queries if str(q).strip()]
    except Exception as e:
        print(f"Ranked query generation failed: {e}")

    # Fallback
    fallback = f"{location_str} weather"
    return [f"{location_str} {weather_diff[:30]}", fallback]


# ─────────────────────────────────────────────────────────────────────────────
# AI crisis analyzer
# Now also picks up to 3 "top posts" (query + snippets that were actually useful)
# ─────────────────────────────────────────────────────────────────────────────

_HELPLINES_MAP = {
    "rescue 1122": "Rescue 1122 - 1122",
    "1122":        "Rescue 1122 - 1122",
    "police emergency": "Police Emergency - 15",
    "police":      "Police Emergency - 15",
    " 15":         "Police Emergency - 15",
    "edhi":        "Edhi Ambulance - 115",
    "115":         "Edhi Ambulance - 115",
    "fire brigade": "Fire Brigade - 16",
    " 16":         "Fire Brigade - 16",
    "women helpline": "Police Women Helpline - 1815",
    "1815":        "Police Women Helpline - 1815",
    "igp complaint": "IGP Complaint Helpline - 1787",
    "1787":        "IGP Complaint Helpline - 1787",
    "national disaster": "NDMA - 051-111-157-157",
    "ndma":        "NDMA - 051-111-157-157",
    "051-111-157": "NDMA - 051-111-157-157",
    "tourism helpline": "KP Tourism Helpline - 1422",
    "1422":        "KP Tourism Helpline - 1422",
}


def _standardise_helplines(raw: list, crisis_type: str) -> list:
    cleaned = []
    for resource in raw:
        resource_lower = resource.lower()
        matched = False
        for key, val in _HELPLINES_MAP.items():
            if key in resource_lower:
                if val not in cleaned:
                    cleaned.append(val)
                matched = True
                break
        if not matched and resource.strip():
            cleaned.append(resource.strip())
    if crisis_type != "safe" and not cleaned:
        cleaned.append("Rescue 1122 - 1122")
    return cleaned


def analyze_with_ai(
    weather_diff: str,
    search_results: dict,       # {platform: [{"query_used": str, "results": [...]}]}
    traffic_incidents: list = None
) -> dict:
    """
    Analyses the anomaly + search results. Returns:
    {
        "prompt": str,
        "response_json": {
            "type", "severity", "confidence", "title", "details",
            "safety_advises", "help_resources", "notification_details",
            "top_posts": [{"query": str, "platform": str, "items": [...]}]  ← new
        }
    }
    """
    traffic_section = ""
    if traffic_incidents:
        traffic_section = (
            "\nActive road incidents detected by TomTom nearby:\n"
            + json.dumps(traffic_incidents, indent=2, ensure_ascii=False)
            + "\n"
        )

    # Flatten search results for prompt (keep compact)
    search_summary = {}
    for platform, data in search_results.items():
        query_used = data.get("query_used", "")
        items = data.get("results", [])[:4]   # limit to 4 per platform in prompt
        search_summary[platform] = {"query_used": query_used, "items": items}

    prompt = f"""
You are a safety assistant for people in Pakistan. An environmental anomaly has been reported.

Anomaly detected:
{weather_diff}
{traffic_section}
Social media reports we found (per platform, with the query that retrieved them):
{json.dumps(search_summary, indent=2, ensure_ascii=False)}

Task:
1. Decide if there is a real crisis (heatwave, flood, dust storm, smog, road incident, fire, etc.).
2. Pick up to 3 platforms whose search results are most relevant and on-point for this crisis.
3. Return a single JSON object with exactly these fields:

{{
  "type": "heatwave|heavy_rainfall|monsoon|flood|cold_wave|fog_smog|dust_storm|severe_wind|road_incident|wildfire|safe",
  "severity": "high|medium|low|none",
  "confidence": "high|medium|low",
  "title": "very short crisis title (max 7 words)",
  "details": "one sentence (max 35 words) summarising what is happening and why it matters",
  "safety_advises": ["max 10-word location-specific tip", "tip 2", "tip 3"],
  "help_resources": ["Service Name - Number"],
  "notification_details": {{
    "type": "weather_alert|road_alert|fire_alert|info|safe",
    "title": "push notification title (max 35 chars)",
    "body":  "push notification body (max 80 chars)"
  }},
  "top_posts": [
    {{
      "platform": "youtube|x|facebook|tiktok",
      "query": "the search query that found these",
      "items": [{{"title": "...", "snippet": "..."}}]
    }}
  ]
}}

Rules:
- "top_posts" must contain only platforms whose results clearly relate to the detected crisis. Max 3 entries.
- If results are irrelevant or empty, omit that platform from "top_posts".
- "help_resources" must only use numbers from this list:
    Rescue 1122 - 1122 | Police Emergency - 15 | Edhi Ambulance - 115 | Fire Brigade - 16
    Police Women Helpline - 1815 | IGP Complaint Helpline - 1787 | NDMA - 051-111-157-157 | KP Tourism Helpline - 1422
  Only include those relevant to the crisis. NEVER invent numbers.
- Use exact city for localised advice.
- If no crisis, type="safe", severity="none", top_posts=[].
- Return ONLY the JSON object. No markdown, no explanation.
"""

    try:
        response_text = ask_ai(prompt, response_json=True)
        response_json = json.loads(response_text)

        # Standardise helplines
        response_json["help_resources"] = _standardise_helplines(
            response_json.get("help_resources", []),
            response_json.get("type", "safe")
        )

        # Ensure top_posts is a list
        if not isinstance(response_json.get("top_posts"), list):
            response_json["top_posts"] = []

        return {"prompt": prompt, "response_json": response_json}

    except Exception as e:
        print(f"AI analysis failed: {e}")
        return {
            "prompt": prompt,
            "response_json": {
                "type": "safe", "severity": "none", "confidence": "low",
                "title": "Analysis Failed",
                "details": "Could not reach AI service.",
                "safety_advises": [],
                "help_resources": ["Rescue 1122 - 1122"],
                "notification_details": {"type": "safe", "title": "Error", "body": "AI analysis failed."},
                "top_posts": []
            }
        }