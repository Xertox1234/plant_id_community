"""
ASGI config for plant_community_backend project with Django Channels support.

Routes HTTP to Django ASGI application and WebSocket to Channels consumers.
"""

import os

# Set settings module BEFORE importing Django/Channels
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')

from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

# Initialize Django ASGI application early to ensure AppRegistry is ready.
django_asgi_app = get_asgi_application()

# Now it is safe to import modules that rely on Django apps
from .channels_middleware import JWTAuthMiddleware

try:
    from . import routing as project_routing
    websocket_routes = project_routing.websocket_urlpatterns
except Exception:
    websocket_routes = []

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(websocket_routes)
        )
    ),
})
