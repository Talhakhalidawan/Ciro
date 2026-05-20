from django.urls import path
from .views.weather import weather_view
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('weather/', weather_view, name='weather'),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)