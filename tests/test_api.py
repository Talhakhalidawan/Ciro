import json
import requests
import uuid

def test_weather_endpoint_success():
    url = 'http://localhost:8000/api/weather/'
    
    # Generate a random user ID for testing
    user_id = str(uuid.uuid4())
    
    dummy_locations = [
        {'user_id': 'user3', 'city_name': 'Islamabad', 'sector': 'G-10', 'latitude': 32.384332172219864, 'longitude': 73.39963776224754, 'time': '2023-10-27T13:00:00Z'}
    ]
    
    for loc in dummy_locations:
        print(f"\n--- Testing location: {loc['user_id']} ({loc['city_name']}) ---")
        payload = {
            'user_id': user_id,
            'city_name': loc['city_name'],
            'sector': loc['sector'],
            'latitude': loc['latitude'],
            'longitude': loc['longitude'],
            'time': loc['time']
        }
        print(f"Sending POST request to {url} with payload: {payload}")
        response = requests.post(url, json=payload)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Status from server:", data.get('status'))
            if 'ai_analysis' in data:
                print("--- AI ANOMALY ANALYSIS TRIGGERED ---")
                print(json.dumps(data['ai_analysis'], indent=2, ensure_ascii=False))
            else:
                print("No anomaly detected (safe).")
            print("Success! Data for", loc['user_id'], "has been saved.")
        else:
            print("Error:", response.text)

def test_weather_anomaly_trigger():
    url = 'http://localhost:8000/api/weather/'
    user_id = f"test-anomaly-{uuid.uuid4()}"
    
    print(f"\n==========================================")
    print(f"TESTING ANOMALY TRIGGER FOR USER: {user_id}")
    print(f"==========================================")
    
    # 1. Send normal baseline request using mock weather to make sure it's stable
    print("\n--- 1. Establishing normal weather baseline (34°C in Islamabad G-10) ---")
    payload1 = {
        'user_id': user_id,
        'city_name': 'Islamabad',
        'sector': 'G-10',
        'latitude': 33.684,
        'longitude': 73.048,
        'time': '2023-10-27T13:00:00Z',
        'mock_current_weather': {
            'temperature_2m': 34.0,
            'wind_gusts_10m': 10.0,
            'precipitation': 0.0,
            'aqi': 80
        }
    }
    response1 = requests.post(url, json=payload1)
    print(f"Baseline Status Code: {response1.status_code}")
    if response1.status_code == 200:
        data = response1.json()
        print("Baseline saved. Current Temp:", data['weather']['current']['temperature_2m'], "°C, AQI:", data['weather_details'].get('aqi'))
    else:
        print("Baseline failed:", response1.text)
        return
        
    # 2. Send request with mocked drastic weather change (temperature rise to 41°C)
    print("\n--- 2. Sending request with realistic anomaly temperature (41°C, rise of +7°C) ---")
    payload2 = {
        'user_id': user_id,
        'city_name': 'Islamabad',
        'sector': 'G-10',
        'latitude': 33.684,
        'longitude': 73.048,
        'time': '2023-10-27T14:00:00Z',
        'mock_current_weather': {
            'temperature_2m': 46.0,  # 41°C vs previous 34°C (rise of 7 > threshold 5)
            'wind_gusts_10m': 10.0,
            'precipitation': 0.0,
            'aqi': 80
        }
    }
    response2 = requests.post(url, json=payload2)
    print(f"Anomaly Status Code: {response2.status_code}")
    if response2.status_code == 200:
        data = response2.json()
        print("Server Response Status:", data.get('status'))
        if 'ai_analysis' in data:
            print("\n🚨 SUCCESS! AI ANOMALY ANALYSIS TRIGGERED!")
            print(json.dumps(data['ai_analysis'], indent=2, ensure_ascii=False))
        else:
            print("❌ FAILURE: No AI analysis returned. Anomaly didn't trigger or AI failed.")
    else:
        print("Request failed:", response2.text)

