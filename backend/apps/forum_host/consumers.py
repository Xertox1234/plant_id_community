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
| topic stopped being visible (re-checked every ~5 min) | 4404 |
| per-user or per-IP socket cap reached | 4429 |

Async, so an idle socket holds no thread and no DB connection.
"""

import asyncio
import json
import logging
import random
from typing import Optional

from apps.core.ratelimit import meta_from_asgi_scope, trusted_client_ip_from_meta
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.core.cache import cache
from wagtail_forum.api.views import visible_topics

from . import constants
from .live import PROTOCOL_VERSION, topic_group

logger = logging.getLogger(__name__)


@database_sync_to_async
def _topic_is_visible(topic_id: int) -> bool:
    # bool() only for mypy: the package is untyped to it, so exists() is Any.
    return bool(visible_topics().filter(pk=topic_id).exists())


class TopicLiveConsumer(AsyncJsonWebsocketConsumer):
    """Deliver one topic's live events to a signed-in reader."""

    async def __call__(self, scope, receive, send):
        # disconnect() runs only on a websocket.disconnect message. A consumer
        # that exits any other way (a handler raising on a send to a client
        # that just dropped) must not leave its re-check timer running.
        try:
            return await super().__call__(scope, receive, send)
        finally:
            recheck_task = getattr(self, "_recheck_task", None)
            if recheck_task is not None:
                recheck_task.cancel()

    async def connect(self):
        self.topic_id = int(self.scope["url_route"]["kwargs"]["topic_id"])
        self.group_name: Optional[str] = None
        self._counted_keys: list[str] = []
        self._recheck_task: Optional[asyncio.Task] = None
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
        self._recheck_task = asyncio.create_task(self._recheck_loop())
        logger.info(
            "[FORUM_LIVE] connect user=%s topic=%s", self.user_id, self.topic_id
        )

    async def disconnect(self, code):
        # Cancel without awaiting: the loop holds nothing that needs unwinding,
        # and awaiting a cancelled task here can stall the close.
        self._cancel_recheck()
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
            self._cancel_recheck()
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            self.group_name = None
            await self.close(code=constants.LIVE_CLOSE_NOT_FOUND)

    def _cancel_recheck(self) -> None:
        if self._recheck_task is not None:
            self._recheck_task.cancel()

    async def _recheck_loop(self) -> None:
        """Close 4404 once the topic stops being visible by the REST rule.

        A board made private or a topic unpublished sends no event every reader
        hears, so without this an open socket would keep receiving id-only
        events for a topic its reader can no longer open. A DB error is not
        "not visible": it is logged once per socket and the next tick retries.
        """
        failure_logged = False
        while True:
            await asyncio.sleep(
                constants.LIVE_VISIBILITY_RECHECK_SECONDS
                * random.uniform(*constants.LIVE_VISIBILITY_RECHECK_JITTER)
            )
            try:
                visible = await _topic_is_visible(self.topic_id)
            except Exception as exc:  # CancelledError is not an Exception
                if not failure_logged:
                    failure_logged = True
                    logger.warning(
                        "[FORUM_LIVE] recheck failed user=%s topic=%s: %s",
                        self.user_id,
                        self.topic_id,
                        type(exc).__name__,
                    )
                continue
            if not visible:
                logger.info(
                    "[FORUM_LIVE] recheck closed user=%s topic=%s",
                    self.user_id,
                    self.topic_id,
                )
                if self.group_name is not None:
                    await self.channel_layer.group_discard(
                        self.group_name, self.channel_name
                    )
                    self.group_name = None
                await self.close(code=constants.LIVE_CLOSE_NOT_FOUND)
                return

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
        ip = trusted_client_ip_from_meta(meta_from_asgi_scope(self.scope))
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
