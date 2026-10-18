"""ASGI middleware for the project's socket and HTTP stacks."""

import asyncio
import logging

from django.conf import settings

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
