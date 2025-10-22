import json
from uuid import UUID
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import get_object_or_404
import logging

from .models import PlantIdentificationRequest

logger = logging.getLogger(__name__)


class IdentificationConsumer(AsyncJsonWebsocketConsumer):
    """Streams progress updates for a single PlantIdentificationRequest.

    URL: ws/plant-identification/requests/<uuid:request_id>/
    Group: plant_id_req_<request_id>
    """

    @property
    def request_id(self) -> str:
        rid = self.scope.get("url_route", {}).get("kwargs", {}).get("request_id")
        # Django path converter passes UUID instance; normalize to str
        if isinstance(rid, UUID):
            return str(rid)
        return str(rid)

    @property
    def group_name(self) -> str:
        return f"plant_id_req_{self.request_id}"

    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            logger.info(
                "WS IdentificationConsumer.connect: unauthorized user, closing 4401 (request_id=%s)",
                self.request_id,
            )
            await self.close(code=4401)  # Unauthorized
            return

        # Authorization: user must own the request
        try:
            _ = await self._get_user_request(user)
        except Exception as exc:
            logger.info(
                "WS IdentificationConsumer.connect: forbidden for user_id=%s request_id=%s error=%s, closing 4403",
                getattr(user, "id", None),
                self.request_id,
                str(exc),
            )
            await self.close(code=4403)  # Forbidden
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(
            "WS IdentificationConsumer.connect: accepted for user_id=%s group=%s",
            getattr(user, "id", None),
            self.group_name,
        )
        # Initial ping
        await self.send_json({
            "type": "init",
            "request_id": self.request_id,
            "message": "connected",
        })

    async def disconnect(self, close_code):
        logger.info(
            "WS IdentificationConsumer.disconnect: group=%s close_code=%s",
            self.group_name,
            close_code,
        )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def _get_user_request(self, user):
        # Use sync-to-async safe ORM call via database_sync_to_async? Channels 4
        # allows awaiting sync_to_async. Keep it simple using get in threadpool.
        from asgiref.sync import sync_to_async
        return await sync_to_async(PlantIdentificationRequest.objects.get)(
            request_id=self.request_id, user=user
        )

    # Handlers for group messages
    async def progress(self, event):
        # event keys: {"type": "progress", "stage": str, "status": str, "data": dict}
        await self.send_json({
            "type": "progress",
            "stage": event.get("stage"),
            "status": event.get("status"),
            "data": event.get("data", {}),
        })

    async def completed(self, event):
        await self.send_json({
            "type": "completed",
            "status": event.get("status"),
            "results_count": event.get("results_count", 0),
        })

    async def error(self, event):
        await self.send_json({
            "type": "error",
            "message": event.get("message", "Unknown error"),
        })
