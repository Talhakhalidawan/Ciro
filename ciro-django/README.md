# Ciro Django

A simple Django backend project for Ciro. 

## Endpoints

### `POST /api/weather/`
This endpoint receives the user's location and current time, and fetches the current weather data from the free [Open-Meteo API](https://open-meteo.com/).

**Request Payload:**
```json
{
  "latitude": 52.52,
  "longitude": 13.41,
  "time": "2023-10-27T10:00:00Z"
}
```

**Response:**
Returns the status, the time received from the user, and the current weather information including temperature, rainfall, weather code, etc.

```json
{
  "status": "success",
  "user_time_received": "2023-10-27T10:00:00Z",
  "weather": {
    "latitude": 52.52,
    "longitude": 13.41,
    "current": {
      "time": "...",
      "interval": 900,
      "temperature_2m": 12.3,
      "relative_humidity_2m": 75,
      ...
    }
    ...
  }
}
```

## Running the project
1. Install dependencies: `pip install django requests`
2. Run server: `python manage.py runserver`

## Testing
Run the tests using the command: `python manage.py test tests`
