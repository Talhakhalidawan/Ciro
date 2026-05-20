import json
import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi
from django.conf import settings
from api.ai import ask_ai
import re

# ── 100 Crisis Keywords (English + Roman Urdu) ─────────────────────────────
CRISIS_KEYWORDS = [
    "accident", "crash", "collision", "smashed", "hit", "runover", "derailed", "wreck",
    "fire", "aag", "burning", "blaze", "inferno", "smoke", "dhuaan", "blast",
    "flood", "sylab", "flooding", "waterlogged", "drown", "doob", "paani", "overflow",
    "rain", "baarish", "heavy rain", "monsoon", "storm", "toofan", "thunder", "lightning",
    "wind", "aandhi", "tornado", "cyclone", "hurricane", "typhoon", "hail", "ola",
    "earthquake", "zalzala", "tremor", "quake", "shake", "landslide", "avalanche",
    "heatwave", "garmi", "hot", "scorching", "sunstroke", "looh",
    "cold", "sardi", "freeze", "snow", "baraf", "blizzard", "frostbite",
    "fog", "smog", "dhund", "pollution", "aqi", "toxic", "poisonous",
    "emergency", "alert", "warning", "danger", "khatra", "critical", "severe", "extreme",
    "dead", "death", "killed", "died", "mout", "mar gaya", "fatal", "casualty",
    "injured", "zakhmi", "hurt", "bleeding", "wound", "hospital", "hatahat",
    "murder", "qatal", "shot", "shooting", "gun", "firing", "stabbing", "attack",
    "robbery", "chori", "dacoity", "daketi", "snatch", "looted", "theft", "mugged",
    "riot", "protest", "strike", "dharna", "ehtejaj", "clash", "mob", "violence",
    "police", "arrest", "raid", "encounter", "flee", "escape", "jail", "prison",
    "blocked", "closed", "band", "jam", "traffic", "sarak", "road", "highway",
    "collapse", "gir gaya", "building", "bridge", "roof", "trapped", "phansa", "rescue",
    "explosion", "dhamaka", "bomb", "suicide", "terrorist", "dehshatgard", "threat"
]

