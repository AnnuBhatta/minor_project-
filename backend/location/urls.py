from django.urls import path
from .views import *

urlpatterns = [
    path('update/', UpdateLocationView.as_view(), name='update-location'),
    path('history/', LocationHistoryView.as_view(), name='location-history'),
    path('current/', CurrentLocationView.as_view(), name='current-location'),
    path('current/<int:user_id>/', CurrentLocationView.as_view(), name='user-current-location'),
]