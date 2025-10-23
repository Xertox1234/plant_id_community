# Authentication Testing and Security Best Practices

**Comprehensive Research Summary for Django/DRF Authentication Systems**

**Research Date**: October 23, 2025
**Focus**: Django REST Framework JWT cookie-based authentication with comprehensive security controls

---

## Table of Contents

1. [Django/DRF Authentication Testing](#djangodrf-authentication-testing)
2. [Session Management Best Practices](#session-management-best-practices)
3. [Error Message Standardization](#error-message-standardization)
4. [Rate Limiting Best Practices](#rate-limiting-best-practices)
5. [Account Lockout Patterns](#account-lockout-patterns)
6. [Password Policy Best Practices](#password-policy-best-practices)
7. [Security Attack Prevention](#security-attack-prevention)
8. [Implementation Checklist](#implementation-checklist)

---

## Django/DRF Authentication Testing

### Recommended Library: Django REST Framework SimpleJWT

**Official Documentation**: https://django-rest-framework-simplejwt.readthedocs.io/

#### Core Testing Patterns

##### 1. Test Token Acquisition and Usage

```python
from rest_framework.test import APIClient
from django.contrib.auth.models import User

class AuthenticationTestCase(TestCase):
    def setUp(self):
        """Create test user - tests use separate database"""
        self.user = User.objects.create_user(
            username='testuser',
            password='TestPass123!'
        )
        self.client = APIClient()

    def test_token_acquisition(self):
        """Test obtaining JWT tokens"""
        response = self.client.post('/api/auth/token/', {
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_authenticated_request(self):
        """Test using access token for authenticated requests"""
        # Get token
        token_response = self.client.post('/api/auth/token/', {
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        access_token = token_response.data['access']

        # Use token (note: 'Bearer' not 'JWT')
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {access_token}'
        )
        response = self.client.get('/api/protected-endpoint/')
        self.assertEqual(response.status_code, 200)
```

##### 2. Test Token Refresh and Blacklisting

```python
from rest_framework_simplejwt.tokens import RefreshToken

class TokenBlacklistTestCase(TestCase):
    def test_token_refresh(self):
        """Test refresh token generates new access token"""
        # Get initial tokens
        refresh = RefreshToken.for_user(self.user)

        # Refresh to get new access token
        response = self.client.post('/api/auth/token/refresh/', {
            'refresh': str(refresh)
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)

    def test_token_blacklisting(self):
        """Test that blacklisted tokens cannot be reused"""
        # Get refresh token
        refresh = RefreshToken.for_user(self.user)

        # Blacklist the token (logout)
        refresh.blacklist()

        # Try to use blacklisted token
        response = self.client.post('/api/auth/token/refresh/', {
            'refresh': str(refresh)
        })
        self.assertEqual(response.status_code, 401)
        self.assertIn('blacklisted', str(response.data).lower())
```

**Configuration**: Add `'rest_framework_simplejwt.token_blacklist'` to `INSTALLED_APPS` and run migrations.

##### 3. Test Cookie-Based Authentication

```python
class CookieAuthTestCase(TestCase):
    def test_cookie_based_token_storage(self):
        """Test JWT tokens stored in HttpOnly cookies"""
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'TestPass123!'
        })

        # Verify cookies are set
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)

        # Verify HttpOnly flag
        access_cookie = response.cookies['access_token']
        self.assertTrue(access_cookie.get('httponly', False))

        # Verify Secure flag (HTTPS only)
        self.assertTrue(access_cookie.get('secure', False))

        # Verify SameSite
        self.assertEqual(access_cookie.get('samesite'), 'Strict')
```

##### 4. Test CSRF Protection with Cookie Authentication

```python
from django.test import Client

class CSRFTestCase(TestCase):
    def test_csrf_required_for_authenticated_requests(self):
        """Test CSRF validation when using cookie authentication"""
        # Login user (establishes session)
        self.client.login(username='testuser', password='TestPass123!')

        # POST without CSRF token should fail
        client_no_csrf = Client(enforce_csrf_checks=True)
        client_no_csrf.login(username='testuser', password='TestPass123!')
        response = client_no_csrf.post('/api/some-action/')
        self.assertEqual(response.status_code, 403)

    def test_csrf_token_flow(self):
        """Test proper CSRF token acquisition and usage"""
        # Get CSRF token
        response = self.client.get('/api/csrf-token/')
        csrf_token = response.cookies['csrftoken'].value

        # Use CSRF token in POST request
        response = self.client.post(
            '/api/some-action/',
            data={'key': 'value'},
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(response.status_code, 200)
```

**Important**: Django REST Framework disables CSRF for unauthenticated requests when using SessionAuthentication. Always verify CSRF is enforced for logged-in users.

##### 5. Test Rate Limiting

```python
from django.test import override_settings
from unittest.mock import patch

class RateLimitTestCase(TestCase):
    def test_login_rate_limiting(self):
        """Test rate limiting prevents brute force attacks"""
        # Attempt 6 failed logins (exceeds 5/min limit)
        for i in range(6):
            response = self.client.post('/api/auth/login/', {
                'username': 'testuser',
                'password': 'WrongPassword'
            })

        # 6th attempt should be rate limited
        self.assertEqual(response.status_code, 429)
        self.assertIn('rate limit', str(response.data).lower())

    @override_settings(RATELIMIT_ENABLE=False)
    def test_without_rate_limiting(self):
        """Disable rate limiting for non-auth tests"""
        # Test application logic without rate limit interference
        response = self.client.get('/api/some-endpoint/')
        self.assertEqual(response.status_code, 200)
```

##### 6. Test IP Spoofing Protection

```python
class IPSpoofingTestCase(TestCase):
    def test_rate_limiting_by_ip(self):
        """Test rate limiting considers IP address"""
        # Make requests from different IPs
        for i in range(3):
            response = self.client.post(
                '/api/auth/login/',
                {'username': 'test', 'password': 'wrong'},
                REMOTE_ADDR=f'192.168.1.{i}'
            )
            # Each IP should be tracked separately
            self.assertNotEqual(response.status_code, 429)

    def test_x_forwarded_for_header(self):
        """Test X-Forwarded-For header handling"""
        response = self.client.get(
            '/api/some-endpoint/',
            HTTP_X_FORWARDED_FOR='8.8.8.8'
        )
        # Verify backend extracts correct IP
        # (implementation depends on django-ipware or similar)
```

**Security Note**: X-Forwarded-For headers are user-supplied and can be spoofed. Always validate at your first server/load balancer level.

### Best Practices Summary

#### MUST HAVE
- ✅ Use `djangorestframework-simplejwt` for JWT authentication
- ✅ Enable token blacklisting for logout functionality
- ✅ Store tokens in HttpOnly, Secure, SameSite cookies (not localStorage)
- ✅ Always use HTTPS in production (HTTP → HTTPS redirect)
- ✅ Test with `enforce_csrf_checks=True` for cookie auth
- ✅ Mock authentication for unit tests, use real auth for integration tests
- ✅ Keep JWT payload minimal (user ID, roles only)

#### RECOMMENDED
- 🔶 Use `force_authenticate()` for testing non-auth functionality
- 🔶 Test token verification endpoint separately
- 🔶 Mock Redis for rate limiting tests (use `fakeredis`)
- 🔶 Test both successful and failed authentication paths
- 🔶 Verify proper token expiration behavior

#### TESTING TOOLS
- **DRF APIClient**: For most API tests
- **DRF RequestFactory**: For view-level testing with CSRF enforcement
- **fakeredis**: For mocking Redis in tests
- **django-fakeredis**: Decorators for Redis mocking
- **override_settings**: For disabling rate limiting in non-auth tests

---

## Session Management Best Practices

### Token Lifetime Recommendations (Industry Standards)

#### Access Token (JWT) Duration

| Application Type | Access Token | Refresh Token | Inactivity Timeout | Absolute Timeout |
|-----------------|-------------|---------------|-------------------|------------------|
| **Consumer Apps** | 1 hour | 30 days | 5 days | 30 days |
| **High-Security Apps** | 5 minutes | 24 hours | 30 minutes | 24 hours |
| **Mobile Apps** | 1 hour | 180 days | None (UX) | 180 days |
| **Standard (Recommended)** | 15-60 minutes | 7-30 days | 2 hours | 7 days |

**Sources**:
- 1Password Passage: https://passage.1password.com/post/better-session-management-with-refresh-tokens
- Supabase Session Docs: https://supabase.com/docs/guides/auth/sessions
- ZITADEL Auth Guide: https://zitadel.com/blog/session-timeouts-logouts

#### Key Principles

**Short-Lived Access Tokens**:
- Typical range: 5 minutes to 1 hour
- Most applications: **15 minutes default**
- Prevents unauthorized use if token stolen
- Requires backend verification without contacting auth service

**Long-Lived Refresh Tokens**:
- Typical range: 7 days to 180 days
- Consumer apps: **30 days**
- Allows token refresh without re-login
- Must be stored securely (database, not just signed JWT)

**Refresh Token Rotation (MUST IMPLEMENT)**:
```python
# Every time refresh token is used, issue NEW refresh token
# and invalidate the old one

def refresh_token_view(request):
    old_refresh = request.data['refresh']

    # Verify and decode old refresh token
    token = RefreshToken(old_refresh)

    # Generate new access + refresh tokens
    new_refresh = token.rotate()  # Built-in SimpleJWT method

    return Response({
        'access': str(token.access_token),
        'refresh': str(new_refresh)
    })
```

**Why Rotation?**: Prevents replay attacks where attacker gains access to original refresh token. If old token is reused after rotation, it indicates compromise.

### Multi-Device Session Management

#### Pattern 1: Centralized Session Storage (Recommended)

**Use Case**: Track all active sessions per user across devices.

```python
# models.py
from django.db import models
from django.contrib.auth.models import User
import uuid

class UserSession(models.Model):
    """Track active sessions across devices"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    refresh_token_jti = models.CharField(max_length=255, unique=True)
    device_name = models.CharField(max_length=255, blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['refresh_token_jti']),
        ]
```

**Benefits**:
- View all active sessions
- Logout from specific device
- Logout from all devices
- Detect session hijacking
- Enforce device limits

#### Pattern 2: Global Logout (All Devices)

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_all_devices(request):
    """Logout user from all devices by blacklisting all refresh tokens"""
    # Get all outstanding tokens for user
    tokens = OutstandingToken.objects.filter(user=request.user)

    # Blacklist all refresh tokens
    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)

    return Response({
        'detail': f'Logged out from {tokens.count()} devices'
    })
```

#### Pattern 3: Device Limit Enforcement

```python
from django.conf import settings

def enforce_device_limit(user, new_session):
    """Limit user to N concurrent sessions"""
    max_sessions = getattr(settings, 'MAX_SESSIONS_PER_USER', 5)

    # Get active sessions, ordered by last activity
    active_sessions = UserSession.objects.filter(
        user=user,
        is_active=True
    ).order_by('-last_activity')

    # If at limit, deactivate oldest session
    if active_sessions.count() >= max_sessions:
        oldest_session = active_sessions.last()
        oldest_session.is_active = False
        oldest_session.save()

        # Blacklist associated refresh token
        token = OutstandingToken.objects.get(
            jti=oldest_session.refresh_token_jti
        )
        BlacklistedToken.objects.get_or_create(token=token)

    # Save new session
    new_session.save()
```

### Inactivity Timeout Implementation

**Challenge**: JWTs are stateless - you can't track "last activity" without backend storage.

**Solution**: Hybrid approach with session tracking.

```python
# middleware.py
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

class InactivityTimeoutMiddleware:
    """Track last activity and enforce inactivity timeout"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = timedelta(minutes=getattr(
            settings, 'INACTIVITY_TIMEOUT_MINUTES', 30
        ))

    def __call__(self, request):
        if request.user.is_authenticated:
            # Get JWT token JTI
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                try:
                    decoded = jwt.decode(
                        token,
                        settings.SECRET_KEY,
                        algorithms=['HS256']
                    )
                    jti = decoded.get('jti')

                    # Update session last activity
                    session = UserSession.objects.filter(
                        refresh_token_jti=jti,
                        is_active=True
                    ).first()

                    if session:
                        # Check if inactive too long
                        inactive_duration = timezone.now() - session.last_activity
                        if inactive_duration > self.timeout:
                            # Invalidate session
                            session.is_active = False
                            session.save()

                            return JsonResponse({
                                'detail': 'Session expired due to inactivity'
                            }, status=401)

                        # Update last activity
                        session.last_activity = timezone.now()
                        session.save(update_fields=['last_activity'])

                except jwt.InvalidTokenError:
                    pass

        return self.get_response(request)
```

### "Remember Me" Functionality

**Security Pattern**: Two-token system with theft detection.

#### Configuration

```python
# settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),  # Default
    'REMEMBER_ME_REFRESH_TOKEN_LIFETIME': timedelta(days=30),  # Extended
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}
```

#### Implementation

```python
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta

@api_view(['POST'])
def login_with_remember_me(request):
    """Login with optional 'remember me' functionality"""
    username = request.data.get('username')
    password = request.data.get('password')
    remember_me = request.data.get('remember_me', False)

    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': 'Invalid credentials'}, status=401)

    # Generate tokens
    refresh = RefreshToken.for_user(user)

    # Extend refresh token lifetime if remember_me
    if remember_me:
        refresh.set_exp(lifetime=timedelta(days=30))

    # Create session record
    session = UserSession.objects.create(
        user=user,
        refresh_token_jti=str(refresh['jti']),
        device_fingerprint=get_device_fingerprint(request),
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )

    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'remember_me': remember_me
    })
```

**Security Measures**:
1. ✅ Tokens are random (16+ bytes from secure source)
2. ✅ Store hash of token, not plaintext
3. ✅ Send token in HttpOnly, Secure cookie (HTTPS only)
4. ✅ Detect theft: If series ID exists but token doesn't match, assume compromise
5. ✅ On password change, invalidate all remember-me tokens
6. ✅ Allow user to view and revoke remembered sessions

**Source**: Troy Hunt's "How to build a secure remember me feature" - https://www.troyhunt.com/how-to-build-and-how-not-to-build/

### Session Invalidation Triggers

**MUST invalidate sessions when**:
- ✅ User explicitly logs out
- ✅ Password changed
- ✅ Email changed (for email-based recovery)
- ✅ Suspicious activity detected
- ✅ User requests "logout all devices"
- ✅ Account disabled/deleted

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

@receiver(post_save, sender=User)
def invalidate_sessions_on_password_change(sender, instance, **kwargs):
    """Invalidate all sessions when password changes"""
    if instance.password_changed:  # Custom flag
        # Blacklist all refresh tokens
        tokens = OutstandingToken.objects.filter(user=instance)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        # Deactivate all sessions
        UserSession.objects.filter(user=instance).update(is_active=False)
```

---

## Error Message Standardization

### RFC 7807 (Obsoleted by RFC 9457): Problem Details for HTTP APIs

**Official Spec**: https://tools.ietf.org/html/rfc7807 (now RFC 9457)

RFC 7807/9457 defines a standard JSON structure for HTTP API errors to provide consistent, machine-readable error responses.

#### Standard Structure

```json
{
  "type": "https://api.example.com/errors/authentication-failed",
  "title": "Authentication Failed",
  "status": 401,
  "detail": "The provided credentials are invalid. Please check your username and password.",
  "instance": "/api/v1/auth/login",
  "timestamp": "2025-10-23T14:32:15Z",
  "errors": [
    {
      "field": "password",
      "code": "invalid",
      "message": "Password does not match our records"
    }
  ]
}
```

**Content-Type**: `application/problem+json` or `application/problem+xml`

#### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | URI | URL to documentation about this error type |
| `title` | string | Short, human-readable summary (generic across occurrences) |
| `status` | integer | HTTP status code |
| `detail` | string | Human-readable explanation specific to this occurrence |
| `instance` | URI | URI identifying this specific error occurrence |

#### Optional Extensions

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | When error occurred (for log correlation) |
| `errors` | array | Field-level validation errors |
| `trace_id` | string | Distributed tracing identifier |
| `help_url` | URI | Link to support/documentation |

### Django/DRF Implementation

#### Custom Exception Handler

```python
# exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.utils import timezone

def problem_details_exception_handler(exc, context):
    """RFC 7807 compliant exception handler"""
    # Call DRF's default handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Convert to RFC 7807 format
        problem_details = {
            'type': get_error_type_url(exc),
            'title': get_error_title(response.status_code),
            'status': response.status_code,
            'detail': get_safe_detail(exc, response.status_code),
            'instance': context['request'].path,
            'timestamp': timezone.now().isoformat(),
        }

        # Add field errors if present
        if hasattr(exc, 'get_full_details'):
            field_errors = extract_field_errors(exc.get_full_details())
            if field_errors:
                problem_details['errors'] = field_errors

        response.data = problem_details
        response['Content-Type'] = 'application/problem+json'

    return response

def get_safe_detail(exc, status_code):
    """Return security-safe error detail message"""
    # Authentication errors - prevent username enumeration
    if status_code == 401:
        return "Authentication failed. Please check your credentials."

    # Permission errors
    if status_code == 403:
        return "You do not have permission to perform this action."

    # Validation errors - safe to be specific
    if status_code == 400:
        if hasattr(exc, 'detail'):
            return str(exc.detail)
        return "The request was invalid."

    # Server errors - never expose internals
    if status_code >= 500:
        return "An internal server error occurred. Please try again later."

    return str(exc.detail) if hasattr(exc, 'detail') else "An error occurred."

# settings.py
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'myapp.exceptions.problem_details_exception_handler',
}
```

### Security-Safe Error Messages

#### Prevent Information Leakage

**DON'T expose**:
- ❌ Stack traces in production
- ❌ Database query errors
- ❌ File paths or internal structure
- ❌ Library/framework versions
- ❌ Whether username exists (enumeration)
- ❌ Specific validation failure on password

**DO provide**:
- ✅ Generic error messages for auth failures
- ✅ HTTP status codes
- ✅ Field-level validation errors (safe details only)
- ✅ Actionable guidance for client
- ✅ Error codes for programmatic handling

#### Authentication Error Examples

```python
# BAD - Reveals which part is wrong
{
    "error": "User 'john@example.com' not found"  # ❌ Username enumeration
}
{
    "error": "Password incorrect for user 'john@example.com'"  # ❌ Confirms username
}

# GOOD - Generic message
{
    "type": "https://api.example.com/errors/authentication-failed",
    "title": "Authentication Failed",
    "status": 401,
    "detail": "The username or password is incorrect.",  # ✅ Doesn't reveal which
    "instance": "/api/v1/auth/login"
}
```

#### Validation Error Examples

```python
# Safe field-level errors for user input
{
    "type": "https://api.example.com/errors/validation-failed",
    "title": "Validation Failed",
    "status": 400,
    "detail": "The request contains invalid data.",
    "instance": "/api/v1/users/",
    "errors": [
        {
            "field": "email",
            "code": "invalid_format",
            "message": "Enter a valid email address."  # ✅ Safe
        },
        {
            "field": "password",
            "code": "too_short",
            "message": "Password must be at least 15 characters."  # ✅ Safe
        }
    ]
}
```

#### Server Error Example

```python
# Production error - hide details, log internally
{
    "type": "https://api.example.com/errors/internal-server-error",
    "title": "Internal Server Error",
    "status": 500,
    "detail": "An unexpected error occurred. Please try again later.",
    "instance": "/api/v1/plants/identify/",
    "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"  # For support lookup
}

# Internally logged (never sent to client):
# [ERROR] trace_id=a1b2c3d4 TypeError: 'NoneType' object is not subscriptable
#   File "/app/services/plant_id_service.py", line 142, in identify_plant
#     result = response.json()['suggestions'][0]
```

#### Rate Limit Error Example

```python
{
    "type": "https://api.example.com/errors/rate-limit-exceeded",
    "title": "Rate Limit Exceeded",
    "status": 429,
    "detail": "Too many login attempts. Please try again in 5 minutes.",
    "instance": "/api/v1/auth/login",
    "retry_after": 300,  # seconds
    "limit": 5,
    "window": 300
}
```

### Error Logging Strategy

**Client Response** (generic) vs **Server Logs** (detailed):

```python
import logging
logger = logging.getLogger(__name__)

def safe_error_response(exc, context):
    """Return safe error to client, log full details server-side"""
    request = context['request']

    # Log full error details server-side
    logger.error(
        f"[ERROR] {exc.__class__.__name__}: {str(exc)}",
        extra={
            'user': request.user.id if request.user.is_authenticated else None,
            'path': request.path,
            'method': request.method,
            'ip': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        },
        exc_info=True  # Include full traceback
    )

    # Return generic error to client
    return Response({
        'type': 'https://api.example.com/errors/internal-server-error',
        'title': 'Internal Server Error',
        'status': 500,
        'detail': 'An unexpected error occurred. Our team has been notified.',
        'instance': request.path,
    }, status=500)
```

**Benefits**:
- ✅ Clients get actionable, safe messages
- ✅ Developers get full debugging info in logs
- ✅ No sensitive information leaked
- ✅ Consistent error format across API

---

## Rate Limiting Best Practices

### OWASP Recommendations

**Source**: OWASP API Security Top 10 2023 - API4: Unrestricted Resource Consumption
**URL**: https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/

#### Authentication Endpoint Rate Limits

| Endpoint | Requests | Window | Scope | Rationale |
|----------|----------|--------|-------|-----------|
| **Login** | 5 | 5 minutes | IP + Username | Prevent brute force |
| **Password Reset** | 3 | 15 minutes | Email | Prevent enumeration |
| **Registration** | 10 | 1 hour | IP | Prevent spam accounts |
| **Token Refresh** | 20 | 5 minutes | User | Normal usage buffer |
| **2FA Verify** | 5 | 5 minutes | Session | Prevent code guessing |

**OWASP Guideline**: "Credential recovery/forgot password endpoints should be treated as login endpoints in terms of brute force, rate limiting, and lockout protections."

### Multi-Dimensional Rate Limiting (Recommended)

Rate limit on **multiple dimensions** to prevent bypass:

1. **Per IP**: Prevent single attacker from brute forcing
2. **Per Username**: Prevent distributed attack on one account
3. **Per Account**: Prevent account takeover after credential leak
4. **Global**: Prevent DoS against authentication service

#### Example Configuration

```python
# settings.py
RATELIMIT_ENABLE = True

# Login endpoint: Multi-dimensional limits
LOGIN_RATE_LIMITS = {
    'per_ip': '5/5m',        # 5 attempts per 5 minutes per IP
    'per_username': '5/5m',  # 5 attempts per 5 minutes per username
    'global': '1000/1h',     # Max 1000 login attempts/hour across system
}

# Password reset: More restrictive
PASSWORD_RESET_RATE_LIMITS = {
    'per_ip': '3/15m',
    'per_email': '3/1h',  # Prevent enumeration via password reset
}
```

### Django Implementation with Redis

#### Using django-ratelimit

```python
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

@ratelimit(key='ip', rate='5/5m', method='POST', block=True)
@ratelimit(key='post:username', rate='5/5m', method='POST', block=True)
def login_view(request):
    """Login with IP + username rate limiting"""
    username = request.POST.get('username')
    password = request.POST.get('password')

    user = authenticate(username=username, password=password)
    if user:
        # Generate tokens, create session, etc.
        pass
    else:
        return Response({
            'type': 'https://api.example.com/errors/authentication-failed',
            'title': 'Authentication Failed',
            'status': 401,
            'detail': 'Invalid credentials. Please try again.',
        }, status=401)
```

**Configuration**:
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Use Redis for rate limiting
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = True  # Set to False in tests
```

### Exponential Backoff Pattern

**Goal**: Progressively increase delay after failed attempts to slow down attacks without permanent lockout.

#### Server-Side Implementation

```python
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone

def get_backoff_delay(identifier, max_attempts=5):
    """Calculate exponential backoff delay

    Attempt 1: 0 seconds
    Attempt 2: 2 seconds  (2^1)
    Attempt 3: 4 seconds  (2^2)
    Attempt 4: 8 seconds  (2^3)
    Attempt 5: 16 seconds (2^4)
    Attempt 6+: 30 seconds (capped)
    """
    cache_key = f'auth_attempts:{identifier}'
    attempts = cache.get(cache_key, 0)

    if attempts == 0:
        return 0

    # Exponential backoff: 2^(attempts-1), capped at 30 seconds
    delay = min(2 ** (attempts - 1), 30)

    # Add jitter (randomness) to prevent synchronized retries
    jitter = random.uniform(0, delay * 0.1)  # ±10% jitter

    return delay + jitter

def check_backoff(identifier):
    """Check if user must wait before next attempt"""
    cache_key = f'auth_backoff:{identifier}'
    next_allowed = cache.get(cache_key)

    if next_allowed:
        now = timezone.now()
        if now < next_allowed:
            wait_seconds = (next_allowed - now).total_seconds()
            return False, wait_seconds

    return True, 0

@api_view(['POST'])
def login_with_backoff(request):
    """Login with exponential backoff"""
    username = request.data.get('username')
    identifier = f"{get_client_ip(request)}:{username}"

    # Check if user must wait
    allowed, wait_seconds = check_backoff(identifier)
    if not allowed:
        return Response({
            'type': 'https://api.example.com/errors/rate-limit-exceeded',
            'title': 'Too Many Attempts',
            'status': 429,
            'detail': f'Too many failed attempts. Please wait {int(wait_seconds)} seconds.',
            'retry_after': int(wait_seconds)
        }, status=429)

    # Attempt authentication
    user = authenticate(
        username=username,
        password=request.data.get('password')
    )

    if user:
        # Success - clear backoff
        cache.delete(f'auth_attempts:{identifier}')
        cache.delete(f'auth_backoff:{identifier}')
        # ... generate tokens, etc.
    else:
        # Failed - increment attempts and set backoff
        attempts_key = f'auth_attempts:{identifier}'
        attempts = cache.get(attempts_key, 0) + 1
        cache.set(attempts_key, attempts, timeout=300)  # 5 minutes

        # Calculate and set next allowed time
        delay = get_backoff_delay(identifier, attempts)
        next_allowed = timezone.now() + timedelta(seconds=delay)
        cache.set(f'auth_backoff:{identifier}', next_allowed, timeout=int(delay) + 60)

        return Response({
            'type': 'https://api.example.com/errors/authentication-failed',
            'title': 'Authentication Failed',
            'status': 401,
            'detail': 'Invalid credentials.',
            'retry_after': int(delay) if delay > 0 else None
        }, status=401)
```

**Benefits**:
- ✅ Slows down automated attacks exponentially
- ✅ No permanent lockout (self-heals after timeout)
- ✅ Jitter prevents thundering herd
- ✅ Legitimate users wait minimal time after 1-2 mistakes

### Rate Limit Monitoring

```python
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def log_rate_limit_hit(func):
    """Decorator to log rate limit hits for monitoring"""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except Ratelimited as e:
            logger.warning(
                f"[RATE_LIMIT] Rate limit exceeded",
                extra={
                    'path': request.path,
                    'ip': get_client_ip(request),
                    'user': request.user.id if request.user.is_authenticated else None,
                    'limit': e.limit,
                    'window': e.window,
                }
            )
            raise
    return wrapper
```

**Alerting Strategy**:
- Track rate limit hits in metrics (Prometheus, CloudWatch, etc.)
- Alert if:
  - Single IP hits rate limit > 50 times/hour (automated attack)
  - Global rate limit hits increase > 300% (DDoS attempt)
  - Specific username targeted > 100 times (credential stuffing)

---

## Account Lockout Patterns

### Industry Standards Comparison

| Standard | Threshold | Lockout Duration | Reset Counter | Notes |
|----------|-----------|------------------|---------------|-------|
| **PCI DSS** | 6 attempts | 30 minutes | After lockout | Payment card industry |
| **NIST SP 800-63B** | 100 attempts | N/A | N/A | Prefers throttling over lockout |
| **Windows Security Baseline** | 10 attempts | 15-30 minutes | 15-60 minutes | Enterprise default |
| **OWASP** | 5 attempts | 15-30 minutes | 15 minutes | Web application standard |
| **Recommended (High Security)** | 5 attempts | 30 minutes | 15 minutes | Balance security + UX |
| **Recommended (Standard)** | 10 attempts | 15 minutes | 30 minutes | More user-friendly |

**Sources**:
- PCI DSS: https://blog.rsisecurity.com/creating-a-pci-dss-account-lockout-policy/
- NIST: https://csf.tools/reference/nist-sp-800-53/r5/ac/ac-7/
- OWASP: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html

### Recommended Configuration

```python
# settings.py
ACCOUNT_LOCKOUT = {
    'ENABLED': True,
    'MAX_ATTEMPTS': 5,              # Failed login attempts before lockout
    'LOCKOUT_DURATION': 30 * 60,    # 30 minutes (seconds)
    'RESET_COUNTER_AFTER': 15 * 60, # Reset counter after 15 minutes of no attempts
    'NOTIFY_USER': True,            # Send email on lockout
    'NOTIFY_ADMINS': True,          # Alert admins on repeated lockouts
}
```

### Implementation

```python
# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class AccountLockout(models.Model):
    """Track failed login attempts and account lockouts"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    failed_attempts = models.IntegerField(default=0)
    last_failed_attempt = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    lockout_count = models.IntegerField(default=0)  # Historical count

    class Meta:
        indexes = [
            models.Index(fields=['locked_until']),
        ]

    def is_locked(self):
        """Check if account is currently locked"""
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False

    def record_failed_attempt(self):
        """Record a failed login attempt"""
        from django.conf import settings
        config = settings.ACCOUNT_LOCKOUT

        # Reset counter if last attempt was too long ago
        if self.last_failed_attempt:
            time_since_last = timezone.now() - self.last_failed_attempt
            if time_since_last.total_seconds() > config['RESET_COUNTER_AFTER']:
                self.failed_attempts = 0

        # Increment attempts
        self.failed_attempts += 1
        self.last_failed_attempt = timezone.now()

        # Check if should lock account
        if self.failed_attempts >= config['MAX_ATTEMPTS']:
            self.lock_account()

        self.save()

    def lock_account(self):
        """Lock the account"""
        from django.conf import settings
        config = settings.ACCOUNT_LOCKOUT

        self.locked_until = timezone.now() + timedelta(
            seconds=config['LOCKOUT_DURATION']
        )
        self.lockout_count += 1
        self.failed_attempts = 0  # Reset counter

        # Notify user
        if config['NOTIFY_USER']:
            self.send_lockout_notification()

        self.save()

    def unlock_account(self):
        """Manually unlock account (admin action)"""
        self.locked_until = None
        self.failed_attempts = 0
        self.save()

    def send_lockout_notification(self):
        """Send email notification about account lockout"""
        from django.core.mail import send_mail
        from django.conf import settings

        send_mail(
            subject='Account Locked - Suspicious Activity Detected',
            message=f"""
            Your account has been temporarily locked due to multiple failed login attempts.

            - Locked until: {self.locked_until.strftime('%Y-%m-%d %H:%M:%S %Z')}
            - Lockout count: {self.lockout_count}

            If this wasn't you, please reset your password immediately.
            If you believe this is an error, contact support.
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.user.email],
            fail_silently=True,
        )

# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import authenticate

@api_view(['POST'])
def login_with_lockout(request):
    """Login with account lockout protection"""
    username = request.data.get('username')
    password = request.data.get('password')

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # Still do timing-safe password check to prevent enumeration
        authenticate(username='nonexistent', password=password)
        return Response({
            'type': 'https://api.example.com/errors/authentication-failed',
            'title': 'Authentication Failed',
            'status': 401,
            'detail': 'Invalid credentials.',
        }, status=401)

    # Check if account is locked
    lockout, _ = AccountLockout.objects.get_or_create(user=user)
    if lockout.is_locked():
        time_remaining = (lockout.locked_until - timezone.now()).total_seconds()
        return Response({
            'type': 'https://api.example.com/errors/account-locked',
            'title': 'Account Locked',
            'status': 403,
            'detail': f'Account is temporarily locked. Try again in {int(time_remaining / 60)} minutes.',
            'locked_until': lockout.locked_until.isoformat(),
        }, status=403)

    # Attempt authentication
    authenticated_user = authenticate(username=username, password=password)

    if authenticated_user:
        # Success - reset lockout counter
        lockout.failed_attempts = 0
        lockout.last_failed_attempt = None
        lockout.save()

        # Generate tokens, create session, etc.
        # ...

    else:
        # Failed - record attempt (may trigger lockout)
        lockout.record_failed_attempt()

        # Check if just locked
        if lockout.is_locked():
            return Response({
                'type': 'https://api.example.com/errors/account-locked',
                'title': 'Account Locked',
                'status': 403,
                'detail': 'Too many failed login attempts. Account locked for 30 minutes.',
                'locked_until': lockout.locked_until.isoformat(),
            }, status=403)

        # Still have attempts remaining
        attempts_remaining = settings.ACCOUNT_LOCKOUT['MAX_ATTEMPTS'] - lockout.failed_attempts
        return Response({
            'type': 'https://api.example.com/errors/authentication-failed',
            'title': 'Authentication Failed',
            'status': 401,
            'detail': f'Invalid credentials. {attempts_remaining} attempts remaining.',
        }, status=401)
```

### Account Unlock Mechanisms

#### 1. Time-Based Unlock (Automatic)

```python
# Middleware to auto-unlock expired lockouts
class AutoUnlockMiddleware:
    """Automatically unlock accounts when lockout period expires"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                lockout = AccountLockout.objects.get(user=request.user)
                if lockout.locked_until and timezone.now() >= lockout.locked_until:
                    lockout.unlock_account()
            except AccountLockout.DoesNotExist:
                pass

        return self.get_response(request)
```

#### 2. Admin Unlock (Manual)

```python
# admin.py
from django.contrib import admin
from .models import AccountLockout

@admin.register(AccountLockout)
class AccountLockoutAdmin(admin.ModelAdmin):
    list_display = ['user', 'failed_attempts', 'locked_until', 'lockout_count']
    list_filter = ['locked_until']
    search_fields = ['user__username', 'user__email']
    actions = ['unlock_accounts']

    def unlock_accounts(self, request, queryset):
        """Admin action to unlock selected accounts"""
        count = 0
        for lockout in queryset:
            lockout.unlock_account()
            count += 1
        self.message_user(request, f'Unlocked {count} accounts.')
    unlock_accounts.short_description = "Unlock selected accounts"
```

#### 3. Email Verification Unlock

```python
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature

def send_unlock_email(user):
    """Send email with unlock link"""
    signer = TimestampSigner()
    token = signer.sign(user.username)
    unlock_url = f"https://example.com/unlock-account/{token}/"

    send_mail(
        subject='Unlock Your Account',
        message=f"""
        Your account has been locked due to multiple failed login attempts.

        Click here to unlock your account:
        {unlock_url}

        This link expires in 1 hour.
        """,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )

@api_view(['POST'])
def unlock_account_via_email(request, token):
    """Unlock account using emailed token"""
    signer = TimestampSigner()
    try:
        # Verify token (max_age=1 hour)
        username = signer.unsign(token, max_age=3600)
        user = User.objects.get(username=username)
        lockout = AccountLockout.objects.get(user=user)
        lockout.unlock_account()

        return Response({
            'detail': 'Account unlocked successfully. You may now log in.'
        })
    except (SignatureExpired, BadSignature, User.DoesNotExist):
        return Response({
            'error': 'Invalid or expired unlock link.'
        }, status=400)
```

### Lockout vs. Throttling Trade-offs

| Approach | Pros | Cons | When to Use |
|----------|------|------|-------------|
| **Account Lockout** | Strong protection against targeted attacks | Can be weaponized (DoS via lockout) | High-value accounts, admin panels |
| **Rate Limiting** | No DoS risk, graceful degradation | Doesn't stop slow brute force | Public APIs, general authentication |
| **Exponential Backoff** | Self-healing, progressive slowdown | Complex to implement correctly | Modern web apps, mobile apps |
| **CAPTCHA After N Attempts** | Distinguishes humans from bots | UX friction, accessibility issues | Medium-security scenarios |

**Recommended Hybrid**:
1. Rate limiting (5/5min per IP + username)
2. Exponential backoff (2^n seconds after failures)
3. Account lockout after 10 attempts (extreme cases)
4. CAPTCHA after 3 failed attempts (optional)

---

## Password Policy Best Practices

### NIST SP 800-63B (2024 Update) - Official Guidelines

**Source**: NIST Special Publication 800-63B (September 2024 draft)
**URL**: https://pages.nist.gov/800-63-4/sp800-63b.html

#### Key NIST Recommendations (2024)

##### 1. **Password Length Over Complexity** ✅

| Requirement | NIST Guideline |
|-------------|----------------|
| **Minimum Length** | 8 characters (MUST) |
| **Recommended Minimum** | 15 characters |
| **Maximum Length** | At least 64 characters (MUST support) |
| **Passphrases** | Spaces and Unicode allowed (encourage) |

**Rationale**: Longer passwords are exponentially harder to crack than complex short passwords. "P@ssw0rd1" (10 chars, complex) is weaker than "correct horse battery staple" (28 chars, simple).

##### 2. **Eliminate Composition Rules** ❌ PROHIBITED

**DON'T require**:
- ❌ "Must contain uppercase letter"
- ❌ "Must contain number"
- ❌ "Must contain special character"
- ❌ "Must not contain dictionary words"

**Rationale**: Composition rules lead to predictable patterns (e.g., "Password1!", "Summer2025!"). Users choose marginally compliant passwords rather than strong ones.

##### 3. **No Mandatory Password Expiration** ❌ PROHIBITED

**NIST 2024**: "Scheduled, mandatory password rotation is prohibited."

**Change passwords ONLY when**:
- ✅ Evidence of compromise detected
- ✅ User forgets password
- ✅ User voluntarily changes password
- ✅ Account shows suspicious activity

**Rationale**: Forced rotation encourages weak passwords (Password1, Password2, etc.) and provides minimal security benefit.

##### 4. **Compromised Credential Screening** ✅ REQUIRED

**MUST check passwords against**:
- Commonly used passwords (top 10,000+)
- Passwords from known breaches (HaveIBeenPwned)
- Context-specific passwords (e.g., "CompanyName2025")

**Implementation**: Use HaveIBeenPwned API (k-anonymity model) or maintain local blocklist.

##### 5. **Character Set Support** ✅ REQUIRED

**MUST allow**:
- All printable ASCII characters (including space)
- Unicode characters (emojis, non-Latin scripts)
- Consecutive spaces

**DON'T allow**:
- Leading/trailing spaces (trim automatically)
- Control characters (e.g., null bytes)

##### 6. **Eliminate Security Questions** ❌ PROHIBITED

**NIST 2024**: "Using and storing password hints or security questions is prohibited."

**Rationale**: Answers are easily obtained via social engineering or public information (mother's maiden name, high school mascot).

##### 7. **Password Manager Support** ✅ ENCOURAGED

**MUST support**:
- Paste functionality (don't block)
- Autofill from password managers
- Very long passwords (64+ characters)

**Rationale**: Password managers generate strong, unique passwords. Blocking them reduces security.

### Django/DRF Implementation

#### Custom Password Validator

```python
# validators.py
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import requests
import hashlib

class NIST2024PasswordValidator:
    """
    NIST SP 800-63B compliant password validator (2024 guidelines)

    Requirements:
    - Minimum 8 characters (15 recommended)
    - Maximum 64+ characters
    - No composition requirements
    - Check against compromised passwords (HaveIBeenPwned)
    - Allow all printable ASCII + Unicode
    """

    def __init__(
        self,
        min_length=15,  # NIST recommends 15+
        max_length=128,
        check_breached=True,
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.check_breached = check_breached

    def validate(self, password, user=None):
        """Validate password against NIST 2024 guidelines"""
        # Length check
        if len(password) < self.min_length:
            raise ValidationError(
                _(f"Password must be at least {self.min_length} characters long."),
                code='password_too_short',
            )

        if len(password) > self.max_length:
            raise ValidationError(
                _(f"Password cannot exceed {self.max_length} characters."),
                code='password_too_long',
            )

        # Check against compromised passwords
        if self.check_breached:
            if self.is_password_breached(password):
                raise ValidationError(
                    _("This password has appeared in a data breach. Please choose a different password."),
                    code='password_breached',
                )

        # Check for common passwords (Django's built-in validator handles this)
        # No composition requirements (removed intentionally)

    def is_password_breached(self, password):
        """Check password against HaveIBeenPwned using k-anonymity"""
        # Hash password with SHA-1
        sha1 = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]

        try:
            # Query HaveIBeenPwned API (k-anonymity: only send first 5 chars)
            response = requests.get(
                f'https://api.pwnedpasswords.com/range/{prefix}',
                timeout=2
            )

            # Check if full hash appears in results
            if response.status_code == 200:
                hashes = (line.split(':') for line in response.text.splitlines())
                for hash_suffix, count in hashes:
                    if hash_suffix == suffix:
                        return True  # Password found in breach

            return False

        except requests.RequestException:
            # If API fails, don't block user (fail open for availability)
            logger.warning("HaveIBeenPwned API unavailable, skipping breach check")
            return False

    def get_help_text(self):
        return _(
            f"Your password must be at least {self.min_length} characters long "
            "and not appear in known data breaches. Use a passphrase or "
            "password manager for best security."
        )


class ContextSpecificPasswordValidator:
    """Prevent passwords containing user-specific information"""

    def validate(self, password, user=None):
        if user:
            # Check against username
            if user.username.lower() in password.lower():
                raise ValidationError(
                    _("Password cannot contain your username."),
                    code='password_contains_username',
                )

            # Check against email
            if user.email:
                email_parts = user.email.lower().split('@')
                for part in email_parts:
                    if len(part) > 3 and part in password.lower():
                        raise ValidationError(
                            _("Password cannot contain parts of your email address."),
                            code='password_contains_email',
                        )

            # Check against first/last name
            if user.first_name and len(user.first_name) > 2:
                if user.first_name.lower() in password.lower():
                    raise ValidationError(
                        _("Password cannot contain your name."),
                        code='password_contains_name',
                    )

    def get_help_text(self):
        return _("Password cannot contain your personal information.")
```

#### Settings Configuration

```python
# settings.py
AUTH_PASSWORD_VALIDATORS = [
    {
        # NIST 2024 compliant validator
        'NAME': 'myapp.validators.NIST2024PasswordValidator',
        'OPTIONS': {
            'min_length': 15,  # Recommended minimum
            'max_length': 128,
            'check_breached': True,  # HaveIBeenPwned check
        }
    },
    {
        # Prevent common passwords (Django built-in)
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        # Context-specific validation
        'NAME': 'myapp.validators.ContextSpecificPasswordValidator',
    },
    # NOTE: UserAttributeSimilarityValidator and NumericPasswordValidator
    # are NOT included per NIST 2024 (no composition requirements)
]

# Allow long passwords (NIST requires 64+ support)
PASSWORD_MAX_LENGTH = 128

# Password managers should be supported
PASSWORD_ALLOW_PASTE = True  # Ensure frontend doesn't block paste
```

### Alternative: zxcvbn-based Strength Estimation

**Library**: `django-zxcvbn-password-validator`
**Approach**: Estimate password strength (entropy) rather than enforce rules.

```python
# Installation
# pip install django-zxcvbn-password-validator

# settings.py
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django_zxcvbn_password_validator.ZxcvbnPasswordValidator',
        'OPTIONS': {
            'min_score': 3,  # Score 0-4 (3 = strong, 4 = very strong)
            'user_attributes': ['username', 'email', 'first_name', 'last_name']
        }
    },
]
```

**Benefits**:
- ✅ Realistic strength estimation (considers patterns, not just rules)
- ✅ User-friendly feedback ("Add another word or two")
- ✅ No arbitrary composition requirements
- ✅ Considers user context automatically

**zxcvbn Scores**:
- 0: Too guessable (risky password)
- 1: Very guessable (protection from throttled online attacks)
- 2: Somewhat guessable (protection from unthrottled online attacks)
- 3: Safely unguessable (moderate protection from offline attacks)
- 4: Very unguessable (strong protection from offline attacks)

### Password Validation API Endpoint

```python
# views.py
from django.contrib.auth.password_validation import validate_password
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['POST'])
def check_password_strength(request):
    """Real-time password strength checking for frontend"""
    password = request.data.get('password', '')
    user = request.user if request.user.is_authenticated else None

    try:
        # Run Django's password validators
        validate_password(password, user=user)

        # If using zxcvbn, get score
        if 'zxcvbn' in [v['NAME'] for v in settings.AUTH_PASSWORD_VALIDATORS]:
            from zxcvbn import zxcvbn
            result = zxcvbn(password, user_inputs=[
                user.username if user else '',
                user.email if user else '',
            ])

            return Response({
                'valid': True,
                'score': result['score'],  # 0-4
                'feedback': result['feedback'],
                'crack_times': result['crack_times_display'],
            })

        return Response({'valid': True})

    except ValidationError as e:
        return Response({
            'valid': False,
            'errors': e.messages,
        }, status=400)
```

**Frontend Integration**:
```javascript
// Real-time password strength indicator
async function checkPassword(password) {
    const response = await fetch('/api/auth/check-password/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({password})
    });

    const data = await response.json();
    if (data.valid) {
        showStrengthMeter(data.score);  // 0-4 scale
        showFeedback(data.feedback);
    } else {
        showErrors(data.errors);
    }
}
```

---

## Security Attack Prevention

### Timing Attack Prevention

**Vulnerability**: Attackers measure response times to determine if username exists.

**Example**:
- Valid username + wrong password: 150ms (database lookup + bcrypt)
- Invalid username: 2ms (no database lookup)

#### Constant-Time Authentication

```python
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User

def timing_safe_authenticate(username, password):
    """Authenticate with constant-time protection"""
    try:
        user = User.objects.get(username=username)
        # Always perform password check (even if locked)
        password_valid = check_password(password, user.password)
    except User.DoesNotExist:
        # Perform dummy password check to match timing of valid user
        check_password(password, 'pbkdf2_sha256$260000$dummy$placeholder')
        password_valid = False
        user = None

    # All code paths take approximately same time
    if user and password_valid:
        # Additional checks (lockout, etc.) go here
        return user

    return None
```

**Why it works**: `check_password()` with dummy hash takes ~same time as real check. Attacker can't distinguish valid vs invalid username by timing.

#### Adding Random Delay (Defense in Depth)

```python
import random
import time

def add_random_delay():
    """Add 300-700ms random delay to mask timing differences"""
    delay = random.uniform(0.3, 0.7)
    time.sleep(delay)

@api_view(['POST'])
def timing_safe_login(request):
    """Login with timing attack protection"""
    add_random_delay()  # First layer

    username = request.data.get('username')
    password = request.data.get('password')

    user = timing_safe_authenticate(username, password)  # Second layer

    if user:
        # Success
        pass
    else:
        # Failure - same response for invalid user or wrong password
        return Response({
            'type': 'https://api.example.com/errors/authentication-failed',
            'title': 'Authentication Failed',
            'status': 401,
            'detail': 'Invalid credentials.',  # Generic message
        }, status=401)
```

### Username Enumeration Prevention

**Vulnerability**: Attacker determines which usernames exist via different responses.

#### Vulnerable Code (DON'T DO THIS)

```python
# ❌ BAD - Reveals username existence
if not User.objects.filter(username=username).exists():
    return Response({'error': 'Username does not exist'}, status=404)

# ❌ BAD - Reveals username existence via password reset
if User.objects.filter(email=email).exists():
    send_reset_email(email)
    return Response({'message': 'Reset email sent'})
else:
    return Response({'error': 'Email not found'}, status=404)
```

#### Secure Implementation

```python
# ✅ GOOD - Same response regardless of username existence
@api_view(['POST'])
def password_reset_request(request):
    """Password reset with enumeration protection"""
    email = request.data.get('email')

    # ALWAYS return success, regardless of whether email exists
    # Send email asynchronously (background job)
    send_password_reset_email.delay(email)  # Celery task

    return Response({
        'detail': 'If that email address is in our system, we sent a password reset link.'
    })

# Asynchronous task (celery)
@shared_task
def send_password_reset_email(email):
    """Send password reset email if user exists"""
    try:
        user = User.objects.get(email=email)
        # Generate token, send email
        # ...
    except User.DoesNotExist:
        # Silently do nothing (don't reveal non-existence)
        pass
```

**Benefits**:
- ✅ Asynchronous processing removes timing differences
- ✅ Same response whether email exists or not
- ✅ Rate limiting on endpoint prevents mass enumeration

### CAPTCHA Integration (After N Failed Attempts)

**Pattern**: Show CAPTCHA after 3 failed login attempts to distinguish humans from bots.

```python
from django.core.cache import cache
import requests

def requires_captcha(identifier):
    """Check if CAPTCHA is required for this identifier"""
    attempts_key = f'login_attempts:{identifier}'
    attempts = cache.get(attempts_key, 0)
    return attempts >= 3  # Require after 3 failures

def verify_recaptcha(token):
    """Verify reCAPTCHA v3 token"""
    response = requests.post(
        'https://www.google.com/recaptcha/api/siteverify',
        data={
            'secret': settings.RECAPTCHA_SECRET_KEY,
            'response': token,
        },
        timeout=5
    )

    result = response.json()
    return result.get('success') and result.get('score', 0) >= 0.5

@api_view(['POST'])
def login_with_captcha(request):
    """Login with CAPTCHA requirement after failures"""
    username = request.data.get('username')
    password = request.data.get('password')
    recaptcha_token = request.data.get('recaptcha_token')

    identifier = f"{get_client_ip(request)}:{username}"

    # Check if CAPTCHA required
    if requires_captcha(identifier):
        if not recaptcha_token:
            return Response({
                'error': 'CAPTCHA required',
                'captcha_required': True,
            }, status=403)

        if not verify_recaptcha(recaptcha_token):
            return Response({
                'error': 'Invalid CAPTCHA',
                'captcha_required': True,
            }, status=403)

    # Proceed with authentication
    user = authenticate(username=username, password=password)

    if user:
        # Success - reset attempts
        cache.delete(f'login_attempts:{identifier}')
        # ...
    else:
        # Failure - increment attempts
        attempts = cache.get(f'login_attempts:{identifier}', 0) + 1
        cache.set(f'login_attempts:{identifier}', attempts, timeout=900)  # 15 min

        captcha_required = attempts >= 3
        return Response({
            'error': 'Invalid credentials',
            'captcha_required': captcha_required,
        }, status=401)
```

### Device Fingerprinting

**Purpose**: Identify suspicious logins from new devices.

```python
import hashlib
import json

def get_device_fingerprint(request):
    """Generate device fingerprint from request metadata"""
    components = [
        request.META.get('HTTP_USER_AGENT', ''),
        request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
        request.META.get('HTTP_ACCEPT_ENCODING', ''),
        # Don't include IP (changes frequently on mobile)
    ]

    fingerprint_string = '|'.join(components)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]

class LoginAttempt(models.Model):
    """Track login attempts with device fingerprinting"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    device_fingerprint = models.CharField(max_length=16)
    success = models.BooleanField()
    new_device = models.BooleanField(default=False)

def is_new_device(user, fingerprint):
    """Check if device has been used before"""
    return not LoginAttempt.objects.filter(
        user=user,
        device_fingerprint=fingerprint,
        success=True
    ).exists()

@api_view(['POST'])
def login_with_device_tracking(request):
    """Login with new device detection"""
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)
    fingerprint = get_device_fingerprint(request)

    if user:
        new_device = is_new_device(user, fingerprint)

        # Log attempt
        LoginAttempt.objects.create(
            user=user,
            ip_address=get_client_ip(request),
            device_fingerprint=fingerprint,
            success=True,
            new_device=new_device
        )

        # Alert user if new device
        if new_device:
            send_new_device_alert.delay(user.id, request.META.get('HTTP_USER_AGENT'))

        # Generate tokens...
        return Response({
            'access': 'token...',
            'new_device_detected': new_device
        })
    else:
        # Log failed attempt
        LoginAttempt.objects.create(
            user=User.objects.filter(username=username).first(),
            ip_address=get_client_ip(request),
            device_fingerprint=fingerprint,
            success=False
        )

        return Response({'error': 'Invalid credentials'}, status=401)
```

---

## Implementation Checklist

### Phase 1: Core Authentication (Week 1)

- [ ] Install and configure `djangorestframework-simplejwt`
- [ ] Enable token blacklist app (`rest_framework_simplejwt.token_blacklist`)
- [ ] Configure token lifetimes (15min access, 7 days refresh)
- [ ] Implement token refresh with rotation
- [ ] Store tokens in HttpOnly, Secure, SameSite=Strict cookies
- [ ] Set up CSRF protection for cookie-based auth
- [ ] Create login, logout, refresh endpoints
- [ ] Write unit tests for token acquisition, refresh, blacklisting

### Phase 2: Rate Limiting & Lockout (Week 2)

- [ ] Install Redis for distributed rate limiting
- [ ] Configure `django-ratelimit` with Redis backend
- [ ] Implement multi-dimensional rate limiting (IP + username)
- [ ] Add exponential backoff for failed attempts
- [ ] Create `AccountLockout` model and logic
- [ ] Configure lockout thresholds (5 attempts, 30min lockout)
- [ ] Implement lockout notification emails
- [ ] Add admin interface for manual unlock
- [ ] Test rate limiting with `fakeredis`
- [ ] Test lockout scenarios

### Phase 3: Password Security (Week 3)

- [ ] Implement NIST 2024 compliant password validator
- [ ] Integrate HaveIBeenPwned API for breach checking
- [ ] Remove composition requirements (no forced uppercase/numbers)
- [ ] Set minimum password length to 15 characters
- [ ] Support passphrases with spaces and Unicode
- [ ] Disable mandatory password expiration
- [ ] Create password strength check endpoint for frontend
- [ ] Update frontend with real-time password strength indicator

### Phase 4: Attack Prevention (Week 4)

- [ ] Implement constant-time authentication
- [ ] Add random delays (300-700ms) to login endpoint
- [ ] Use generic error messages (prevent enumeration)
- [ ] Make password reset asynchronous
- [ ] Add CAPTCHA requirement after 3 failed attempts
- [ ] Implement device fingerprinting
- [ ] Set up new device detection and alerts
- [ ] Create IP-based security monitoring

### Phase 5: Session Management (Week 5)

- [ ] Create `UserSession` model for multi-device tracking
- [ ] Implement "logout from all devices" functionality
- [ ] Add device limit enforcement (max 5 concurrent sessions)
- [ ] Build session management UI (view active sessions)
- [ ] Implement "remember me" with extended refresh token
- [ ] Add inactivity timeout middleware
- [ ] Invalidate sessions on password change
- [ ] Create session activity log

### Phase 6: Error Handling (Week 6)

- [ ] Implement RFC 7807 exception handler
- [ ] Standardize error response format (type, title, status, detail, instance)
- [ ] Use `application/problem+json` content type
- [ ] Add field-level error details for validation
- [ ] Implement trace IDs for error correlation
- [ ] Set up structured logging (JSON format)
- [ ] Configure error alerting (500 errors, rate limit hits)
- [ ] Review all error messages for information leakage

### Phase 7: Testing & Documentation (Week 7)

- [ ] Write comprehensive test suite (100+ test cases)
- [ ] Test all authentication flows (login, refresh, logout)
- [ ] Test CSRF enforcement for cookie auth
- [ ] Test rate limiting across dimensions
- [ ] Test account lockout and unlock mechanisms
- [ ] Test timing attack protection
- [ ] Test username enumeration prevention
- [ ] Load test authentication endpoints (100 req/sec)
- [ ] Document all security features
- [ ] Create API documentation (OpenAPI/Swagger)

### Phase 8: Monitoring & Production (Week 8)

- [ ] Set up metrics collection (Prometheus/CloudWatch)
- [ ] Create dashboards for:
  - [ ] Login success/failure rates
  - [ ] Rate limit hits
  - [ ] Account lockouts
  - [ ] New device detections
  - [ ] Password strength distribution
- [ ] Configure alerting:
  - [ ] Spike in failed logins (>300%)
  - [ ] High rate limit hits (>100/hour)
  - [ ] Multiple account lockouts from same IP
- [ ] Set up log aggregation (ELK/Splunk)
- [ ] Create runbook for security incidents
- [ ] Perform security audit (OWASP checklist)
- [ ] Penetration testing (brute force, enumeration)
- [ ] Deploy to production with feature flags

---

## Testing Best Practices Summary

### Test Categories

#### 1. **Unit Tests** (Test individual components)

```python
# Test password validation
def test_nist_password_validator_min_length():
    validator = NIST2024PasswordValidator(min_length=15)
    with pytest.raises(ValidationError):
        validator.validate('short')

# Test token generation
def test_refresh_token_rotation():
    refresh = RefreshToken.for_user(user)
    old_jti = refresh['jti']
    new_refresh = refresh.rotate()
    assert new_refresh['jti'] != old_jti
```

#### 2. **Integration Tests** (Test API endpoints)

```python
def test_login_with_valid_credentials(api_client):
    response = api_client.post('/api/auth/login/', {
        'username': 'testuser',
        'password': 'ValidPassword123'
    })
    assert response.status_code == 200
    assert 'access' in response.cookies
    assert response.cookies['access']['httponly']
```

#### 3. **Security Tests** (Test attack scenarios)

```python
def test_rate_limiting_prevents_brute_force(api_client):
    """Test that rate limiting blocks brute force attacks"""
    for i in range(6):
        response = api_client.post('/api/auth/login/', {
            'username': 'target_user',
            'password': f'wrong_password_{i}'
        })

    assert response.status_code == 429  # Too Many Requests
    assert 'rate limit' in response.data['detail'].lower()

def test_timing_attack_resistance(api_client):
    """Test that valid and invalid usernames take similar time"""
    import time

    # Time valid username
    start = time.time()
    api_client.post('/api/auth/login/', {
        'username': 'existing_user',
        'password': 'wrong_password'
    })
    valid_duration = time.time() - start

    # Time invalid username
    start = time.time()
    api_client.post('/api/auth/login/', {
        'username': 'nonexistent_user_xyz',
        'password': 'wrong_password'
    })
    invalid_duration = time.time() - start

    # Times should be within 100ms of each other
    assert abs(valid_duration - invalid_duration) < 0.1
```

#### 4. **Load Tests** (Test performance)

```python
# Using locust for load testing
from locust import HttpUser, task, between

class AuthenticationUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def login(self):
        self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123'
        })

    @task(3)  # 3x weight (more common)
    def refresh_token(self):
        self.client.post('/api/auth/token/refresh/', {
            'refresh': self.refresh_token
        })
```

### Testing Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **pytest** | Unit/integration tests | All test types |
| **pytest-django** | Django integration | Testing Django apps |
| **factory_boy** | Test data generation | Creating realistic test users |
| **fakeredis** | Mock Redis | Testing rate limiting/caching |
| **freezegun** | Mock datetime | Testing token expiration |
| **responses** | Mock HTTP requests | Testing HaveIBeenPwned API |
| **locust** | Load testing | Performance validation |
| **django.test.override_settings** | Config changes | Testing different configurations |

---

## Additional Resources

### Official Documentation

- **Django REST Framework**: https://www.django-rest-framework.org/
- **SimpleJWT**: https://django-rest-framework-simplejwt.readthedocs.io/
- **NIST SP 800-63B**: https://pages.nist.gov/800-63-4/sp800-63b.html
- **RFC 7807 (9457)**: https://tools.ietf.org/html/rfc7807
- **OWASP API Security**: https://owasp.org/API-Security/

### Security Standards

- **OWASP Authentication Cheat Sheet**: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- **OWASP Session Management**: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- **PCI DSS Requirements**: https://www.pcisecuritystandards.org/

### Third-Party Services

- **HaveIBeenPwned API**: https://haveibeenpwned.com/API/v3
- **reCAPTCHA v3**: https://developers.google.com/recaptcha/docs/v3

### Libraries

- **djangorestframework-simplejwt**: JWT authentication
- **django-ratelimit**: Rate limiting
- **django-ipware**: IP address extraction
- **zxcvbn-python**: Password strength estimation
- **django-zxcvbn-password-validator**: Django integration

### Articles & Guides

- **Troy Hunt - Secure "Remember Me"**: https://www.troyhunt.com/how-to-build-and-how-not-to-build/
- **1Password Passage - Refresh Tokens**: https://passage.1password.com/post/better-session-management-with-refresh-tokens

---

**Document Version**: 1.0
**Last Updated**: October 23, 2025
**Maintainer**: Development Team
**Review Schedule**: Quarterly (next review: January 2026)
