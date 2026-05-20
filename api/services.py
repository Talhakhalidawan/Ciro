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
                url     = r.get("href", "")
                if title or snippet:
                    results.append({"title": title, "snippet": snippet, "url": url})
    except Exception as e:
        err_msg = f"DDG search failed ({site_filter}): {e}"
        print(err_msg)
        # Propagate network/connection error to abort smart keyword searches early
        e_str = str(e)
        if "ConnectError" in e_str or "connection" in e_str.lower() or "timeout" in e_str.lower() or "rate limit" in e_str.lower():
            raise ConnectionError(err_msg)
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
                    v_id = item.get("id", {}).get("videoId", "")
                    url = f"https://www.youtube.com/watch?v={v_id}" if v_id else ""
                    results.append({
                        "title":   _clean(s.get("title", "")),
                        "snippet": _clean(s.get("description", "")),
                        "url":     url
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
        try:
            res = search_fn(query)
            results = res.get("results", [])
            print(f"  [{platform}] query='{query}' → {len(results)} result(s)")
            if len(results) > len(best["results"]):
                best = {"platform": platform, "query_used": query, "results": results}
            if _is_useful(results, min_results):
                print(f"  [{platform}] ✓ Good results — stopping keyword iteration")
                return {"platform": platform, "query_used": query, "results": results}
        except ConnectionError as ce:
            print(f"  [{platform}] Network connection failure. Aborting keyword iteration early: {ce}")
            break
        except Exception as ex:
            print(f"  [{platform}] Unexpected search failure: {ex}")

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
Anomaly near {location_str}: {weather_diff}
Generate a JSON array of 5-8 short search queries (English/Roman Urdu, e.g. garmi, toofan, baarish, sylab, sarak band, aag) to verify this on DuckDuckGo.
Include '{location_str}' in queries. Sort most specific first.
Return ONLY a JSON array of strings. Example: ["{location_str} heatwave", "{location_str} garmi"]
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
    search_results: dict,       # {platform: {"query_used": str, "results": [...]}}
    traffic_incidents: list = None
) -> dict:
    """
    Analyses the anomaly + search results. Returns:
    {
        "prompt": str,
        "response_json": {
            "type", "severity", "confidence", "title", "details",
            "safety_advises", "help_resources", "notification_details",
            "top_posts": [{"query": str, "platform": str, "items": [...]}]
        }
    }
    """
    traffic_section = ""
    if traffic_incidents:
        traffic_section = (
            "\nRoad incidents:\n"
            + json.dumps(traffic_incidents, ensure_ascii=False)
            + "\n"
        )

    # 1. Programmatically filter & score all retrieved search items in Python
    all_items = []
    for platform, data in search_results.items():
        query_used = data.get("query_used", "")
        for item in data.get("results", []):
            all_items.append({
                "platform": platform,
                "query_used": query_used,
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("url", "")
            })

    # Crisis keywords for relevance scoring
    crisis_keywords = [
        "temp", "garmi", "heatwave", "hot", "rain", "monsoon", "flood", "sylab", "baarish", 
        "wind", "storm", "aandhi", "toofan", "smog", "fog", "mosam", "degree", "aqi", 
        "pollution", "smoke", "fire", "aag", "wildfire", "accident", "closed", "delay", 
        "block", "sarak", "band", "traffic", "jam", "route"
    ]

    def score_item(it):
        text = f"{it['title']} {it['snippet']}".lower()
        score = 0
        for kw in crisis_keywords:
            if kw in text:
                score += 1
        return score

    # Score and sort items
    scored_items = []
    for idx, item in enumerate(all_items):
        score = score_item(item)
        scored_items.append((score, idx, item))

    # Sort descending by score
    scored_items.sort(key=lambda x: x[0], reverse=True)

    # Pick the top 7 items overall to keep prompt size tiny
    top_scored_items = scored_items[:7]

    # Map candidate posts to simple candidates containing ONLY id, platform, title (NO url, NO snippet!)
    ai_candidates = []
    for score, idx, item in top_scored_items:
        ai_candidates.append({
            "id": idx,
            "platform": item["platform"],
            "title": item["title"]
        })

    prompt = f"""
Anomaly: {weather_diff}
{traffic_section}
Candidates: {json.dumps(ai_candidates, ensure_ascii=False)}

Task:
Analyze the anomaly and determine if a crisis exists. Note: consider regional geography (e.g., if there are no forests, fires are urban/agricultural).
Select up to 3 relevant post IDs confirming the event.
Return ONLY valid JSON:
{{
  "type": "heatwave|heavy_rainfall|monsoon|flood|cold_wave|fog_smog|dust_storm|severe_wind|road_incident|urban_fire|safe",
  "severity": "high|medium|low|none",
  "confidence": "high|medium|low",
  "title": "Short title",
  "details": "One short sentence.",
  "safety_advises": ["Tip 1", "Tip 2"],
  "help_resources": ["Rescue 1122 - 1122"],
  "notification_details": {{"type": "weather_alert|road_alert|fire_alert|info|safe", "title": "Title", "body": "Body"}},
  "top_post_ids": [id1, id2]
}}
"""

    try:
        response_text = ask_ai(prompt, response_json=True)
        response_json = json.loads(response_text)

        # Standardise helplines
        response_json["help_resources"] = _standardise_helplines(
            response_json.get("help_resources", []),
            response_json.get("type", "safe")
        )

        # Map top_post_ids selected by AI back to their full details (title, snippet, url) in Python
        selected_ids = response_json.get("top_post_ids", [])
        if not isinstance(selected_ids, list):
            selected_ids = []

        platform_map = {}
        for p_idx in selected_ids:
            # Find in top_scored_items
            found = next((item for score, idx, item in top_scored_items if idx == p_idx), None)
            if found:
                platform = found["platform"]
                query = found["query_used"]
                item_detail = {
                    "title": found["title"],
                    "snippet": found["snippet"],
                    "url": found["url"]
                }
                if platform not in platform_map:
                    platform_map[platform] = {
                        "platform": platform,
                        "query": query,
                        "items": []
                    }
                platform_map[platform]["items"].append(item_detail)

        response_json["top_posts"] = list(platform_map.values())
        # Clean up the top_post_ids field so it is not returned in the final response
        if "top_post_ids" in response_json:
            del response_json["top_post_ids"]

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