"""The live topic socket (forum live replies, slice 2).

``ws/forum/topics/<topic_id>/``: a signed-in reader with the topic open joins
the topic's group and receives the id-only events ``live.broadcast`` sends.
Clients send nothing but an optional ``{"type": "ping"}``.

Every refusal a client must tell apart is accept-then-close: a close before
accept reaches the client as a bare handshake 403 and the code is lost.

| Condition | Close code |
|---|---|
| ``FORUM_LIVE_UPDATES_ENABLED`` off | 4503 (client stops; web polls) |
| no valid user | 4401 (mobile refreshes once; web backs off) |
| topic not visible by the REST rule | 4404 |
| per-user or per-IP socket cap reached | 4429 |

Async, so an idle socket holds no thread and no DB connection.
"""

import json
import logging
from typing import Optional

from apps.core.ratelimit import trusted_client_ip_from_meta
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.core.cache import cache
from wagtail_forum.api.views import visible_topics

from . import constants
from .live import PROTOCOL_VERSION, topic_group

logger = logging.getLogger(__name__)


def _scope_meta(scope) -> dict:
    """A META-shaped view of the handshake, for the shared client-IP rule.

    Built by Django's own ASGI rules (``ASGIRequest.__init__``): a header
    name containing ``_`` is dropped, so a client's ``x_forwarded_for`` can't
    stand in for the proxy's ``X-Forwarded-For``, and a repeated header is
    joined with ``,`` rather than the last copy winning.
    """
    meta = {"REMOTE_ADDR": (scope.get("client") or ("",))[0] or ""}
    for raw_name, raw_value in scope.get("headers", []):
        name = raw_name.decode("latin-1")
        if "_" in name:
            continue
        key = "HTTP_" + name.upper().replace("-", "_")
        value = raw_value.decode("latin-1")
        if key in meta:
            value = meta[key] + "," + value
        meta[key] = value
    return meta


@database_sync_to_async
def _topic_is_visible(topic_id: int) -> bool:
    return visible_topics().filter(pk=topic_id).exists()


class TopicLiveConsumer(AsyncJsonWebsocketConsumer):
    """Deliver one topic's live events to a signed-in reader."""

    async def connect(self):
        self.topic_id = int(self.scope["url_route"]["kwargs"]["topic_id"])
        self.group_name: Optional[str] = None
        self._counted_keys: list[str] = []
        user = self.scope.get("user")
        self.user_id = user.pk if user is not None and user.is_authenticated else None

        if not settings.FORUM_LIVE_UPDATES_ENABLED:
            return await self._refuse(constants.LIVE_CLOSE_DISABLED, "disabled")
        if self.user_id is None:
            return await self._refuse(
                constants.LIVE_CLOSE_UNAUTHENTICATED, "unauthenticated"
            )
        if not await _topic_is_visible(self.topic_id):
            return await self._refuse(constants.LIVE_CLOSE_NOT_FOUND, "not visible")
        if not await self._take_slots():
            return await self._refuse(constants.LIVE_CLOSE_LIMITED, "over cap")

        self.group_name = topic_group(self.topic_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(
            "[FORUM_LIVE] connect user=%s topic=%s", self.user_id, self.topic_id
        )

    async def disconnect(self, code):
        if self.group_name is not None:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(
                "[FORUM_LIVE] disconnect user=%s topic=%s code=%s",
                self.user_id,
                self.topic_id,
                code,
            )
        await self._give_back_slots()

    async def receive_json(self, content, **kwargs):
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json({"v": PROTOCOL_VERSION, "type": "pong"})

    @classmethod
    async def decode_json(cls, text_data):
        # A frame that is not JSON is ignored like any other unknown input.
        try:
            return json.loads(text_data)
        except ValueError:
            return None

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if text_data is None:
            return  # binary frames mean nothing here
        await super().receive(text_data=text_data, **kwargs)

    async def forum_live_event(self, message):
        event = message["event"]
        await self.send_json(event)
        if event.get("type") == "topic.removed":
            # The topic is gone for everyone: deliver the event, then drop the
            # subscription so this socket hears nothing more about it.
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            self.group_name = None
            await self.close(code=constants.LIVE_CLOSE_NOT_FOUND)

    async def _refuse(self, code: int, reason: str) -> None:
        logger.info(
            "[FORUM_LIVE] refused user=%s topic=%s code=%s reason=%s",
            self.user_id,
            self.topic_id,
            code,
            reason,
        )
        await self.accept()
        await self.close(code=code)

    def _cap_keys(self) -> list[tuple[str, int]]:
        prefix = constants.LIVE_SOCKET_COUNT_KEY_PREFIX
        keys = [(f"{prefix}:u:{self.user_id}", constants.LIVE_MAX_SOCKETS_PER_USER)]
        ip = trusted_client_ip_from_meta(_scope_meta(self.scope))
        if ip:
            keys.append((f"{prefix}:ip:{ip}", constants.LIVE_MAX_SOCKETS_PER_IP))
        return keys

    async def _take_slots(self) -> bool:
        """Count this socket against each cap; False (and nothing held) when
        one is full. A cache that cannot count (Redis down; the project cache
        ignores its exceptions) admits the socket uncounted."""
        ttl = constants.LIVE_SOCKET_COUNT_TTL_SECONDS
        for key, cap in self._cap_keys():
            try:
                await cache.aadd(key, 0, ttl)
                count = await cache.aincr(key)
            except ValueError:  # the key expired between add and incr
                continue
            if count is None:
                continue
            self._counted_keys.append(key)
            if count > cap:
                await self._give_back_slots()
                return False
        return True

    async def _give_back_slots(self) -> None:
        keys, self._counted_keys = self._counted_keys, []
        for key in keys:
            try:
                await cache.adecr(key)
            except ValueError:  # expired (TTL backstop): nothing to give back
                pass
