import json
import requests
import uuid

def test_weather_endpoint_success():
    url = 'http://localhost:8000/api/weather/'
    
    # Generate a random user ID for testing
    user_id = str(uuid.uuid4())
    
    dummy_locations = [
        {'user_id': 'user1', 'latitude': 52.52, 'longitude': 13.41, 'time': '2023-10-27T10:00:00Z'},
        {'user_id': 'user2', 'latitude': 40.71, 'longitude': -74.00, 'time': '2023-10-27T12:00:00Z'},
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

def test_weather_endpoint_missing_coordinates():
    url = 'http://localhost:8000/api/weather/'
    payload = {
        'time': '2023-10-27T10:00:00Z',
        'user_id': 'test-user-123'
    }
    print(f"\nSending POST request to {url} with payload: {payload}")
    response = requests.post(url, json=payload)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 400:
        print("Correctly received 400 Bad Request error:", response.json())
    else:
        print("Unexpected response:", response.text)

if __name__ == "__main__":
    print("--- Running Live API Tests ---")
    test_weather_endpoint_success()
    test_weather_endpoint_missing_coordinates()
    print("--- Done ---")
