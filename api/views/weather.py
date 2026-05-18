import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from api.models import WeatherRequest, SearchLog, AIResponseLog
from django.utils.dateparse import parse_datetime
from concurrent.futures import ThreadPoolExecutor
from api.services import (
    search_youtube,
    search_x,
    search_facebook,
    search_tiktok,
    analyze_with_ai,
    generate_search_keywords
)

def is_weather_unusual(current_data, previous_request, city_name=None, sector=None):
    """
    Checks if the current weather is significantly different from the previous.
    Returns a string detailing the difference if unusual, else None.
    Thresholds:
    - Temperature rise > 5 degrees C
    - Rain for two consecutive readings (precipitation > 0)
    - AQI jumped by more than 50 points
    """
    if not previous_request:
        return None

    area_str = f"In {city_name}" if city_name else "In this area"
    if city_name and sector:
        area_str = f"In {city_name} ({sector})"

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
        sector = data.get('sector')

        if not user_id or lat is None or lon is None:
            return JsonResponse({'error': 'user_id, latitude, and longitude are required'}, status=400)

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

        # Allow mock overrides (for testing)
        mock_current = data.get('mock_current_weather')
        if mock_current:
            current.update(mock_current)
            if 'aqi' in mock_current:
                aqi = mock_current['aqi']

        current['aqi'] = aqi

        # ── Save to DB ────────────────────────────────────────────
        parsed_time = parse_datetime(user_time) if user_time else None
        new_request = WeatherRequest.objects.create(
            user_id=user_id,
            latitude=lat,
            longitude=lon,
            user_time=parsed_time,
            city_name=city_name,
            sector=sector,
            aqi=aqi,
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
        anomaly_diff = is_weather_unusual(
            current, previous_request,
            city_name=city_name, sector=sector
        )
        ai_response = None

        if anomaly_diff:
            # 1. Generate location‑aware keywords (fixes Hindi issue)
            keywords_data = generate_search_keywords(
                anomaly_diff,
                city=city_name,
                sector=sector
            )
            keywords_list = keywords_data.get("keywords", ["weather anomaly Pakistan"])

            # Build the combined search query (still used as a seed)
            query = " ".join(keywords_list)
            print(f"Generated search query for anomaly: {query}")

            # Log keywords
            from api.models import AnomalyKeywordLog
            AnomalyKeywordLog.objects.create(
                weather_request=new_request,
                keywords_english=keywords_data.get("keywords_english", []),
                keywords_roman_urdu=keywords_data.get("keywords_roman_urdu", [])
            )

            # 2. Build the location string that will be prepended to all searches
            location_str = ""
            if city_name:
                location_str = city_name
                if sector:
                    location_str += f" {sector}"
            # Fallback if no location given
            if not location_str:
                location_str = "Pakistan"

            # 3. Parallel searches with location prepended
            search_results_dict = {}
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_yt = executor.submit(search_youtube, query, location_str)
                future_x = executor.submit(search_x, query, location_str)
                future_fb = executor.submit(search_facebook, query, location_str)
                future_tk = executor.submit(search_tiktok, query, location_str)

                for future in [future_yt, future_x, future_fb, future_tk]:
                    res = future.result()
                    platform = res['platform']
                    
                    # Clean '#' characters from results to prevent markdown parser / hashing issues in LLM prompts
                    cleaned_results = []
                    for item in res.get('results', []):
                        cleaned_results.append({
                            "title": item.get("title", "").replace("#", ""),
                            "snippet": item.get("snippet", "").replace("#", "")
                        })
                    
                    search_results_dict[platform] = cleaned_results

                    SearchLog.objects.create(
                        weather_request=new_request,
                        platform=platform,
                        query=f"{location_str} {query}" if location_str else query,
                        results=cleaned_results
                    )

            # 4. Send to AI
            ai_data = analyze_with_ai(anomaly_diff, search_results_dict)
            if "error" not in ai_data:
                ai_response = ai_data["response_json"]
                AIResponseLog.objects.create(
                    weather_request=new_request,
                    prompt=ai_data["prompt"],
                    response_json=ai_response
                )

        # ── Final response ────────────────────────────────────────
        final_response = {
            'status': 'success',
            'user_time_received': user_time,
            'weather_details': {
                'temperature_2m': current.get('temperature_2m'),
                'relative_humidity_2m': current.get('relative_humidity_2m'),
                'apparent_temperature': current.get('apparent_temperature'),
                'precipitation': current.get('precipitation'),
                'wind_speed_10m': current.get('wind_speed_10m'),
                'wind_gusts_10m': current.get('wind_gusts_10m'),
                'weather_code': current.get('weather_code'),
                'aqi': aqi,
            },
            'weather': weather_data
        }

        if ai_response and ai_response.get('type') != 'safe':
            final_response['ai_analysis'] = ai_response

        return JsonResponse(final_response, json_dumps_params={'ensure_ascii': False})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Exception in weather_view: {e}")
        return JsonResponse({'error': str(e)}, status=500)