import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from api.models import WeatherRequest
from django.utils.dateparse import parse_datetime

@csrf_exempt
@require_POST
def weather_view(request):
    try:
        data = json.loads(request.body)
        lat = data.get('latitude')
        lon = data.get('longitude')
        user_time = data.get('time')
        
        if lat is None or lon is None:
            return JsonResponse({'error': 'latitude and longitude are required'}, status=400)
            
        # Call Open-Meteo API
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "timezone": "auto"
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            weather_data = response.json()
            
            # Save to database
            parsed_time = parse_datetime(user_time) if user_time else None
            WeatherRequest.objects.create(
                latitude=lat,
                longitude=lon,
                user_time=parsed_time,
                weather_data=weather_data
            )
            
            return JsonResponse({
                'status': 'success',
                'user_time_received': user_time,
                'weather': weather_data
            })
        else:
            return JsonResponse({'error': 'Failed to fetch weather data'}, status=502)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