# ── Crisis Metadata (saves AI tokens) ───────────────────────────────────────
CRISIS_METADATA = {
    'heatwave': {
        'safety_advises': ['Stay indoors during peak hours (11am-4pm)', 'Drink water every 30 minutes', 'Avoid direct sunlight', 'Wear loose cotton clothing', 'Check on elderly neighbors'],
        'help_resources': ['Emergency Rescue: 1122', 'Health Helpline: 1166'],
        'notification': {'type': 'heatwave_alert', 'title': 'Heatwave Alert', 'body': 'Extreme heat detected in your area. Stay hydrated and indoors.'}
    },
    'heavy_rain': {
        'safety_advises': ['Avoid low-lying areas', 'Drive slowly with headlights on', 'Watch for falling trees', 'Stay indoors if possible'],
        'help_resources': ['Emergency Rescue: 1122'],
        'notification': {'type': 'weather_alert', 'title': 'Heavy Rain Alert', 'body': 'Intense rainfall reported. Avoid travel if possible.'}
    },
    'monsoon': {
        'safety_advises': ['Avoid riverbanks and drains', 'Do not touch fallen wires', 'Stock drinking water', 'Keep emergency light ready'],
        'help_resources': ['Emergency Rescue: 1122', 'PDMA: 1700'],
        'notification': {'type': 'weather_alert', 'title': 'Monsoon Alert', 'body': 'Heavy monsoon rains causing disruptions.'}
    },
    'flood': {
        'safety_advises': ['Move to higher ground immediately', 'Avoid walking through floodwater', 'Do not drive through flooded roads', 'Keep emergency supplies ready'],
        'help_resources': ['Emergency Rescue: 1122', 'PDMA: 1700'],
        'notification': {'type': 'flood_alert', 'title': 'Flooding Alert', 'body': 'Heavy flooding reported in your area.'}
    },
    'cold_wave': {
        'safety_advises': ['Wear multiple layers', 'Keep windows closed', 'Use heaters safely', 'Check on vulnerable people'],
        'help_resources': ['Emergency Rescue: 1122'],
        'notification': {'type': 'weather_alert', 'title': 'Cold Wave Alert', 'body': 'Dangerously low temperatures detected.'}
    },
    'fog': {
        'safety_advises': ['Drive with fog lights', 'Maintain safe distance', 'Avoid high speeds', 'Use low beam headlights'],
        'help_resources': ['Highway Police: 130', 'Emergency Rescue: 1122'],
        'notification': {'type': 'weather_alert', 'title': 'Dense Fog Alert', 'body': 'Low visibility due to dense fog.'}
    },
    'dust_storm': {
        'safety_advises': ['Cover nose and mouth', 'Stay indoors', 'Close all windows', 'Protect eyes'],
        'help_resources': ['Emergency Rescue: 1122'],
        'notification': {'type': 'weather_alert', 'title': 'Dust Storm Alert', 'body': 'Dust storm reducing visibility.'}
    },
    'severe_wind': {
        'safety_advises': ['Stay away from trees and billboards', 'Secure loose objects', 'Avoid outdoor activities', 'Park vehicles safely'],
        'help_resources': ['Emergency Rescue: 1122'],
        'notification': {'type': 'weather_alert', 'title': 'High Wind Alert', 'body': 'Dangerously strong winds detected.'}
    },
    'road_incident': {
        'safety_advises': ['Use alternative routes', 'Expect severe delays', 'Drive carefully', 'Give way to emergency vehicles'],
        'help_resources': ['Highway Police: 130', 'Emergency Rescue: 1122'],
        'notification': {'type': 'road_alert', 'title': 'Road Incident Alert', 'body': 'Major road closure due to incident.'}
    },
    'fire': {
        'safety_advises': ['Evacuate if instructed by authorities', 'Close all windows and doors', 'Wear N95 mask if outdoors', 'Keep emergency kit ready', 'Call fire brigade immediately'],
        'help_resources': ['Fire Brigade: 16', 'Emergency Rescue: 1122'],
        'notification': {'type': 'fire_alert', 'title': 'Wildfire Alert', 'body': 'Active fires detected near your location.'}
    },
    'crime': {
        'safety_advises': ['Avoid the area', 'Stay in groups', 'Report suspicious activity', 'Keep emergency contacts ready'],
        'help_resources': ['Police: 15', 'Emergency Rescue: 1122'],
        'notification': {'type': 'security_alert', 'title': 'Security Alert', 'body': 'Security incident reported nearby.'}
    },
    'accident': {
        'safety_advises': ['Avoid the area', 'Give way to emergency vehicles', 'Drive carefully', 'Use alternative routes'],
        'help_resources': ['Emergency Rescue: 1122', 'Highway Police: 130'],
        'notification': {'type': 'road_alert', 'title': 'Major Accident', 'body': 'Serious accident reported nearby.'}
    },
    'safe': {
        'safety_advises': [],
        'help_resources': [],
        'notification': {'type': 'safe', 'title': 'All Clear', 'body': 'No incidents detected.'}
    }
}


def _clean(text: str) -> str:
    return (text or "").replace("#", "").strip()


def is_recent(published_text: str, max_hours: int = 3) -> bool:
    """Check if the video is published within the last X hours based on YouTube's simple text."""
    if not published_text:
        return False
    text = published_text.lower()
    if "second" in text or "minute" in text:
        return True
    if "hour" in text:
        match = re.search(r'(\d+)\s+hour', text)
        if match:
            hours = int(match.group(1))
            if hours <= max_hours:
                return True
    return False


