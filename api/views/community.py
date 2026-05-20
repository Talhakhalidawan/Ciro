import json
import math
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from api.models import CommunityIncident
from api.services import log_step


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def incident_to_dict(inc):
    return {
        'id': inc.id,
        'user_id': inc.user_id,
        'title': inc.title,
        'description': inc.description,
        'incident_type': inc.incident_type,
        'latitude': inc.latitude,
        'longitude': inc.longitude,
        'radius_km': inc.radius_km,
        'custom_boundary': inc.custom_boundary,
        'created_at': inc.created_at.isoformat(),
        'is_active': inc.is_active,
    }


@csrf_exempt
@require_POST
def create_incident(request):
    """Create a new community incident report."""
    try:
        data = json.loads(request.body)
        
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        incident_type = data.get('incident_type', 'other')
        user_id = data.get('user_id', 'anonymous')
        lat = data.get('latitude')
        lon = data.get('longitude')
        radius_km = data.get('radius_km', 1.0)
        custom_boundary = data.get('custom_boundary')
        user_lat = data.get('user_latitude')
        user_lon = data.get('user_longitude')

        log_step("COMMUNITY CREATE", "New incident report received", {
            "user_id": user_id,
            "title": title,
            "type": incident_type,
            "lat": lat, "lon": lon,
            "radius_km": radius_km,
            "user_lat": user_lat, "user_lon": user_lon,
        })
        
        if not title or lat is None or lon is None:
            log_step("COMMUNITY CREATE", "Rejected: missing required fields")
            return JsonResponse({'error': 'title, latitude, and longitude are required'}, status=400)
        
        # Enforce 70km reporting radius
        if user_lat is not None and user_lon is not None:
            distance = haversine_km(user_lat, user_lon, lat, lon)
            if distance > 70:
                log_step("COMMUNITY CREATE", f"Rejected: incident is {distance:.1f}km from user (max 70km)")
                return JsonResponse({'error': 'You can only report incidents within 70 km of your location'}, status=400)
        
        incident = CommunityIncident.objects.create(
            user_id=user_id,
            title=title,
            description=description,
            incident_type=incident_type,
            latitude=lat,
            longitude=lon,
            radius_km=radius_km,
            custom_boundary=custom_boundary,
        )

        log_step("COMMUNITY CREATE", f"Incident #{incident.id} saved successfully", {
            "id": incident.id, "type": incident_type, "title": title
        })
        
        return JsonResponse({
            'status': 'success',
            'incident': incident_to_dict(incident)
        }, status=201)
        
    except json.JSONDecodeError:
        log_step("COMMUNITY ERROR", "Invalid JSON in request body")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        log_step("COMMUNITY ERROR", f"Exception in create_incident: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def list_incidents(request):
    """
    GET incidents near the user's location.
    Query params: lat, lon (required)
    Also returns a 'notify' flag for incidents within 20km.
    Optional: since_id to only get new incidents after a specific ID.
    """
    try:
        lat = request.GET.get('lat')
        lon = request.GET.get('lon')
        since_id = request.GET.get('since_id', '0')

        log_step("COMMUNITY LIST", "Fetching incidents", {
            "lat": lat, "lon": lon, "since_id": since_id
        })
        
        if lat is None or lon is None:
            return JsonResponse({'error': 'lat and lon query params are required'}, status=400)
        
        lat = float(lat)
        lon = float(lon)
        since_id = int(since_id)
        
        incidents = CommunityIncident.objects.filter(is_active=True)
        if since_id > 0:
            incidents = incidents.filter(id__gt=since_id)
        
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=24)
        incidents = incidents.filter(created_at__gte=cutoff)
        
        results = []
        notify_count = 0
        for inc in incidents:
            distance = haversine_km(lat, lon, inc.latitude, inc.longitude)
            if distance <= 70:
                entry = incident_to_dict(inc)
                entry['distance_km'] = round(distance, 1)
                entry['notify'] = distance <= 20
                if entry['notify']:
                    notify_count += 1
                results.append(entry)
        
        results.sort(key=lambda x: x['id'], reverse=True)

        log_step("COMMUNITY LIST", f"Returning {len(results)} incidents ({notify_count} within 20km notify zone)")
        
        return JsonResponse({
            'status': 'success',
            'count': len(results),
            'incidents': results
        })
        
    except (ValueError, TypeError) as e:
        log_step("COMMUNITY ERROR", f"Invalid parameters: {e}")
        return JsonResponse({'error': f'Invalid parameters: {e}'}, status=400)
    except Exception as e:
        log_step("COMMUNITY ERROR", f"Exception in list_incidents: {e}")
        return JsonResponse({'error': str(e)}, status=500)
