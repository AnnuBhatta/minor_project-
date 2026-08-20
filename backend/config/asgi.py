import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from config.jwt_auth import JWTAuthMiddleware
from emergency.routing import websocket_urlpatterns as emergency_urls
from location.routing import websocket_urlpatterns as location_urls
from alerts.routing import websocket_urlpatterns as alerts_urls

# Combine all WebSocket URLs
websocket_urlpatterns = alerts_urls + emergency_urls + location_urls

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
    ),
})
