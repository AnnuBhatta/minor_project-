from django.urls import path
from .views import *

urlpatterns = [
    # Emergency events
    path('events/', EmergencyEventListCreateView.as_view(), name='emergency-list-create'),
    path('events/<int:pk>/', EmergencyEventDetailView.as_view(), name='emergency-detail'),
    path('events/<int:pk>/resolve/', EmergencyResolveView.as_view(), name='emergency-resolve'),
    path('events/<int:pk>/cancel/', EmergencyCancelView.as_view(), name='emergency-cancel'),
    
    # Active emergencies (for guardians)
    path('active/', ActiveEmergenciesView.as_view(), name='active-emergencies'),
    
    # Notifications
    path('notifications/', EmergencyNotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:pk>/', EmergencyNotificationDetailView.as_view(), name='notification-detail'),
    path('notifications/<int:pk>/read/', MarkNotificationReadView.as_view(), name='notification-read'),
]