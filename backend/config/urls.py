from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from vitals.views import VitalReadingIngestView

# ============================================================
# Swagger/OpenAPI Configuration
# ============================================================
schema_view = get_schema_view(
    openapi.Info(
        title="Health Monitor API",
        default_version='v1',
        description="🏥 Health Monitor System API - Complete documentation",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@healthmonitor.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

# ============================================================
# URL Patterns
# ============================================================
urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/readings/ingest/', VitalReadingIngestView.as_view(), name='readings-ingest'),
    path('api/auth/', include('accounts.urls')),
    path('api/vitals/', include('vitals.urls')),
    path('api/alerts/', include('alerts.urls')),
    path('api/demo/', include('demo.urls')),
    path('api/emergency/', include('emergency.urls')),
    path('api/location/', include('location.urls')),
    path('api/ml/', include('ml_api.urls')),
    
    # Swagger/OpenAPI Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('swagger.json/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# ============================================================
# Serve static and media files in development
# ============================================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)