def log_step(service_name, message, details=None):
    border = "═" * 60
    print(f"\n{border}")
    print(f"📡 [{service_name.upper()}] - {message}")
    if details is not None:
        if isinstance(details, dict) or isinstance(details, list):
            print(json.dumps(details, indent=2, ensure_ascii=False))
        else:
            print(f"   ↳ {details}")
    print(f"{border}\n")


def contains_crisis_keyword(text: str) -> bool:
    text = text.lower()
    for kw in CRISIS_KEYWORDS:
        if f" {kw} " in f" {text} ":
            return True
    return False


def check_safe_zones(current_data, firms_fires, tomtom_count):
    """
    Checks if weather exceeds safe bounds.
    - Temperature safe zone: 4°C to 45°C
    - Rain limit: 20mm
    - AQI limit: 150
    """
    issues = []
    temp = current_data.get('temperature_2m')
    if temp is not None:
        if temp < 4:
            issues.append(f"Temperature is unusually cold: {temp}°C")
        elif temp > 45:
            issues.append(f"Temperature is dangerously hot: {temp}°C")
            
    precip = current_data.get('precipitation', 0)
    if precip > 20:
        issues.append(f"Heavy rainfall detected: {precip}mm")
        
    aqi = current_data.get('aqi', 0)
    if aqi > 150:
        issues.append(f"Unhealthy Air Quality Index (AQI): {aqi}")
        
    if firms_fires > 0:
        issues.append(f"NASA FIRMS detected {firms_fires} active thermal anomalies/fires.")
        
    if tomtom_count > 0:
        issues.append(f"TomTom detected {tomtom_count} active road incident(s).")
        
    if issues:
        return "; ".join(issues)
    return None


def get_deep_youtube_details(query: str, max_results: int = 4):
    """
    Scrapes YouTube for the latest news on a query.
    Filters videos strictly: published within max_hours + contains crisis keywords.
    Returns up to `max_results` filtered videos.
    """
    log_step("YOUTUBE SCRAPER", f"Initiating YouTube search query: '{query}'")
    filtered_videos = []
    
    max_hours = getattr(settings, 'YOUTUBE_SCRAPE_MAX_HOURS_AGO', 3)
    
    try:
        videos = scrapetube.get_search(query, sort_by="upload_date")
        count = 0
        parsed_count = 0
        for video in videos:
            if count > 100:
                break
            count += 1

            published_time = video.get('publishedTimeText', {}).get('simpleText', '')
            if not is_recent(published_time, max_hours=max_hours):
                continue

            title_runs = video.get('title', {}).get('runs', [{}])
            title = title_runs[0].get('text', '') if title_runs else ''

            description_snippet = ""
            desc_runs = video.get('detailedMetadataSnippets', [{}])[0].get('snippetText', {}).get('runs', [])
            for run in desc_runs:
                description_snippet += run.get('text', '')

            parsed_count += 1
            combined_text = f"{title} {description_snippet}"

            if not contains_crisis_keyword(combined_text):
                continue

            video_id = video.get('videoId')
            url = f"https://www.youtube.com/watch?v={video_id}"
            length_text = video.get('lengthText', {}).get('simpleText', '')

            duration_sec = 0
            if length_text:
                parts = length_text.split(":")
                try:
                    if len(parts) == 3:
                        duration_sec = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
                    elif len(parts) == 2:
                        duration_sec = int(parts[0])*60 + int(parts[1])
                except:
                    pass

            filtered_videos.append({
                "video_id": video_id,
                "title": _clean(title),
                "url": url,
                "published_time": published_time,
                "duration_text": length_text,
                "duration_sec": duration_sec,
                "snippet": _clean(description_snippet)
            })

            if len(filtered_videos) >= max_results:
                break

        log_step("YOUTUBE SCRAPER", f"Scraped {count} videos. Checked {parsed_count} within 3h. Matches: {len(filtered_videos)}", filtered_videos)

    except Exception as e:
        log_step("YOUTUBE SCRAPER ERROR", f"Scrapetube failed: {e}")

    return filtered_videos


