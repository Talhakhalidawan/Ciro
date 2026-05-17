from django.db import models

class WeatherRequest(models.Model):
    latitude = models.FloatField()
    longitude = models.FloatField()
    user_time = models.DateTimeField(null=True, blank=True)
    weather_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Request at {self.created_at} for lat:{self.latitude}, lon:{self.longitude}"
