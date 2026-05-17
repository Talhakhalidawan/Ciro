import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from api.models import WeatherRequest, SearchLog, AIResponseLog
from django.utils.dateparse import parse_datetime
from concurrent.futures import ThreadPoolExecutor
from api.services import search_youtube, search_reddit, search_telegram, search_google, analyze_with_ai

def is_weather_unusual(current_data, previous_request):
    """
    Checks if the current weather is significantly different from the previous.
    Returns a string detailing the difference if unusual, else None.
    Thresholds:
    - Temperature change > 10 degrees C
    - Wind gusts > 50 km/h (if previously < 20)
    - Precipitation > 10mm (if previously 0)
    Modify this logic to change anomaly detection thresholds.
    """
    if not previous_request:
        return None
        
    current_temp = current_data.get('temperature_2m', 0)
    prev_temp = previous_request.temperature_2m or 0
    if abs(current_temp - prev_temp) > 10:
        return f"Temperature changed drastically from {prev_temp}°C to {current_temp}°C."

    current_wind = current_data.get('wind_gusts_10m', 0)
    prev_wind = previous_request.wind_gusts_10m or 0
    if current_wind > 50 and prev_wind < 20:
        return f"Wind gusts suddenly increased to {current_wind} km/h."

    current_precip = current_data.get('precipitation', 0)
    prev_precip = previous_request.precipitation or 0
    if current_precip > 10 and prev_precip < 2:
        return f"Sudden high precipitation detected: {current_precip} mm."

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
        
        if not user_id or lat is None or lon is None:
            return JsonResponse({'error': 'user_id, latitude, and longitude are required'}, status=400)
            
        # Get previous weather data for this user
        previous_request = WeatherRequest.objects.filter(user_id=user_id).order_by('-created_at').first()

        # Call Open-Meteo API
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "timezone": "auto"
        }
        
        response = requests.get(url, params=params)
        if response.status_code != 200:
            return JsonResponse({'error': 'Failed to fetch weather data'}, status=502)
            
        weather_data = response.json()
        current = weather_data.get('current', {})

        # Allow mocking of current weather values for testing anomalies
        mock_current = data.get('mock_current_weather')
        if mock_current:
            current.update(mock_current)

        # Save to database
        parsed_time = parse_datetime(user_time) if user_time else None
        new_request = WeatherRequest.objects.create(
            user_id=user_id,
            latitude=lat,
            longitude=lon,
            user_time=parsed_time,
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
        
        anomaly_diff = is_weather_unusual(current, previous_request)
        ai_response = None

        if anomaly_diff:
            # Spawn parallel tasks
            search_results_dict = {}
            with ThreadPoolExecutor(max_workers=4) as executor:
                query = "weather anomaly emergency"
                future_yt = executor.submit(search_youtube, query)
                future_rd = executor.submit(search_reddit, query)
                future_tg = executor.submit(search_telegram, query)
                future_gg = executor.submit(search_google, query)

                for future in [future_yt, future_rd, future_tg, future_gg]:
                    res = future.result()
                    platform = res['platform']
                    search_results_dict[platform] = res['results']
                    
                    # Log search to DB
                    SearchLog.objects.create(
                        weather_request=new_request,
                        platform=platform,
                        query=query,
                        results=res['results']
                    )

            # Pass to AI
            ai_data = analyze_with_ai(anomaly_diff, search_results_dict)
            if "error" not in ai_data:
                ai_response = ai_data["response_json"]
                # Log AI to DB
                AIResponseLog.objects.create(
                    weather_request=new_request,
                    prompt=ai_data["prompt"],
                    response_json=ai_response
                )

        # Build response
        final_response = {
            'status': 'success',
            'user_time_received': user_time,
            'weather': weather_data
        }
        
        # If AI response exists and is not safe
        if ai_response and ai_response.get('type') != 'safe':
            final_response['ai_analysis'] = ai_response
            
        return JsonResponse(final_response)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Exception in weather_view: {e}")
        return JsonResponse({'error': str(e)}, status=500)
