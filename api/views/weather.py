import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from api.models import WeatherRequest, SearchLog, AIResponseLog
from django.utils.dateparse import parse_datetime
from concurrent.futures import ThreadPoolExecutor
from api.services import (
    smart_search_platform,
    analyze_with_ai,
    generate_ranked_queries
)


def is_weather_unusual(current_data, previous_request, city_name=None):
    """
    Checks if the current weather/environment is significantly different from the previous.
    Returns a string detailing the difference if unusual, else None.
    Thresholds:
    - Temperature rise > 5 degrees C
    - Rain for two consecutive readings (precipitation > 0)
    - AQI jumped by more than 50 points
    - NASA FIRMS thermal anomalies detected > 0
    - TomTom road incidents (Accident/RoadClosed/Flooding etc.) detected > 0
    """
    if not previous_request:
        return None

    area_str = f"In {city_name}" if city_name else "In this area"

    current_temp = current_data.get('temperature_2m', 0)
    prev_temp = previous_request.temperature_2m or 0
    if current_temp - prev_temp > 5:
        return f"{area_str}, temperature rose from {prev_temp}°C to {current_temp}°C."

    current_precip = current_data.get('precipitation', 0)
    prev_precip = previous_request.precipitation or 0
    if current_precip > 0 and prev_precip > 0:
        return f"{area_str}, persistent rain detected across two consecutive readings: {prev_precip}mm and {current_precip}mm."

    current_aqi = current_data.get('aqi', 0)
    prev_aqi = previous_request.aqi or 0
    if abs(current_aqi - prev_aqi) > 50:
        return f"{area_str}, AQI jumped drastically from {prev_aqi} to {current_aqi}."

    firms_fires = current_data.get('firms_fires_detected', 0)
    if firms_fires > 0:
        return f"{area_str}, NASA FIRMS detected {firms_fires} active thermal anomalies/fires nearby."

    tomtom_count = current_data.get('tomtom_incidents_count', 0)
    if tomtom_count > 0:
        incidents = current_data.get('tomtom_incidents_summary', [])
        # Build a concise summary of the most severe incidents (up to 3)
        top_incidents = incidents[:3]
        summaries = []
        for inc in top_incidents:
            cat = inc.get('category', '')
            desc = inc.get('description', '')
            delay = inc.get('delay', '')
            parts = [p for p in [cat, desc, delay] if p]
            summaries.append(", ".join(parts))
        incidents_text = "; ".join(summaries) if summaries else f"{tomtom_count} incident(s)"
        return f"{area_str}, TomTom detected {tomtom_count} active road incident(s): {incidents_text}."

    return None


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

        if not user_id or lat is None or lon is None:
            return JsonResponse({'error': 'user_id, latitude, and longitude are required'}, status=400)

        # Mock response bypass logic removed to ensure requests always pass through the actual AI engine.

        # ── Previous weather for this area ──────────────────────
        previous_request = None
        if city_name:
            previous_request = WeatherRequest.objects.filter(
                city_name=city_name
            ).order_by('-created_at').first()
        if not previous_request:
            previous_request = WeatherRequest.objects.filter(
                user_id=user_id
            ).order_by('-created_at').first()

        # ── Fetch current weather from Open‑Meteo ─────────────────
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "timezone": "auto"
        }
        response = requests.get(url, params=params)       # ← timeout increased
        if response.status_code != 200:
            return JsonResponse({'error': 'Failed to fetch weather data'}, status=502)

        weather_data = response.json()
        current = weather_data.get('current', {})

        # ── Fetch AQI from Open‑Meteo Air Quality API ─────────────
        aqi = 0
        try:
            aqi_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
            aqi_params = {
                "latitude": lat,
                "longitude": lon,
                "current": "us_aqi"
            }
            aqi_resp = requests.get(aqi_url, params=aqi_params)
            if aqi_resp.status_code == 200:
                aqi = aqi_resp.json().get('current', {}).get('us_aqi', 0)
        except Exception as e:
            print(f"Air quality fetch failed: {e}")

        # ── Fetch Thermal Anomalies (Fires) from NASA FIRMS ───────
        firms_fires_detected = 0
        from django.conf import settings
        firms_key = getattr(settings, 'NASA_FIRMS_MAP_KEY', None)
        if firms_key:
            try:
                # Bounding box roughly 11km x 11km around coordinate
                lon_min, lat_min = lon - 0.1, lat - 0.1
                lon_max, lat_max = lon + 0.1, lat + 0.1
                firms_url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{firms_key}/VIIRS_SNPP_NRT/{lon_min},{lat_min},{lon_max},{lat_max}/1"
                firms_resp = requests.get(firms_url, timeout=10)
                if firms_resp.status_code == 200:
                    lines = firms_resp.text.strip().split("\n")
                    if len(lines) > 1: # Header + data rows
                        firms_fires_detected = len(lines) - 1
            except Exception as e:
                print(f"NASA FIRMS fetch failed: {e}")

        # ── Fetch Road Incidents from TomTom Traffic API ──────────
        tomtom_incidents_count = 0
        tomtom_incidents_summary = []
        tomtom_key = getattr(settings, 'MYTOMTOM_API_KEY', None)
        if tomtom_key:
            try:
                # Bounding box ~11km x 11km around coordinate (same as FIRMS)
                tt_lon_min, tt_lat_min = lon - 0.1, lat - 0.1
                tt_lon_max, tt_lat_max = lon + 0.1, lat + 0.1
                bbox_str = f"{tt_lon_min},{tt_lat_min},{tt_lon_max},{tt_lat_max}"

                # Fields we care about for the AI prompt
                fields = "{incidents{type,properties{id,iconCategory,magnitudeOfDelay,events{description,iconCategory},from,to,roadNumbers,timeValidity}}}"

                # Filter to incidents that matter: Accident, DangerousConditions, RoadClosed, LaneClosed, RoadWorks, Flooding
                category_filter = "1,3,7,8,9,11"

                tomtom_url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
                tomtom_params = {
                    "key": tomtom_key,
                    "bbox": bbox_str,
                    "fields": fields,
                    "language": "en-GB",
                    "categoryFilter": category_filter,
                    "timeValidityFilter": "present"
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
                        category = props.get("iconCategory", "Unknown")
                        from_road = props.get("from", "")
                        to_road = props.get("to", "")
                        delay = props.get("magnitudeOfDelay", 0)  # 0=unknown,1=minor,2=moderate,3=major,4=undefined
                        delay_label = {0: "Unknown delay", 1: "Minor delay", 2: "Moderate delay", 3: "Major delay", 4: "Undefined delay"}.get(delay, "")
                        summary_entry = {
                            "category": category,
                            "description": desc.replace("#", ""),
                            "from": from_road,
                            "to": to_road,
                            "delay": delay_label
                        }
                        tomtom_incidents_summary.append(summary_entry)
                    print(f"TomTom: {tomtom_incidents_count} road incident(s) detected near {city_name or lat}")
                else:
                    print(f"TomTom API returned {tt_resp.status_code}: {tt_resp.text[:200]}")
            except Exception as e:
                print(f"TomTom traffic fetch failed: {e}")

        # Allow mock overrides (for testing)
        mock_current = data.get('mock_current_weather')
        if mock_current:
            current.update(mock_current)
            if 'aqi' in mock_current:
                aqi = mock_current['aqi']
            if 'firms_fires_detected' in mock_current:
                firms_fires_detected = mock_current['firms_fires_detected']
            if 'tomtom_incidents_count' in mock_current:
                tomtom_incidents_count = mock_current['tomtom_incidents_count']
            if 'tomtom_incidents_summary' in mock_current:
                tomtom_incidents_summary = mock_current['tomtom_incidents_summary']

        current['aqi'] = aqi
        current['firms_fires_detected'] = firms_fires_detected
        current['tomtom_incidents_count'] = tomtom_incidents_count
        current['tomtom_incidents_summary'] = tomtom_incidents_summary

        # ── Save to DB ────────────────────────────────────────────
        parsed_time = parse_datetime(user_time) if user_time else None
        new_request = WeatherRequest.objects.create(
            user_id=user_id,
            latitude=lat,
            longitude=lon,
            user_time=parsed_time,
            city_name=city_name,
            aqi=aqi,
            firms_fires_detected=firms_fires_detected,
            tomtom_incidents_count=tomtom_incidents_count,
            tomtom_incidents_summary=tomtom_incidents_summary,
            temperature_2m=current.get('temperature_2m'),
            relative_humidity_2m=current.get('relative_humidity_2m'),
            apparent_temperature=current.get('apparent_temperature'),
            is_day=current.get('is_day'),
            precipitation=current.get('precipitation'),
            rain=current.get('rain'),
            showers=current.get('showers'),
            snowfall=current.get('snowfall'),
            weather_code=current.get('weather_code'),
            cloud_cover=current.get('cloud_cover'),
            pressure_msl=current.get('pressure_msl'),
            surface_pressure=current.get('surface_pressure'),
            wind_speed_10m=current.get('wind_speed_10m'),
            wind_direction_10m=current.get('wind_direction_10m'),
            wind_gusts_10m=current.get('wind_gusts_10m'),
        )

        # ── Anomaly check ─────────────────────────────────────────
        from django.conf import settings
        debug_force_crisis = getattr(settings, 'DEBUG_FORCE_CRISIS_ANOMALY', False)

        if debug_force_crisis:
            # Overwrite current weather memory to guarantee it triggers an anomaly
            current['temperature_2m'] = 48.5
            current['apparent_temperature'] = 52.0
            current['precipitation'] = 0.0
            current['firms_fires_detected'] = 4

        anomaly_diff = is_weather_unusual(
            current, previous_request,
            city_name=city_name
        )

        if debug_force_crisis and not anomaly_diff:
            anomaly_diff = f"In {city_name or 'Gujrat'}, temperature rose dramatically to 48.5°C and 4 thermal anomalies/fires were detected."

        ai_response = None

        if anomaly_diff:
            # 1. Generate ranked search queries (best → worst, location-aware)
            ranked_queries = generate_ranked_queries(
                anomaly_diff,
                city=city_name
            )
            print(f"Ranked queries ({len(ranked_queries)}): {ranked_queries}")

            # Log keywords to DB
            from api.models import AnomalyKeywordLog
            AnomalyKeywordLog.objects.create(
                weather_request=new_request,
                keywords_english=ranked_queries,
                keywords_roman_urdu=[]
            )

            # 2. Per-platform smart search: try ranked queries in order
            #    until useful results are found or list is exhausted.
            #    Run all 4 platforms in parallel for speed.
            platforms = ["youtube", "x", "facebook", "tiktok"]
            search_results_dict = {}   # platform -> {query_used, results}

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(smart_search_platform, p, ranked_queries): p
                    for p in platforms
                }
                for future in futures:
                    platform = futures[future]
                    try:
                        res = future.result()
                        search_results_dict[platform] = {
                            "query_used": res["query_used"],
                            "results":    res["results"]
                        }
                        SearchLog.objects.create(
                            weather_request=new_request,
                            platform=platform,
                            query=res["query_used"],
                            results=res["results"]
                        )
                    except Exception as e:
                        print(f"Search failed for {platform}: {e}")
                        search_results_dict[platform] = {"query_used": "", "results": []}

            # 3. Send to AI for analysis + top_posts selection
            ai_data = analyze_with_ai(
                anomaly_diff,
                search_results_dict,
                traffic_incidents=tomtom_incidents_summary or None
            )
            if "error" not in ai_data:
                ai_response = ai_data["response_json"]
                AIResponseLog.objects.create(
                    weather_request=new_request,
                    prompt=ai_data["prompt"],
                    response_json=ai_response
                )

        # ── Build lean, mobile-ready response ─────────────────────
        final_response = {
            'status': 'success',
            # Core environmental snapshot
            'environment': {
                'temperature_c':       current.get('temperature_2m'),
                'feels_like_c':        current.get('apparent_temperature'),
                'humidity_pct':        current.get('relative_humidity_2m'),
                'precipitation_mm':    current.get('precipitation'),
                'wind_speed_kmh':      current.get('wind_speed_10m'),
                'wind_gusts_kmh':      current.get('wind_gusts_10m'),
                'weather_code':        current.get('weather_code'),
                'aqi':                 aqi,
                'active_fires_nearby': firms_fires_detected,
            },
            # Road incidents (always present so app can show live traffic)
            'traffic': {
                'incident_count': tomtom_incidents_count,
                'incidents':      tomtom_incidents_summary
            }
        }

        # Alert block — only added when there is an actual crisis returned from AI analysis
        if ai_response and ai_response.get('type') != 'safe':
            notif = ai_response.get('notification_details', {})
            final_response['alert'] = {
                'type':          ai_response.get('type'),
                'severity':      ai_response.get('severity'),
                'confidence':    ai_response.get('confidence'),
                'title':         ai_response.get('title'),
                'details':       ai_response.get('details'),
                'safety_advises':  ai_response.get('safety_advises', []),
                'help_resources':  ai_response.get('help_resources', []),
                'notification': {
                    'type':  notif.get('type', 'weather_alert'),
                    'title': notif.get('title', ''),
                    'body':  notif.get('body', notif.get('details', ''))
                },
                'top_posts': ai_response.get('top_posts', [])
            }

        return JsonResponse(final_response, json_dumps_params={'ensure_ascii': False})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Exception in weather_view: {e}")
        return JsonResponse({'error': str(e)}, status=500)