"""
ASGI config for plant_community_backend project with Django Channels support.

Routes HTTP to Django ASGI application and WebSocket to Channels consumers.
"""

import os

# Set settings module BEFORE importing Django/Channels
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plant_community_backend.settings")

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

# Initialize Django ASGI application early to ensure AppRegistry is ready.
django_asgi_app = get_asgi_application()

# Now it is safe to import modules that rely on Django apps
from .channels_middleware import JWTAuthMiddleware  # noqa: E402

try:
    from . import routing as project_routing

    websocket_routes = project_routing.websocket_urlpatterns
except Exception:
    websocket_routes = []


def build_websocket_app(routes):
    """The full websocket stack around ``URLRouter(routes)``.

    The session stack is OUTSIDE the JWT middleware: it parses
    ``scope["cookies"]`` and sets the session user (or anonymous), and the JWT
    middleware replaces that user only when a token validates.
    """
    return AuthMiddlewareStack(JWTAuthMiddleware(URLRouter(routes)))


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": build_websocket_app(websocket_routes),
    }
)
