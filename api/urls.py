from django.urls import path
from .views.weather import weather_view
from .views.community import create_incident, list_incidents


urlpatterns = [
    path('weather/', weather_view, name='weather'),
    path('community/incidents/', list_incidents, name='list_incidents'),
    path('community/incidents/create/', create_incident, name='create_incident'),
]
