from django.contrib import admin
from .models import WeatherRequest, SearchLog, AIResponseLog, AnomalyKeywordLog, AdminCrisisScenario, CommunityIncident

# Register your models here.

class AdminCrisisScenarioAdmin(admin.ModelAdmin):
    list_display = ('crisis_type', 'location', 'is_active', 'created_at')
    list_filter = ('is_active', 'crisis_type')
    search_fields = ('location',)

class CommunityIncidentAdmin(admin.ModelAdmin):
    list_display = ('title', 'incident_type', 'user_id', 'latitude', 'longitude', 'is_active', 'created_at')
    list_filter = ('is_active', 'incident_type')
    search_fields = ('title', 'description', 'user_id')

admin.site.register(WeatherRequest)
admin.site.register(SearchLog)
admin.site.register(AIResponseLog)
admin.site.register(AnomalyKeywordLog)
admin.site.register(AdminCrisisScenario, AdminCrisisScenarioAdmin)
admin.site.register(CommunityIncident, CommunityIncidentAdmin)