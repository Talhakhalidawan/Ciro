from django.db import models

class WeatherRequest(models.Model):
    user_id = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    user_time = models.DateTimeField(null=True, blank=True)
    
    # Localized area details
    city_name = models.CharField(max_length=255, null=True, blank=True)
    aqi = models.IntegerField(null=True, blank=True)
    firms_fires_detected = models.IntegerField(default=0, null=True, blank=True)
    tomtom_incidents_count = models.IntegerField(default=0, null=True, blank=True)
    tomtom_incidents_summary = models.JSONField(default=list, null=True, blank=True)
    
    # Weather fields
    temperature_2m = models.FloatField(null=True, blank=True)
    relative_humidity_2m = models.FloatField(null=True, blank=True)
    apparent_temperature = models.FloatField(null=True, blank=True)
    is_day = models.IntegerField(null=True, blank=True)
    precipitation = models.FloatField(null=True, blank=True)
    rain = models.FloatField(null=True, blank=True)
    showers = models.FloatField(null=True, blank=True)
    snowfall = models.FloatField(null=True, blank=True)
    weather_code = models.IntegerField(null=True, blank=True)
    cloud_cover = models.FloatField(null=True, blank=True)
    pressure_msl = models.FloatField(null=True, blank=True)
    surface_pressure = models.FloatField(null=True, blank=True)
    wind_speed_10m = models.FloatField(null=True, blank=True)
    wind_direction_10m = models.FloatField(null=True, blank=True)
    wind_gusts_10m = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Request by {self.user_id} at {self.created_at}"

class SearchLog(models.Model):
    weather_request = models.ForeignKey(WeatherRequest, on_delete=models.CASCADE, related_name="searches")
    platform = models.CharField(max_length=50) # youtube, reddit, telegram, google
    query = models.CharField(max_length=255)
    results = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class AIResponseLog(models.Model):
    weather_request = models.ForeignKey(WeatherRequest, on_delete=models.CASCADE, related_name="ai_responses")
    prompt = models.TextField()
    response_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class AnomalyKeywordLog(models.Model):
    weather_request = models.ForeignKey(WeatherRequest, on_delete=models.CASCADE, related_name="keywords")
    keywords_english = models.JSONField(default=list)
    keywords_roman_urdu = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Keywords for request {self.weather_request.id}"

class AdminCrisisScenario(models.Model):
    CRISIS_CHOICES = [
        ('heatwave', 'Heatwave'),
        ('fire', 'Fire'),
        ('road_accident', 'Road Accident'),
        ('safe_response', 'Safe Response')
    ]

    crisis_type = models.CharField(max_length=50, choices=CRISIS_CHOICES)
    location = models.CharField(max_length=255, help_text="Enter city name (e.g. Islamabad), or 'all' to apply to all requests.")
    is_active = models.BooleanField(default=True, help_text="Check to activate this simulated scenario.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "ACTIVE" if self.is_active else "INACTIVE"
        return f"[{status}] {self.get_crisis_type_display()} in {self.location}"


class CommunityIncident(models.Model):
    INCIDENT_TYPES = [
        ('accident', 'Accident'),
        ('fire', 'Fire'),
        ('flood', 'Flooding'),
        ('road_closure', 'Road Closure'),
        ('power_outage', 'Power Outage'),
        ('gas_leak', 'Gas Leak'),
        ('protest', 'Protest'),
        ('crime', 'Crime'),
        ('medical', 'Medical Emergency'),
        ('other', 'Other'),
    ]

    user_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    description = models.TextField()
    incident_type = models.CharField(max_length=50, choices=INCIDENT_TYPES, default='other')
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_km = models.FloatField(default=1.0, help_text="Affected area radius in km")
    # Optional custom polygon boundary (stored as JSON array of {lat, lng} points)
    custom_boundary = models.JSONField(null=True, blank=True, help_text="Custom polygon points if user drew a shape")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.incident_type}] {self.title} by {self.user_id}"
