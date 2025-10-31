"""
Secure authentication module with httpOnly cookie support for JWT tokens.
"""
from typing import Optional, Tuple
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken, Token
from rest_framework.authentication import CSRFCheck
from rest_framework import exceptions
from apps.core.utils.pii_safe_logging import log_safe_user_context
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication using httpOnly cookies for enhanced security.
    Falls back to Authorization header if cookie is not present.
    """
    
    def authenticate(self, request: Request) -> Optional[Tuple[User, Token]]:
        """
        Authenticate using httpOnly cookie or Authorization header.

        Args:
            request: DRF request object

        Returns:
            Tuple of (User, Token) if authentication succeeds, None otherwise
        """
        # First try cookie-based authentication
        raw_token = self.get_raw_token_from_cookie(request)
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
            validated_token = self.get_validated_token(raw_token)

            return self.get_user(validated_token), validated_token
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
        return request.COOKIES.get('access_token')

    def enforce_csrf(self, request: Request) -> None:
        """
        Enforce CSRF validation for cookie-based authentication.

        Args:
            request: DRF request object

        Raises:
            exceptions.PermissionDenied: If CSRF validation fails
        """
        # Skip CSRF for safe methods
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return

        def dummy_view(request: HttpRequest) -> HttpResponse:
            return HttpResponse()

        check = CSRFCheck(dummy_view)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f'CSRF Failed: {reason}')


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
    access_max_age = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
    refresh_max_age = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
    
    # Set httpOnly cookies
    # IMPORTANT: domain=None allows cookies to be sent from different ports on localhost
    # This enables frontend (localhost:5174) to send cookies to backend (localhost:8000)
    response.set_cookie(
        key='access_token',
        value=str(access_token),
        max_age=access_max_age,
        httponly=True,
        secure=not settings.DEBUG,  # Use secure cookies in production
        samesite='Strict' if not settings.DEBUG else 'Lax',
        domain=None,  # Default domain (allows cross-port in localhost)
        path='/'
    )

    response.set_cookie(
        key='refresh_token',
        value=str(refresh),
        max_age=refresh_max_age,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Strict' if not settings.DEBUG else 'Lax',
        domain=None,  # Default domain (allows cross-port in localhost)
        path='/api/auth/'  # Restrict refresh token to auth endpoints
    )
    
    logger.info(f"JWT cookies set for {log_safe_user_context(user)}")
    return response


def clear_jwt_cookies(response: HttpResponse) -> HttpResponse:
    """
    Clear JWT cookies from the response (for logout).

    Args:
        response: Django HttpResponse object

    Returns:
        Modified response with JWT cookies cleared
    """
    response.delete_cookie('access_token', path='/')
    response.delete_cookie('refresh_token', path='/api/auth/')
    logger.info("JWT cookies cleared")
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
        refresh_token = request.COOKIES.get('refresh_token')
        
        # Fall back to request data (for backward compatibility)
        if not refresh_token:
            refresh_token = request.data.get('refresh')
        
        return refresh_token