import json
import requests
import uuid

URL = 'http://localhost:8000/api/weather/'


def _post(payload):
    return requests.post(URL, json=payload, timeout=120)


def _print_response(data):
    env = data.get('environment', data.get('weather_details', {}))
    print(f"  Environment: temp={env.get('temperature_c', env.get('temperature_2m'))}°C "
          f"| aqi={env.get('aqi')} | fires={env.get('active_fires_nearby', 0)}")
    traffic = data.get('traffic', data.get('traffic_incidents', {}))
    print(f"  Traffic: {traffic.get('incident_count', traffic.get('count', 0))} incident(s)")
    if 'alert' in data:
        alert = data['alert']
        print(f"\n  🚨 ALERT TRIGGERED!")
        print(f"     type      : {alert.get('type')}")
        print(f"     severity  : {alert.get('severity')}")
        print(f"     confidence: {alert.get('confidence')}")
        print(f"     title     : {alert.get('title')}")
        print(f"     details   : {alert.get('details')}")
        print(f"     safety    : {alert.get('safety_advises')}")
        print(f"     helplines : {alert.get('help_resources')}")
        notif = alert.get('notification', {})
        print(f"     push notif: [{notif.get('type')}] {notif.get('title')} — {notif.get('body')}")
        top_posts = alert.get('top_posts', [])
        if top_posts:
            print(f"\n  📰 TOP POSTS ({len(top_posts)}):")
            for tp in top_posts:
                print(f"     [{tp.get('platform')}] query='{tp.get('query')}'")
                for item in (tp.get('items') or [])[:2]:
                    print(f"       • {item.get('title','')[:80]}")
                    print(f"         Link: {item.get('url', 'None')}")
        else:
            print("  📰 top_posts: [] (no relevant social posts found)")
    elif data.get('status') == 'success':
        print("  ✅ No crisis — safe response returned.")
    else:
        print(f"  ❌ Unexpected response: {json.dumps(data, indent=2)[:400]}")


# ── Test 1: Weather heatwave anomaly ──────────────────────────────────────────
def test_weather_anomaly_trigger():
    user_id = f"test-anomaly-{uuid.uuid4()}"
    print(f"\n{'='*60}")
    print(f"TEST 1 — WEATHER HEATWAVE ANOMALY")
    print(f"{'='*60}")

    print("\n  Step 1: Baseline (34°C, Islamabad)")
    r1 = _post({
        'user_id': user_id, 'city_name': 'Islamabad',
        'latitude': 33.684, 'longitude': 73.048, 'time': '2023-10-27T13:00:00Z',
        'mock_current_weather': {'temperature_2m': 34.0, 'precipitation': 0.0, 'aqi': 80}
    })
    if r1.status_code != 200:
        print(f"  ❌ Baseline failed: {r1.status_code} {r1.text[:200]}")
        return
    d1 = r1.json()
    env1 = d1.get('environment', d1.get('weather_details', {}))
    print(f"  ✅ Baseline saved. Temp={env1.get('temperature_c', env1.get('temperature_2m'))}°C")

    print("\n  Step 2: Anomaly (46°C — rise of +12°C triggers alert)")
    r2 = _post({
        'user_id': user_id, 'city_name': 'Islamabad',
        'latitude': 33.684, 'longitude': 73.048, 'time': '2023-10-27T14:00:00Z',
        'mock_current_weather': {'temperature_2m': 46.0, 'precipitation': 0.0, 'aqi': 80}
    })
    print(f"  HTTP {r2.status_code}")
    if r2.status_code == 200:
        _print_response(r2.json())
    else:
        print(f"  ❌ {r2.text[:300]}")


