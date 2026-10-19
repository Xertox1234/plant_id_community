"""A test-only consumer that reports who the socket authenticated as."""

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.urls import path


class EchoUserConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        user = self.scope.get("user")
        authed = user is not None and user.is_authenticated
        await self.send_json({"user_id": user.pk if authed else None})


ECHO_PATH = "/ws/echo/"
echo_routes = [path("ws/echo/", EchoUserConsumer.as_asgi())]
