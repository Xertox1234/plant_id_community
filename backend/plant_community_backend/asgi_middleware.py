"""ASGI middleware for the project's socket and HTTP stacks."""

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
