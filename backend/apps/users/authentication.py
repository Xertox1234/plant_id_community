"""
Secure authentication module with httpOnly cookie support for JWT tokens.
"""

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Literal, Optional, Tuple, cast

from apps.core.utils.pii_safe_logging import log_safe_user_context
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import AuthUser, JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken, Token

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    # The concrete class, so `User` is valid as an annotation (todo 580).
    from apps.users.models import User
else:
    User = get_user_model()

# Must match the v1 mount of apps.users.urls in plant_community_backend/urls.py —
# the browser only sends the refresh cookie to paths under this prefix. (The
# deprecated unversioned /api/auth/ mount no longer receives the cookie; clients
# there must send the token in the request body.)
REFRESH_COOKIE_PATH = "/api/v1/auth/"

# The values HttpResponse.set_cookie accepts for `samesite`.
SameSite = Optional[Literal["Lax", "Strict", "None", False]]


def _jwt_cookie_flags() -> Tuple[SameSite, bool]:
    """
    Return the (samesite, secure) pair for the JWT cookies.

    Mirrors the session cookie via SESSION_COOKIE_SAMESITE. Prod now serves
    the API same-site (api.houseplant-md.com, a subdomain of the frontend's
    own registrable domain) with SESSION_COOKIE_SAMESITE=Lax — Secure stays
    required regardless, since these cookies only ever travel over HTTPS in
    prod. Lax (not Strict) because the Google OAuth callback returns via a
    cross-site top-level GET redirect, which only Lax/None cookies survive.
    """
    # settings.py reads it from the environment as a plain str.
    samesite = cast(SameSite, settings.SESSION_COOKIE_SAMESITE)
    secure = not settings.DEBUG or str(samesite).lower() == "none"
    return samesite, secure


class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication using httpOnly cookies for enhanced security.
    Falls back to Authorization header if cookie is not present.
    """

    def authenticate(self, request: Request) -> Optional[Tuple[AuthUser, Token]]:
        """
        Authenticate using httpOnly cookie or Authorization header.

        Args:
            request: DRF request object

        Returns:
            Tuple of (User, Token) if authentication succeeds, None otherwise
        """
        # First try cookie-based authentication
        raw_token: str | bytes | None = self.get_raw_token_from_cookie(request)
        cookie_auth = raw_token is not None

        # Fall back to header-based authentication if no cookie
        if raw_token is None:
            header = self.get_header(request)
            if header is None:
                return None
            raw_token = self.get_raw_token(header)

        if raw_token is None:
            return None

        try:
            # CRITICAL SECURITY: Enforce CSRF FIRST for cookie-based auth
            # CSRF must be the first line of defense, not the second
            # Prevents timing attacks on token validation
            if cookie_auth:
                self.enforce_csrf(request)

            # Validate the token after CSRF check
            # simplejwt hints bytes, but decodes a str token the same way.
            validated_token = self.get_validated_token(raw_token)  # type: ignore[arg-type]

            # AuthUser is a constrained TypeVar (AbstractBaseUser or TokenUser) in an
            # unbound signature; mypy checks this line against TokenUser alone.
            return self.get_user(validated_token), validated_token  # type: ignore[return-value]
        except exceptions.AuthenticationFailed as e:
            # Log authentication failures for debugging
            logger.warning(f"[AUTH] JWT authentication failed: {str(e)}")
            # Return None to allow other authentication classes to try
            return None
        except exceptions.PermissionDenied as e:
            # CRITICAL SECURITY: CSRF failures MUST block the request
            # CSRF validation exists to prevent state-changing requests from malicious sites
            # Allowing fallback defeats the entire purpose of CSRF protection
            logger.error(f"[SECURITY] CSRF validation failed for cookie auth: {str(e)}")
            # Re-raise the exception - CSRF failures must block the request
            raise

    def get_raw_token_from_cookie(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from httpOnly cookie.

        Args:
            request: DRF request object

        Returns:
            JWT token string or None if not present
        """
        token: Optional[str] = request.COOKIES.get("access_token")
        return token

    def enforce_csrf(self, request: Request) -> None:
        """
        Enforce CSRF validation for cookie-based authentication.

        Args:
            request: DRF request object

        Raises:
            exceptions.PermissionDenied: If CSRF validation fails
        """
        # Skip CSRF for safe methods
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return

        def dummy_view(request: HttpRequest) -> HttpResponse:
            return HttpResponse()

        check = CSRFCheck(dummy_view)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")


def set_jwt_cookies(response: HttpResponse, user: User) -> HttpResponse:
    """
    Set JWT tokens as httpOnly cookies in the response.

    Args:
        response: Django HttpResponse object
        user: User instance to generate tokens for

    Returns:
        Modified response with JWT cookies set
    """
    refresh = RefreshToken.for_user(user)
    access_token = refresh.access_token

    # Calculate max age in seconds
    # SIMPLE_JWT is a mixed dict; both lifetimes are timedeltas in settings.py.
    # int() is what set_cookie does with a number anyway.
    access_lifetime = cast(timedelta, settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"])
    refresh_lifetime = cast(timedelta, settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"])
    access_max_age = int(access_lifetime.total_seconds())
    refresh_max_age = int(refresh_lifetime.total_seconds())

    samesite, secure = _jwt_cookie_flags()

    # Set httpOnly cookies
    # IMPORTANT: domain=None allows cookies to be sent from different ports on localhost
    # This enables frontend (localhost:5174) to send cookies to backend (localhost:8000)
    response.set_cookie(
        key="access_token",
        value=str(access_token),
        max_age=access_max_age,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=None,  # Default domain (allows cross-port in localhost)
        path="/",
    )

    response.set_cookie(
        key="refresh_token",
        value=str(refresh),
        max_age=refresh_max_age,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=None,  # Default domain (allows cross-port in localhost)
        path=REFRESH_COOKIE_PATH,  # Restrict refresh token to auth endpoints
    )

    logger.info(f"[AUTH] JWT cookies set for {log_safe_user_context(user)}")
    return response


def clear_jwt_cookies(response: HttpResponse) -> HttpResponse:
    """
    Clear JWT cookies from the response (for logout).

    Args:
        response: Django HttpResponse object

    Returns:
        Modified response with JWT cookies cleared
    """
    # samesite must match set_jwt_cookies: a cross-site response may only set
    # (and therefore expire) SameSite=None cookies, and delete_cookie derives
    # its Secure flag from samesite.
    samesite, _ = _jwt_cookie_flags()
    response.delete_cookie("access_token", path="/", samesite=samesite)
    response.delete_cookie("refresh_token", path=REFRESH_COOKIE_PATH, samesite=samesite)
    logger.info("[AUTH] JWT cookies cleared")
    return response


class RefreshTokenFromCookie:
    """
    Helper class to get refresh token from httpOnly cookie.
    """

    @staticmethod
    def get_refresh_token(request: Request) -> Optional[str]:
        """
        Extract refresh token from cookie or request data.

        Args:
            request: Django request object

        Returns:
            Refresh token string or None
        """
        # First try to get from cookie
        refresh_token: Optional[str] = request.COOKIES.get("refresh_token")

        # Fall back to request data (for backward compatibility)
        if not refresh_token:
            refresh_token = request.data.get("refresh")

        return refresh_token
