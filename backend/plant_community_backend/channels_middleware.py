import urllib.parse
from typing import Optional
import logging

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
logger = logging.getLogger(__name__)


class JWTAuthMiddleware(BaseMiddleware):
    """Authenticate WebSocket connections via JWT.

    Looks for token in query string (?token=...) as a simple, frontend-friendly option.
    Also falls back to reading the JWT from cookies (httpOnly) when the query param
    is absent, aligning WS auth with cookie-first REST auth.

    If token is missing/invalid, leaves user as AnonymousUser and allows outer
    AuthMiddlewareStack (session) to take effect if present.
    """

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        query_string = scope.get("query_string", b"")
        token_source = None
        token = self._extract_token(query_string)
        if token:
            token_source = "query"
        if not token:
            # Fallback to cookie-based token (httpOnly cookie set by backend)
            token = self._extract_token_from_cookies(scope)
            if token:
                token_source = "cookie"
        user = None

        if token:
            try:
                access = AccessToken(token)
                user_id = access.get("user_id")
                if user_id:
                    user = await self._get_user(user_id)
                logger.info(
                    "WS JWTAuthMiddleware: token_source=%s token_prefix=%s user_id=%s",
                    token_source,
                    token[:10] if isinstance(token, str) else None,
                    user_id,
                )
            except Exception as exc:
                logger.warning(
                    "WS JWTAuthMiddleware: token parse/validation failed (source=%s): %s",
                    token_source,
                    str(exc),
                )
                user = None
        else:
            logger.info(
                "WS JWTAuthMiddleware: no token found (query_string=%s, has_cookie=%s)",
                query_string.decode(errors="ignore"),
                any(h[0] == b"cookie" for h in scope.get("headers", [])),
            )

        scope["user"] = user or scope.get("user") or AnonymousUser()
        return await super().__call__(scope, receive, send)

    def _extract_token(self, query_string_bytes: bytes) -> Optional[str]:
        try:
            query = urllib.parse.parse_qs(query_string_bytes.decode())
            vals = query.get("token")
            if vals:
                return vals[0]
        except Exception:
            pass
        return None

    def _extract_token_from_cookies(self, scope, name: str = 'access_token') -> Optional[str]:
        """Extract a token from the Cookie header in the ASGI scope.

        The scope headers are a list of (name, value) byte pairs.
        """
        try:
            headers = dict(scope.get('headers', []))
            cookie_bytes = headers.get(b'cookie')
            if not cookie_bytes:
                return None
            cookie_str = cookie_bytes.decode()
            for part in cookie_str.split(';'):
                k, _, v = part.strip().partition('=')
                if k == name:
                    return v
        except Exception:
            pass
        return None

    @database_sync_to_async
    def _get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()
