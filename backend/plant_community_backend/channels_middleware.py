import logging
from typing import Optional

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken

logger = logging.getLogger(__name__)

ACCESS_COOKIE_NAME = "access_token"


class JWTAuthMiddleware(BaseMiddleware):
    """Authenticate a WebSocket with the same access JWT that REST accepts.

    Sources, in order: an ``Authorization: Bearer <access>`` header (the mobile
    app; ``dart:io`` sockets can set headers) and the ``access_token`` cookie
    (the web app; it is ``path="/"``, so the browser sends it on the handshake).
    A token in the query string is NOT accepted: URLs end up in logs.

    Must sit INSIDE channels' ``AuthMiddlewareStack``: that stack parses
    ``scope["cookies"]`` and sets ``scope["user"]`` (the session user, or
    anonymous). This middleware replaces that user only when a token validates,
    so a socket with no token keeps its session user.

    No part of a token is ever logged.
    """

    async def __call__(self, scope, receive, send):
        source, raw = self._raw_token(scope)
        user = None
        if raw is not None:
            user = await self._user_for(raw)
            if user is not None:
                scope = dict(scope, user=user)
        logger.debug(
            "[AUTH] WS auth source=%s user_id=%s",
            source,
            user.pk if user is not None else None,
        )
        return await super().__call__(scope, receive, send)

    @staticmethod
    def _raw_token(scope) -> tuple[str, Optional[str]]:
        for name, value in scope.get("headers", []):
            if name == b"authorization":
                scheme, _, token = value.decode("latin-1").partition(" ")
                if scheme == "Bearer" and token.strip():
                    return "header", token.strip()
        token = scope.get("cookies", {}).get(ACCESS_COOKIE_NAME)
        if token:
            return "cookie", token
        return "none", None

    @database_sync_to_async
    def _user_for(self, raw: str):
        """The active user the token names, or None. simplejwt's own checks:
        signature, expiry, token type, the user-id claim and ``is_active``."""
        auth = JWTAuthentication()
        try:
            # simplejwt types the raw token as bytes; PyJWT's decode encodes a
            # str to UTF-8 bytes itself, so this is the same input it saw.
            return auth.get_user(auth.get_validated_token(raw.encode("utf-8")))
        except (InvalidToken, AuthenticationFailed) as exc:
            logger.warning("[AUTH] WS token rejected: %s", type(exc).__name__)
            return None