# ── Test 2: NASA FIRMS fire anomaly ───────────────────────────────────────────
def test_firms_anomaly_trigger():
    user_id = f"test-firms-{uuid.uuid4()}"
    print(f"\n{'='*60}")
    print(f"TEST 2 — NASA FIRMS THERMAL ANOMALY (FIRE)")
    print(f"{'='*60}")

    print("\n  Step 1: Baseline (no fires)")
    r1 = _post({
        'user_id': user_id, 'city_name': 'Islamabad Margalla Hills',
        'latitude': 33.74, 'longitude': 73.05, 'time': '2023-10-27T13:00:00Z',
        'mock_current_weather': {'temperature_2m': 30.0, 'firms_fires_detected': 0}
    })
    print(f"  HTTP {r1.status_code}")

    print("\n  Step 2: 5 active fire hotspots detected")
    r2 = _post({
        'user_id': user_id, 'city_name': 'Islamabad Margalla Hills',
        'latitude': 33.74, 'longitude': 73.05, 'time': '2023-10-27T14:00:00Z',
        'mock_current_weather': {'temperature_2m': 30.0, 'firms_fires_detected': 5}
    })
    print(f"  HTTP {r2.status_code}")
    if r2.status_code == 200:
        _print_response(r2.json())
    else:
        print(f"  ❌ {r2.text[:300]}")


# ── Test 3: TomTom road incidents ─────────────────────────────────────────────
def test_tomtom_anomaly_trigger():
    user_id = f"test-tomtom-{uuid.uuid4()}"
    print(f"\n{'='*60}")
    print(f"TEST 3 — TOMTOM ROAD INCIDENTS")
    print(f"{'='*60}")

    print("\n  Step 1: Baseline (no road incidents)")
    r1 = _post({
        'user_id': user_id, 'city_name': 'Islamabad',
        'latitude': 33.684, 'longitude': 73.048, 'time': '2023-10-27T13:00:00Z',
        'mock_current_weather': {
            'temperature_2m': 30.0,
            'tomtom_incidents_count': 0, 'tomtom_incidents_summary': []
        }
    })
    print(f"  HTTP {r1.status_code}")

    print("\n  Step 2: Road closed + accident")
    r2 = _post({
        'user_id': user_id, 'city_name': 'Islamabad',
        'latitude': 33.684, 'longitude': 73.048, 'time': '2023-10-27T14:00:00Z',
        'mock_current_weather': {
            'temperature_2m': 30.0,
            'tomtom_incidents_count': 2,
            'tomtom_incidents_summary': [
                {"category": "RoadClosed", "description": "Road closed due to flooding",
                 "from": "G-10 Markaz", "to": "G-9 Interchange", "delay": "Major delay"},
                {"category": "Accident", "description": "Multi-vehicle accident",
                 "from": "G-10/1", "to": "IJP Road", "delay": "Moderate delay"}
            ]
        }
    })
    print(f"  HTTP {r2.status_code}")
    if r2.status_code == 200:
        _print_response(r2.json())
    else:
        print(f"  ❌ {r2.text[:300]}")


# ── Test 4: Safe / no-anomaly baseline ────────────────────────────────────────
def test_safe_response():
    user_id = f"test-safe-{uuid.uuid4()}"
    print(f"\n{'='*60}")
    print(f"TEST 4 — SAFE RESPONSE (no anomaly)")
    print(f"{'='*60}")
    unique_city = f"SafeCity-{uuid.uuid4()}"
    r = _post({
        'user_id': user_id, 'city_name': unique_city,
        'latitude': 33.684, 'longitude': 73.048, 'time': '2023-10-27T13:00:00Z'
    })
    print(f"  HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        _print_response(data)
        # Verify response shape
        assert 'environment' in data, "Missing 'environment' key"
        assert 'traffic' in data,     "Missing 'traffic' key"
        assert 'alert' not in data,   "'alert' should NOT be present for safe response"
        print("  ✅ Response shape is correct (environment + traffic, no alert)")
    else:
        print(f"  ❌ {r.text[:300]}")


if __name__ == "__main__":
    print("=" * 60)
    print("  CIRO WEATHER API — FULL TEST SUITE")
    print("=" * 60)
    test_weather_anomaly_trigger()
    test_firms_anomaly_trigger()
    test_tomtom_anomaly_trigger()
    test_safe_response()
    print(f"\n{'='*60}")
    print("  Done.")
