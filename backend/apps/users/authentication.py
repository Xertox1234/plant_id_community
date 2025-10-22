"""
Secure authentication module with httpOnly cookie support for JWT tokens.
"""
from django.conf import settings
from django.http import HttpResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.authentication import CSRFCheck
from rest_framework import exceptions
import logging

logger = logging.getLogger(__name__)


class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication using httpOnly cookies for enhanced security.
    Falls back to Authorization header if cookie is not present.
    """
    
    def authenticate(self, request):
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
            # Validate the token
            validated_token = self.get_validated_token(raw_token)
            
            # Enforce CSRF for cookie-based authentication ONLY after token validation
            if cookie_auth:
                self.enforce_csrf(request)
            
            return self.get_user(validated_token), validated_token
        except exceptions.AuthenticationFailed:
            # If token validation fails, return None instead of raising exception
            # This allows other authentication classes to try
            return None
        except exceptions.PermissionDenied:
            # If CSRF fails for cookie-based auth, return None
            # This allows the request to be processed as unauthenticated
            return None
    
    def get_raw_token_from_cookie(self, request):
        """
        Extract JWT token from httpOnly cookie.
        """
        return request.COOKIES.get('access_token')
    
    def enforce_csrf(self, request):
        """
        Enforce CSRF validation for cookie-based authentication.
        """
        # Skip CSRF for safe methods
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return
        
        def dummy_view(request):
            return HttpResponse()
        
        check = CSRFCheck(dummy_view)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f'CSRF Failed: {reason}')


def set_jwt_cookies(response, user):
    """
    Set JWT tokens as httpOnly cookies in the response.
    
    Args:
        response: Django HttpResponse object
        user: User instance to generate tokens for
    """
    refresh = RefreshToken.for_user(user)
    access_token = refresh.access_token
    
    # Calculate max age in seconds
    access_max_age = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
    refresh_max_age = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
    
    # Set httpOnly cookies
    response.set_cookie(
        key='access_token',
        value=str(access_token),
        max_age=access_max_age,
        httponly=True,
        secure=not settings.DEBUG,  # Use secure cookies in production
        samesite='Strict' if not settings.DEBUG else 'Lax',
        path='/'
    )
    
    response.set_cookie(
        key='refresh_token',
        value=str(refresh),
        max_age=refresh_max_age,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Strict' if not settings.DEBUG else 'Lax',
        path='/api/auth/'  # Restrict refresh token to auth endpoints
    )
    
    logger.info(f"JWT cookies set for user: {user.username}")
    return response


def clear_jwt_cookies(response):
    """
    Clear JWT cookies from the response (for logout).
    
    Args:
        response: Django HttpResponse object
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
    def get_refresh_token(request):
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