def test_firms_anomaly_trigger():
    url = 'http://localhost:8000/api/weather/'
    user_id = f"test-firms-{uuid.uuid4()}"
    
    print(f"\n==========================================")
    print(f"TESTING FIRMS ANOMALY TRIGGER FOR USER: {user_id}")
    print(f"==========================================")
    
    # 1. Send normal baseline request
    print("\n--- 1. Establishing normal baseline (No fires) ---")
    payload1 = {
        'user_id': user_id,
        'city_name': 'Islamabad',
        'sector': 'Margalla Hills',
        'latitude': 33.74,
        'longitude': 73.05,
        'time': '2023-10-27T13:00:00Z',
        'mock_current_weather': {
            'temperature_2m': 30.0,
            'firms_fires_detected': 0
        }
    }
    response1 = requests.post(url, json=payload1)
    print(f"Baseline Status Code: {response1.status_code}")
    
    # 2. Send request with mocked FIRMS fires
    print("\n--- 2. Sending request with mocked FIRMS thermal anomaly (5 fires) ---")
    payload2 = {
        'user_id': user_id,
        'city_name': 'Islamabad',
        'sector': 'Margalla Hills',
        'latitude': 33.74,
        'longitude': 73.05,
        'time': '2023-10-27T14:00:00Z',
        'mock_current_weather': {
            'temperature_2m': 30.0,
            'firms_fires_detected': 5  # Anomaly trigger
        }
    }
    response2 = requests.post(url, json=payload2)
    print(f"Anomaly Status Code: {response2.status_code}")
    if response2.status_code == 200:
        data = response2.json()
        print("Server Response Status:", data.get('status'))
        if 'ai_analysis' in data:
            print("\n🚨 SUCCESS! NASA FIRMS AI ANOMALY TRIGGERED!")
            print(json.dumps(data['ai_analysis'], indent=2, ensure_ascii=False))
        else:
            print("❌ FAILURE: No AI analysis returned for FIRMS anomaly.")
    else:
        print("Request failed:", response2.text)

def test_tomtom_anomaly_trigger():
    url = 'http://localhost:8000/api/weather/'
    user_id = f"test-tomtom-{uuid.uuid4()}"

    print(f"\n==========================================")
    print(f"TESTING TOMTOM ROAD INCIDENTS FOR USER: {user_id}")
    print(f"==========================================")

    # 1. Baseline (no incidents)
    print("\n--- 1. Establishing normal baseline (no road incidents) ---")
    payload1 = {
        'user_id': user_id,
        'city_name': 'Islamabad',
        'sector': 'G-10',
        'latitude': 33.684,
        'longitude': 73.048,
        'time': '2023-10-27T13:00:00Z',
        'mock_current_weather': {
            'temperature_2m': 30.0,
            'tomtom_incidents_count': 0,
            'tomtom_incidents_summary': []
        }
    }
    response1 = requests.post(url, json=payload1)
    print(f"Baseline Status Code: {response1.status_code}")

    # 2. Trigger with mocked road incidents
    print("\n--- 2. Sending request with mocked TomTom road incidents ---")
    payload2 = {
        'user_id': user_id,
        'city_name': 'Islamabad',
        'sector': 'G-10',
        'latitude': 33.684,
        'longitude': 73.048,
        'time': '2023-10-27T14:00:00Z',
        'mock_current_weather': {
            'temperature_2m': 30.0,
            'tomtom_incidents_count': 2,
            'tomtom_incidents_summary': [
                {"category": "RoadClosed", "description": "Road closed due to flooding", "from": "G-10 Markaz", "to": "G-9 Interchange", "delay": "Major delay"},
                {"category": "Accident", "description": "Multi-vehicle accident", "from": "G-10/1", "to": "IJP Road", "delay": "Moderate delay"}
            ]
        }
    }
    response2 = requests.post(url, json=payload2)
    print(f"Anomaly Status Code: {response2.status_code}")
    if response2.status_code == 200:
        data = response2.json()
        print("Server Response Status:", data.get('status'))
        print("Traffic Incidents in Response:", json.dumps(data.get('traffic_incidents', {}), indent=2))
        if 'ai_analysis' in data:
            print("\n🚨 SUCCESS! TOMTOM ROAD INCIDENT AI ANOMALY TRIGGERED!")
            print(json.dumps(data['ai_analysis'], indent=2, ensure_ascii=False))
        else:
            print("❌ FAILURE: No AI analysis returned for TomTom road incident.")
    else:
        print("Request failed:", response2.text)

if __name__ == "__main__":
    print("--- Running Live API Tests ---")
    test_weather_anomaly_trigger()
    test_firms_anomaly_trigger()
    test_tomtom_anomaly_trigger()
    test_weather_endpoint_success()
    print("--- Done ---")
