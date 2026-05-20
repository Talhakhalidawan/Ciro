import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_datetime
from api.models import WeatherRequest, SearchLog, AIResponseLog
from api.services import (
    get_deep_youtube_details,
    fetch_youtube_transcript,
    build_single_ai_prompt,
    parse_ai_crisis_response,
    get_crisis_metadata,
    log_step,
    check_safe_zones
)


@csrf_exempt
@require_POST
def weather_view(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        lat = data.get('latitude')
        lon = data.get('longitude')
        user_time = data.get('time')
        city_name = data.get('city_name')

        log_step("API ROUTER", "Incoming Weather Request Received", {
            "user_id": user_id, "latitude": lat, "longitude": lon,
            "time": user_time, "city_name": city_name
        })

        location_name = city_name or "Unknown Location"
        region_and_country = f"{location_name}, Pakistan"

        if not user_id or lat is None or lon is None:
            return JsonResponse({'error': 'user_id, latitude, and longitude are required'}, status=400)

        # ── Debug Flags ────────────────────────────────────────────
        from django.conf import settings
        debug_force_crisis = getattr(settings, 'DEBUG_FORCE_CRISIS_ANOMALY', False)
        debug_yt_mode = getattr(settings, 'DEBUG_YT_MODE', False)
        debug_ai_prompt = getattr(settings, 'DEBUG_AI_PROMPT', False)
        debug_mock_ai = getattr(settings, 'DEBUG_MOCK_AI', False)

        # ── Fetch current weather from Open‑Meteo ───────────────────
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "timezone": "auto"
        }
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            return JsonResponse({'error': 'Failed to fetch weather data'}, status=502)

        weather_data = response.json()
        current = weather_data.get('current', {})

        # ── Fetch AQI ──────────────────────────────────────────────
        aqi = 0
        try:
            aqi_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
            aqi_resp = requests.get(aqi_url, params={"latitude": lat, "longitude": lon, "current": "us_aqi"}, timeout=10)
            if aqi_resp.status_code == 200:
                aqi = aqi_resp.json().get('current', {}).get('us_aqi', 0)
        except Exception as e:
            print(f"Air quality fetch failed: {e}")

        # ── Fetch NASA FIRMS ───────────────────────────────────────
        firms_fires_detected = 0
        firms_key = getattr(settings, 'NASA_FIRMS_MAP_KEY', None)
        if firms_key:
            try:
                lon_min, lat_min = lon - 0.1, lat - 0.1
                lon_max, lat_max = lon + 0.1, lat + 0.1
                firms_url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{firms_key}/VIIRS_SNPP_NRT/{lon_min},{lat_min},{lon_max},{lat_max}/1"
                firms_resp = requests.get(firms_url, timeout=10)
                if firms_resp.status_code == 200:
                    lines = firms_resp.text.strip().split("\n")
                    if len(lines) > 1:
                        firms_fires_detected = len(lines) - 1
            except Exception as e:
                print(f"NASA FIRMS fetch failed: {e}")

        # ── Fetch TomTom Traffic ───────────────────────────────────
        tomtom_incidents_count = 0
        tomtom_incidents_summary = []
        tomtom_key = getattr(settings, 'MYTOMTOM_API_KEY', None)
        if tomtom_key:
            try:
                geocode_url = f"https://api.tomtom.com/search/2/reverseGeocode/{lat},{lon}.json"
                geocode_resp = requests.get(geocode_url, params={"key": tomtom_key}, timeout=5)
                if geocode_resp.status_code == 200:
                    geo_data = geocode_resp.json()
                    addresses = geo_data.get("addresses", [])
                    if addresses:
                        address = addresses[0].get("address", {})
                        resolved_city = address.get("municipality") or address.get("localName") or address.get("countrySubdivision") or "Unknown Location"
                        country = address.get("country") or "Pakistan"
                        if city_name:
                            location_name = city_name
                            region_and_country = f"{city_name}, {country}"
                        else:
                            location_name = resolved_city
                            region_and_country = f"{resolved_city}, {country}"
            except Exception as e:
                print(f"TomTom Reverse Geocoding failed: {e}")

            try:
                tt_lon_min, tt_lat_min = lon - 0.1, lat - 0.1
                tt_lon_max, tt_lat_max = lon + 0.1, lat + 0.1
                bbox_str = f"{tt_lon_min},{tt_lat_min},{tt_lon_max},{tt_lat_max}"
                fields = "{incidents{type,properties{id,iconCategory,magnitudeOfDelay,events{description,iconCategory},from,to,roadNumbers,timeValidity}}}"
                tomtom_url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
                tomtom_params = {
                    "key": tomtom_key, "bbox": bbox_str, "fields": fields,
                    "language": "en-GB", "categoryFilter": "1,3,7,8,9,11", "timeValidityFilter": "present"
                }
                tt_resp = requests.get(tomtom_url, params=tomtom_params, timeout=10)
                if tt_resp.status_code == 200:
                    tt_data = tt_resp.json()
                    incidents = tt_data.get("incidents", [])
                    tomtom_incidents_count = len(incidents)
                    for inc in incidents:
                        props = inc.get("properties", {})
                        events = props.get("events", [])
                        desc = events[0].get("description", "") if events else ""
                        delay = props.get("magnitudeOfDelay", 0)
                        delay_label = {0: "Unknown", 1: "Minor", 2: "Moderate", 3: "Major", 4: "Undefined"}.get(delay, "")
                        tomtom_incidents_summary.append({
                            "category": props.get("iconCategory", "Unknown"),
                            "description": desc.replace("#", ""),
                            "from": props.get("from", ""),
                            "to": props.get("to", ""),
                            "delay": delay_label
                        })
            except Exception as e:
                print(f"TomTom traffic fetch failed: {e}")

        # Mock overrides
        mock_current = data.get('mock_current_weather')
        if mock_current:
            current.update(mock_current)
            if 'aqi' in mock_current: aqi = mock_current['aqi']
            if 'firms_fires_detected' in mock_current: firms_fires_detected = mock_current['firms_fires_detected']
            if 'tomtom_incidents_count' in mock_current: tomtom_incidents_count = mock_current['tomtom_incidents_count']
            if 'tomtom_incidents_summary' in mock_current: tomtom_incidents_summary = mock_current['tomtom_incidents_summary']

        current['aqi'] = aqi
        current['firms_fires_detected'] = firms_fires_detected
        current['tomtom_incidents_count'] = tomtom_incidents_count
        current['tomtom_incidents_summary'] = tomtom_incidents_summary

        log_step("SENSOR DATA", "Environmental readings", {
            "city": location_name, "temp": current.get('temperature_2m'),
            "aqi": aqi, "fires": firms_fires_detected, "traffic": tomtom_incidents_count
        })

        # ── Save to DB ────────────────────────────────────────────
        parsed_time = parse_datetime(user_time) if user_time else None
        new_request = WeatherRequest.objects.create(
            user_id=user_id, latitude=lat, longitude=lon, user_time=parsed_time,
            city_name=city_name, aqi=aqi, firms_fires_detected=firms_fires_detected,
            tomtom_incidents_count=tomtom_incidents_count, tomtom_incidents_summary=tomtom_incidents_summary,
            temperature_2m=current.get('temperature_2m'),
            relative_humidity_2m=current.get('relative_humidity_2m'),
            apparent_temperature=current.get('apparent_temperature'),
            is_day=current.get('is_day'), precipitation=current.get('precipitation'),
            rain=current.get('rain'), showers=current.get('showers'),
            snowfall=current.get('snowfall'), weather_code=current.get('weather_code'),
            cloud_cover=current.get('cloud_cover'), pressure_msl=current.get('pressure_msl'),
            surface_pressure=current.get('surface_pressure'), wind_speed_10m=current.get('wind_speed_10m'),
            wind_direction_10m=current.get('wind_direction_10m'), wind_gusts_10m=current.get('wind_gusts_10m'),
        )

        # ── Simulator Check ─────────────────────────────────────────
        from api.models import AdminCrisisScenario
        simulated_crisis = None
        active_scenarios = AdminCrisisScenario.objects.filter(is_active=True)
        req_city = (city_name or "").lower().strip()
        for scenario in active_scenarios:
            loc = scenario.location.lower().strip()
            if loc == 'all' or loc == req_city:
                simulated_crisis = scenario.crisis_type
                break

        # ── Workflow Variables ─────────────────────────────────────
        ai_response = None
        youtube_videos = []
        static_query = f"{city_name} latest news"

        if simulated_crisis:
            log_step("SIMULATOR", f"Active scenario: {simulated_crisis}")
            if simulated_crisis == 'heatwave':
                current['temperature_2m'] = 48.5
                ai_response = {'type': 'heatwave', 'severity': 'high', 'confidence': 'high',
                    'title': 'Extreme Heatwave Alert', 'details': 'Temperatures have spiked significantly.', 'main_video_indices': []}
            elif simulated_crisis == 'fire':
                firms_fires_detected = 5
                current['firms_fires_detected'] = 5
                ai_response = {'type': 'fire', 'severity': 'critical', 'confidence': 'high',
                    'title': 'Active Wildfire Warning', 'details': 'Multiple thermal anomalies detected.', 'main_video_indices': []}
            elif simulated_crisis == 'road_accident':
                tomtom_incidents_count = 2
                current['tomtom_incidents_count'] = 2
                ai_response = {'type': 'road_incident', 'severity': 'medium', 'confidence': 'high',
                    'title': 'Major Road Accident', 'details': 'Severe accident closed major routes.', 'main_video_indices': []}
            elif simulated_crisis == 'safe_response':
                ai_response = {'type': 'safe', 'severity': 'none', 'confidence': 'high',
                    'title': 'All Clear', 'details': 'No incidents detected.', 'main_video_indices': []}
        else:
            # ── REAL WORKFLOW ───────────────────────────────────────
            weather_issue_summary = check_safe_zones(current, firms_fires_detected, tomtom_incidents_count)
            log_step("SAFE ZONES", weather_issue_summary or "Weather is SAFE")

            if debug_force_crisis:
                weather_issue_summary = f"In {city_name or 'Gujrat'}, temperature rose to 48.5°C and fires detected."

            # 1. YouTube Scrape
            youtube_videos = get_deep_youtube_details(static_query, max_results=4)
            
            if debug_yt_mode:
                return JsonResponse({
                    "debug_mode": True, "query": static_query,
                    "results": youtube_videos, "weather_issues": weather_issue_summary
                })

            SearchLog.objects.create(
                weather_request=new_request, platform="youtube_scraper",
                query=static_query, results=youtube_videos
            )

            # 2. Fetch transcripts (max 2 videos, ≤3 min only)
            transcripts_fetched = 0
            for v in youtube_videos:
                if transcripts_fetched >= 2:
                    break
                if 0 < v['duration_sec'] <= 180:
                    v['transcript'] = fetch_youtube_transcript(v['video_id'])
                    transcripts_fetched += 1
                else:
                    v['transcript'] = "(Skipped - >3 min or live)"

            # 3. SINGLE AI CALL
            if youtube_videos or weather_issue_summary:
                prompt = build_single_ai_prompt(city_name, weather_issue_summary, youtube_videos)
                
                if debug_ai_prompt:
                    log_step("DEBUG", "AI Prompt", prompt)

                if debug_mock_ai:
                    ai_raw = json.dumps({
                        "type": "fire", "severity": "high", "confidence": "high",
                        "title": "Mock: Fire Detected", "details": "Mock AI for testing.",
                        "main_video_indices": [0] if youtube_videos else []
                    })
                else:
                    from api.ai import ask_ai
                    ai_raw = ask_ai(prompt, response_json=False)
                
                ai_response = parse_ai_crisis_response(ai_raw)
                
                AIResponseLog.objects.create(
                    weather_request=new_request,
                    prompt=prompt[:2000],
                    response_json=ai_response
                )
            else:
                ai_response = {'type': 'safe', 'severity': 'none', 'confidence': 'high',
                    'title': 'All Clear', 'details': 'No incidents detected.', 'main_video_indices': []}

        # ── Build Response ──────────────────────────────────────────
        final_response = {
            'status': 'success',
            'interval_minutes': getattr(settings, 'WEATHER_CHECK_INTERVAL_MINUTES', 30),
            'location_name': location_name,
            'region_and_country': region_and_country,
            'environment': {
                'temperature_c': current.get('temperature_2m'),
                'feels_like_c': current.get('apparent_temperature'),
                'humidity_pct': current.get('relative_humidity_2m'),
                'precipitation_mm': current.get('precipitation'),
                'wind_speed_kmh': current.get('wind_speed_10m'),
                'wind_gusts_kmh': current.get('wind_gusts_10m'),
                'weather_code': current.get('weather_code'),
                'aqi': aqi,
                'active_fires_nearby': firms_fires_detected,
            },
            'traffic': {
                'incident_count': tomtom_incidents_count,
                'incidents': tomtom_incidents_summary
            }
        }

        # Attach alert if crisis
        if ai_response and ai_response.get('type') != 'safe':
            crisis_type = ai_response.get('type', 'safe')
            metadata = get_crisis_metadata(crisis_type)
            
            # Build top_posts from main_video_indices
            top_posts = []
            for idx in ai_response.get('main_video_indices', []):
                if 0 <= idx < len(youtube_videos):
                    v = youtube_videos[idx]
                    top_posts.append({"title": v['title'], "snippet": v['snippet'], "url": v['url']})
            
            final_response['alert'] = {
                'type': crisis_type,
                'severity': ai_response.get('severity', 'medium'),
                'confidence': ai_response.get('confidence', 'low'),
                'title': ai_response.get('title', 'Alert'),
                'details': ai_response.get('details', 'An incident has been detected.'),
                'safety_advises': metadata['safety_advises'],
                'help_resources': metadata['help_resources'],
                'notification': metadata['notification'],
                'top_posts': [{
                    "platform": "youtube",
                    "query": static_query,
                    "items": top_posts
                }] if top_posts else []
            }
            log_step("ALERT", "Crisis payload attached", final_response['alert'])
        else:
            log_step("ALERT", "Safe payload returned")

        return JsonResponse(final_response, json_dumps_params={'ensure_ascii': False})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        log_step("API ERROR", f"Critical exception: {e}")
        return JsonResponse({'error': str(e)}, status=500)