import json
import requests
import uuid

def test_weather_endpoint_success():
    url = 'http://localhost:8000/api/weather/'
    
    # Generate a random user ID for testing
    user_id = str(uuid.uuid4())
    
    dummy_locations = [
        {'user_id': 'user3', 'latitude': 32.384332172219864, 'longitude': 73.39963776224754, 'time': '2023-10-27T13:00:00Z'}
    ]
    
    for loc in dummy_locations:
        print(f"\n--- Testing location: {loc['user_id']} ---")
        payload = {
            'user_id': user_id,
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
                print(json.dumps(data['ai_analysis'], indent=2))
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
    print("\n--- 1. Establishing normal weather baseline (15°C) ---")
    payload1 = {
        'user_id': user_id,
        'latitude': 32.384,
        'longitude': 73.399,
        'time': '2023-10-27T13:00:00Z',
        'mock_current_weather': {
            'temperature_2m': 25.0,
            'wind_gusts_10m': 10.0,
            'precipitation': 0.0
        }
    }
    response1 = requests.post(url, json=payload1)
    print(f"Baseline Status Code: {response1.status_code}")
    if response1.status_code == 200:
        data = response1.json()
        print("Baseline saved. Current Temp:", data['weather']['current']['temperature_2m'], "°C")
    else:
        print("Baseline failed:", response1.text)
        return
        
    # 2. Send request with mocked drastic weather change (temperature jump of 15°C)
    print("\n--- 2. Sending request with sudden temperature jump (+15°C) ---")
    payload2 = {
        'user_id': user_id,
        'latitude': 32.384,
        'longitude': 73.399,
        'time': '2023-10-27T14:00:00Z',
        'mock_current_weather': {
            'temperature_2m': 100.0,  # 30°C vs previous 15°C (diff = 15 > threshold 10)
            'wind_gusts_10m': 10.0,
            'precipitation': 0.0
        }
    }
    response2 = requests.post(url, json=payload2)
    print(f"Anomaly Status Code: {response2.status_code}")
    if response2.status_code == 200:
        data = response2.json()
        print("Server Response Status:", data.get('status'))
        if 'ai_analysis' in data:
            print("\n🚨 SUCCESS! AI ANOMALY ANALYSIS TRIGGERED!")
            print(json.dumps(data['ai_analysis'], indent=2))
        else:
            print("❌ FAILURE: No AI analysis returned. Anomaly didn't trigger or AI failed.")
    else:
        print("Request failed:", response2.text)

if __name__ == "__main__":
    print("--- Running Live API Tests ---")
    test_weather_anomaly_trigger()
    test_weather_endpoint_success()
    print("--- Done ---")
