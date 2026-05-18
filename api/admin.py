from django.contrib import admin
from .models import WeatherRequest, SearchLog, AIResponseLog, AnomalyKeywordLog

# Register your models here.

admin.site.register(WeatherRequest)
admin.site.register(SearchLog)
admin.site.register(AIResponseLog)
admin.site.register(AnomalyKeywordLog)