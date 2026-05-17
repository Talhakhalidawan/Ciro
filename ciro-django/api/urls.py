from django.urls import path
from .views.weather import weather_view

urlpatterns = [
    path('weather/', weather_view, name='weather'),
]
