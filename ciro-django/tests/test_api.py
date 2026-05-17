import json
import requests

def test_weather_endpoint_success():
    url = 'http://localhost:8000/api/weather/'
    
    dummy_locations = [
        {'name': 'Berlin', 'latitude': 52.52, 'longitude': 13.41, 'time': '2023-10-27T10:00:00Z'},
        {'name': 'New York', 'latitude': 40.71, 'longitude': -74.00, 'time': '2023-10-27T12:00:00Z'},
        {'name': 'Tokyo', 'latitude': 35.68, 'longitude': 139.69, 'time': '2023-10-27T20:00:00Z'}
    ]
    
    for loc in dummy_locations:
        print(f"\n--- Testing location: {loc['name']} ---")
        payload = {
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
            print("Success! Data for", loc['name'], "has been saved to the database on the backend.")
        else:
            print("Error:", response.text)

def test_weather_endpoint_missing_coordinates():
    url = 'http://localhost:8000/api/weather/'
    payload = {
        'time': '2023-10-27T10:00:00Z'
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
