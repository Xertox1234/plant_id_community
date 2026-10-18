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

# Now it is safe to import modules that rely on Django apps. Routing is
# imported plainly: a broken routing module must fail the boot, never serve
# zero socket routes in silence.
from . import routing as project_routing  # noqa: E402
from .asgi_middleware import OptionalOriginValidator  # noqa: E402
from .channels_middleware import JWTAuthMiddleware  # noqa: E402


def build_websocket_app(routes):
    """The full websocket stack around ``URLRouter(routes)``.

    The Origin check is outermost, so a cross-site socket is refused before
    any auth work. The session stack is OUTSIDE the JWT middleware: it parses
    ``scope["cookies"]`` and sets the session user (or anonymous), and the JWT
    middleware replaces that user only when a token validates.
    """
    return OptionalOriginValidator(
        AuthMiddlewareStack(JWTAuthMiddleware(URLRouter(routes)))
    )


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": build_websocket_app(project_routing.websocket_urlpatterns),
    }
)
