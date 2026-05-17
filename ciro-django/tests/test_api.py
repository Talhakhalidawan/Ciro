import json
from django.test import TestCase, Client
from django.urls import reverse

class WeatherAPITest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_weather_endpoint_success(self):
        url = '/api/weather/'
        payload = {
            'latitude': 52.52,
            'longitude': 13.41,
            'time': '2023-10-27T10:00:00Z'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['user_time_received'], payload['time'])
        self.assertIn('weather', data)
        self.assertIn('current', data['weather'])

    def test_weather_endpoint_missing_coordinates(self):
        url = '/api/weather/'
        payload = {
            'time': '2023-10-27T10:00:00Z'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