def fetch_youtube_transcript(video_id: str) -> str:
    log_step("TRANSCRIPT API", f"Attempting subtitle retrieval for video: '{video_id}'")
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'ur', 'hi', 'pa'])
        text = " ".join([t['text'] for t in transcript_list])
        log_step("TRANSCRIPT API", f"Successfully fetched transcript ({len(text)} chars)")
        return text[:3000]
    except Exception as e:
        log_step("TRANSCRIPT API WARNING", f"Transcript unavailable: {e}")
        return ""


def build_single_ai_prompt(city_name: str, weather_issues: str, videos: list) -> str:
    """
    Builds a highly token-efficient prompt for the SINGLE AI call.
    """
    video_lines = []
    for i, v in enumerate(videos[:4]):
        trans = v.get('transcript', '') or ''
        trans_snippet = trans[:800] if trans else "N/A"
        dur = v.get('duration_text', '?')
        video_lines.append(f'{i}. "{v["title"]}" ({dur}) | Transcript: {trans_snippet}')
    
    video_block = "\n".join(video_lines) if video_lines else "No recent crisis-related videos found."
    weather_block = weather_issues or "All weather parameters within safe bounds."
    
    prompt = f"""City: {city_name}
Weather/Environment: {weather_block}
Recent Video Evidence:
{video_block}

Task: Determine if a real crisis or major incident is currently happening in {city_name}.
Rules:
- If videos confirm a local crisis corroborated by weather data, output crisis JSON.
- If videos are generic news or weather is safe with no video evidence, output safe JSON.
- Severity: high (immediate danger), medium (significant disruption), low (minor).
- Confidence: high (multiple sources confirm), medium (one source), low (uncertain).
- main_video_indices: array of indices (0-3) of the most relevant videos.

Return ONLY valid JSON:
{{"type":"heatwave|heavy_rain|monsoon|flood|cold_wave|fog|dust_storm|severe_wind|road_incident|fire|crime|accident|safe","severity":"high|medium|low|none","confidence":"high|medium|low","title":"Short alert title","details":"One sentence describing the situation.","main_video_indices":[0,1]}}"""

    return prompt


def parse_ai_crisis_response(response_text: str) -> dict:
    """
    Parses and validates the single AI response.
    Returns a safe fallback if parsing fails.
    """
    try:
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        data = json.loads(text)
        
        if 'type' not in data: data['type'] = 'safe'
        if 'severity' not in data: data['severity'] = 'none'
        if 'confidence' not in data: data['confidence'] = 'low'
        if 'title' not in data: data['title'] = 'Incident Detected'
        if 'details' not in data: data['details'] = 'A potential issue has been identified in your area.'
        if 'main_video_indices' not in data: data['main_video_indices'] = []
            
        data['main_video_indices'] = [i for i in data['main_video_indices'] if isinstance(i, int) and 0 <= i <= 3]
        
        return data
        
    except Exception as e:
        log_step("AI PARSER ERROR", f"Failed to parse AI response: {e}. Raw: {response_text[:200]}")
        return {
            "type": "safe", "severity": "none", "confidence": "low",
            "title": "Analysis Error", "details": "Could not verify crisis status.",
            "main_video_indices": []
        }


def get_crisis_metadata(crisis_type: str) -> dict:
    """
    Retrieves safety advice, help resources, and notification details
    based on crisis type. This eliminates the need for AI to generate these,
    saving significant tokens.
    """
    return CRISIS_METADATA.get(crisis_type, {
        'safety_advises': ['Stay alert', 'Follow local news updates', 'Keep emergency contacts ready'],
        'help_resources': ['Emergency Rescue: 1122'],
        'notification': {'type': 'general_alert', 'title': 'Incident Alert', 'body': 'A potential incident has been detected in your area.'}
    })