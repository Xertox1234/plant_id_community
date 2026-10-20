"""ASGI middleware for the project's socket and HTTP stacks."""

import asyncio
import logging
import time

from apps.core.ratelimit import (
    _mask_ip,
    log_safe_ip,
    meta_from_asgi_scope,
    trusted_client_ip_from_meta,
)
from apps.forum_host import constants as live_constants
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def _normalise(origin: str) -> str:
    return origin.strip().rstrip("/").lower()


class OptionalOriginValidator:
    """Refuse a socket whose ``Origin`` header names a site we don't serve.

    The web app authenticates its socket with a cookie, so without this any
    website could open a socket as the signed-in reader (cross-site WebSocket
    hijacking). The allowed set is ``CORS_ALLOWED_ORIGINS``, compared exactly
    (scheme, host and port), read per connection so settings overrides apply.

    A socket with NO Origin passes: browsers always send one, and the mobile
    app sends none. Channels' stock ``OriginValidator`` rejects that case.
    The refusal is a close before accept, so the handshake fails with 403.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            origin = None
            for name, value in scope.get("headers", []):
                if name == b"origin":
                    origin = value.decode("latin-1")
                    break
            if origin is not None:
                allowed = {_normalise(o) for o in settings.CORS_ALLOWED_ORIGINS}
                if _normalise(origin) not in allowed:
                    logger.info("[SECURITY] WS origin refused: %.100s", origin)
                    await send({"type": "websocket.close"})
                    return
        return await self.inner(scope, receive, send)


class WebsocketConnectRateLimit:
    """Refuse a socket connect over the per-IP rate, before any auth work.

    The session stack and the JWT middleware both query the database before a
    consumer's ``connect()`` runs, so a reconnect storm costs DB work per
    attempt unless it is cut off out here. A fixed window per trusted client
    IP (masked as the HTTP limiter masks it), counted in the shared cache.

    The refusal is accept-then-close 4429, the code both clients back off on.
    An IP that cannot be resolved, or a cache that cannot count (the project
    cache answers ``None`` when Redis is down), is admitted: fail open, like
    the consumer's socket caps. Non-websocket scopes pass straight through.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket" and await self._over_rate(scope):
            await receive()  # the websocket.connect event
            await send({"type": "websocket.accept"})
            await send(
                {"type": "websocket.close", "code": live_constants.LIVE_CLOSE_LIMITED}
            )
            return None
        return await self.inner(scope, receive, send)

    async def _over_rate(self, scope) -> bool:
        ip = trusted_client_ip_from_meta(meta_from_asgi_scope(scope))
        if not ip:
            return False
        window = live_constants.LIVE_CONNECT_RATE_WINDOW_SECONDS
        limit = live_constants.LIVE_CONNECT_RATE_PER_IP
        key = (
            f"{live_constants.LIVE_CONNECT_RATE_KEY_PREFIX}:"
            f"{_mask_ip(ip)}:{int(time.time() // window)}"
        )
        try:
            await cache.aadd(key, 0, window + 5)
            count = await cache.aincr(key)
        except ValueError:  # the key expired between add and incr
            return False
        if count is None or count <= limit:
            return False
        if count == limit + 1:  # once per IP per window
            logger.info("[FORUM_LIVE] connect rate limited ip=%s", log_safe_ip(ip))
        return True


class HttpConcurrencyLimit:
    """Bound in-flight HTTP requests per worker; extra requests wait.

    Under ASGI, Django runs each in-flight request's sync code on its own
    thread, holding its own DB connection, so in-flight requests are what
    Postgres connections scale with. Sockets are a different load: an idle
    one holds no thread. Bounding HTTP here, apart from uvicorn's
    ``--limit-concurrency`` (which counts sockets too and answers 503), lets
    open sockets grow without starving requests or the database. Requests
    over the limit queue rather than fail; uvicorn's cap still bounds the
    total connections a worker holds.

    Non-HTTP scopes pass straight through. The semaphore is made per event
    loop (uvicorn runs one per worker; tests start a fresh loop per call).
    """

    def __init__(self, inner, limit: int):
        self.inner = inner
        self.limit = limit
        self._loop = None
        self._semaphore = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop, self._semaphore = loop, asyncio.Semaphore(self.limit)
        return self._semaphore

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.inner(scope, receive, send)
        async with self._get_semaphore():
            return await self.inner(scope, receive, send)
