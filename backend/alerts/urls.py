from django.urls import path
from .views import AlertDetailView, AlertListCreateView

app_name = 'alerts'

urlpatterns = [
    path('', AlertListCreateView.as_view(), name='alert-list-create'),
    path('<int:pk>/', AlertDetailView.as_view(), name='alert-detail'),
]
