from django.contrib import admin
from .models import WeatherRequest, SearchLog, AIResponseLog, AnomalyKeywordLog, AdminCrisisScenario

# Register your models here.

class AdminCrisisScenarioAdmin(admin.ModelAdmin):
    list_display = ('crisis_type', 'location', 'is_active', 'created_at')
    list_filter = ('is_active', 'crisis_type')
    search_fields = ('location',)

admin.site.register(WeatherRequest)
admin.site.register(SearchLog)
admin.site.register(AIResponseLog)
admin.site.register(AnomalyKeywordLog)
admin.site.register(AdminCrisisScenario, AdminCrisisScenarioAdmin)