from apps.forum_host.consumers import TopicLiveConsumer
from django.urls import path, re_path

from .consumers import DenyConsumer

# WebSocket routes. Real routes go BEFORE the catch-all, which must stay last:
# it closes every other path with 4404 instead of letting URLRouter raise
# (a logged traceback per scanner probe).
websocket_urlpatterns = [
    path("ws/forum/topics/<int:topic_id>/", TopicLiveConsumer.as_asgi()),
    re_path(r"", DenyConsumer.as_asgi()),
]
