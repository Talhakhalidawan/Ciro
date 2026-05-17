from django.contrib import admin
from .models import WeatherRequest, SearchLog, AIResponseLog

# Register your models here.

admin.site.register(WeatherRequest)
admin.site.register(SearchLog)
admin.site.register(AIResponseLog)