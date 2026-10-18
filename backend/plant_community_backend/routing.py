from django.urls import re_path

from .consumers import DenyConsumer

# WebSocket routes. Real routes go BEFORE the catch-all, which must stay last:
# it closes any other /ws/ path with 4404 instead of letting URLRouter raise.
websocket_urlpatterns = [
    re_path(r"^ws/", DenyConsumer.as_asgi()),
]
