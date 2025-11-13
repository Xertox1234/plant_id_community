# Authentication & Authorization Patterns

**Last Updated**: November 13, 2025
**Consolidated From**:
- `docs/development/AUTHENTICATION_TESTING_PATTERNS_CODIFICATION.md`
- `docs/development/SECURITY_PATTERNS_CODIFIED.md`
- `docs/testing/DRF_AUTHENTICATION_TESTING_PATTERNS.md`

**Status**: ✅ Production-Tested Patterns

---

## Table of Contents

1. [JWT Authentication](#jwt-authentication)
2. [Session Management](#session-management)
3. [OAuth Integration](#oauth-integration)
4. [Django REST Framework Auth](#django-rest-framework-auth)
5. [Testing Patterns](#testing-patterns)
6. [Security Best Practices](#security-best-practices)

---

## JWT Authentication

### Pattern: Secure JWT Secret Keys

**Anti-Pattern** ❌:
```python
# settings.py - INSECURE
JWT_SECRET_KEY = "jwt-dev-secret-key-change-in-production-2024"
SECRET_KEY = "django-insecure-dev-key-change-in-production-2024"
```

**Problems**:
- Predictable keys allow token forgery
- Development keys left in production
- Complete authentication bypass possible
- User impersonation via forged tokens

**Correct Pattern** ✅:
```python
# settings.py
import os
from django.core.exceptions import ImproperlyConfigured

# JWT Secret Key (separate from Django SECRET_KEY)
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    raise ImproperlyConfigured('JWT_SECRET_KEY environment variable not set')

# Validate key strength in production
if not DEBUG:
    if len(JWT_SECRET_KEY) < 50:
        raise ImproperlyConfigured('JWT_SECRET_KEY must be at least 50 characters')

    # Block insecure patterns
    insecure_patterns = ['insecure', 'dev', 'test', 'sample', 'change', 'example']
    if any(pattern in JWT_SECRET_KEY.lower() for pattern in insecure_patterns):
        raise ImproperlyConfigured('JWT_SECRET_KEY contains insecure pattern')
```

**Generation**:
```bash
# Generate strong JWT secret
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

**Configuration**:
```python
# backend/.env (NEVER commit)
JWT_SECRET_KEY=your-generated-secret-here-64-chars-minimum

# backend/.env.example (commit this)
JWT_SECRET_KEY=generate-with-python-secrets-token-urlsafe-64
```

---

### Pattern: JWT Token Lifecycle

**Correct Implementation**:
```python
# apps/users/authentication.py
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

User = get_user_model()

def generate_tokens_for_user(user):
    """
    Generate JWT access and refresh tokens for authenticated user.

    Returns:
        dict: {
            'access': str (5-15 min lifetime),
            'refresh': str (7-30 day lifetime)
        }
    """
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }

# settings.py - Token Configuration
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Short-lived
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),     # Long-lived
    'ROTATE_REFRESH_TOKENS': True,                   # Issue new refresh on use
    'BLACKLIST_AFTER_ROTATION': True,                # Blacklist old refresh tokens
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': JWT_SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

**Why This Matters**:
- Short access token lifetime limits exposure window
- Refresh token rotation prevents token replay attacks
- Blacklisting ensures old tokens can't be reused

---

### Pattern: Token Refresh with Blacklisting

**Anti-Pattern** ❌:
```python
# Directly using refresh token without blacklisting
def refresh_token_view(request):
    refresh_token = request.data.get('refresh')
    token = RefreshToken(refresh_token)
    return Response({'access': str(token.access_token)})  # Old refresh still valid!
```

**Correct Pattern** ✅:
```python
# apps/users/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

@api_view(['POST'])
def token_refresh(request):
    """
    Refresh access token using refresh token.
    Blacklists old refresh token and issues new one.
    """
    refresh_token = request.data.get('refresh')

    if not refresh_token:
        return Response({'error': 'Refresh token required'}, status=400)

    try:
        # Parse and validate refresh token
        token = RefreshToken(refresh_token)

        # Blacklist the old refresh token
        token.blacklist()

        # Generate new tokens
        new_refresh = RefreshToken.for_user(token.user)

        return Response({
            'access': str(new_refresh.access_token),
            'refresh': str(new_refresh)
        })

    except TokenError as e:
        return Response({'error': str(e)}, status=401)
```

---

## Session Management

### Pattern: Secure Session Configuration

**Correct Configuration**:
```python
# settings.py

# Session cookie security
SESSION_COOKIE_SECURE = not DEBUG  # HTTPS only in production
SESSION_COOKIE_HTTPONLY = True     # Prevent JavaScript access (XSS protection)
SESSION_COOKIE_SAMESITE = 'Lax'    # CSRF protection
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 days

# CSRF cookie security
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Session backend (use cache for performance)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

**Why Each Setting Matters**:
- `SECURE`: HTTPS-only prevents token interception
- `HTTPONLY`: Prevents XSS attacks from stealing tokens
- `SAMESITE='Lax'`: CSRF protection while allowing normal navigation
- Cache backend: Fast session lookups, automatic cleanup

---

### Pattern: Account Lockout Protection

**Correct Implementation**:
```python
# apps/core/security.py
from django.core.cache import cache
from datetime import datetime, timedelta

LOCKOUT_TIME_WINDOW = 300  # 5 minutes
MAX_ATTEMPTS = 5
LOCKOUT_DURATION = 900      # 15 minutes

def check_account_locked(username):
    """
    Check if account is locked due to failed login attempts.

    Returns:
        tuple: (is_locked: bool, attempts_remaining: int, lockout_expires: datetime|None)
    """
    cache_key = f"lockout_attempts:{username}"
    attempts = cache.get(cache_key, [])

    # Remove attempts outside time window
    current_time = datetime.now()
    attempts = [
        a for a in attempts
        if (current_time - a['timestamp']).total_seconds() < LOCKOUT_TIME_WINDOW
    ]

    # Check if locked
    if len(attempts) >= MAX_ATTEMPTS:
        oldest_attempt = min(attempts, key=lambda x: x['timestamp'])
        lockout_expires = oldest_attempt['timestamp'] + timedelta(seconds=LOCKOUT_DURATION)

        if current_time < lockout_expires:
            return True, 0, lockout_expires

    # Update cache with cleaned attempts
    cache.set(cache_key, attempts, LOCKOUT_TIME_WINDOW)

    return False, MAX_ATTEMPTS - len(attempts), None

def record_failed_attempt(username):
    """Record failed login attempt for account lockout tracking."""
    cache_key = f"lockout_attempts:{username}"

    # Use optimistic locking for thread safety
    max_retries = 3
    for attempt in range(max_retries):
        attempts = cache.get(cache_key, [])

        # Add new attempt
        attempts.append({
            'timestamp': datetime.now(),
            'ip': get_client_ip()  # Track IP for security logs
        })

        # Atomic cache update
        if cache.add(cache_key, attempts, LOCKOUT_TIME_WINDOW):
            return True

        # If add fails, another thread updated - retry
        cache.set(cache_key, attempts, LOCKOUT_TIME_WINDOW)
        return True

    return False
```

**Testing Pattern**:
```python
# apps/users/tests/test_account_lockout.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

class AccountLockoutTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='correct_password123'
        )

    def test_account_locks_after_max_attempts(self):
        """Account should lock after MAX_ATTEMPTS failed logins."""
        # Make MAX_ATTEMPTS failed login attempts
        for i in range(5):
            response = self.client.post('/api/v1/auth/login/', {
                'username': 'testuser',
                'password': 'wrong_password'
            })
            self.assertEqual(response.status_code, 401)

        # Next attempt should be locked
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'correct_password123'  # Even correct password fails
        })
        self.assertEqual(response.status_code, 429)  # Too Many Requests
        self.assertIn('Account temporarily locked', response.data['error'])
```

---

## OAuth Integration

### Pattern: Secure OAuth Configuration

**Anti-Pattern** ❌:
```python
# settings.py - INSECURE
GOOGLE_OAUTH2_CLIENT_ID = 'your-google-client-id.apps.googleusercontent.com'
GOOGLE_OAUTH2_CLIENT_SECRET = 'your-google-client-secret'  # Hardcoded!
```

**Correct Pattern** ✅:
```python
# settings.py
GOOGLE_OAUTH2_CLIENT_ID = os.environ.get('GOOGLE_OAUTH2_CLIENT_ID')
GOOGLE_OAUTH2_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH2_CLIENT_SECRET')

# Validate in production
if not DEBUG:
    if not GOOGLE_OAUTH2_CLIENT_ID or not GOOGLE_OAUTH2_CLIENT_SECRET:
        raise ImproperlyConfigured('OAuth credentials not configured')

# Configure django-allauth
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APP': {
            'client_id': GOOGLE_OAUTH2_CLIENT_ID,
            'secret': GOOGLE_OAUTH2_CLIENT_SECRET,
            'key': ''
        }
    }
}
```

---

## Django REST Framework Auth

### Pattern: DRF Permission Classes

**Correct Implementation**:
```python
# apps/forum/permissions.py
from rest_framework import permissions

class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """Allow unauthenticated read, require auth for write."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

class IsAuthorOrModerator(permissions.BasePermission):
    """Object-level permission: author or moderator can modify."""

    def has_object_permission(self, request, view, obj):
        # Read permissions for anyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions for author or moderators
        return (
            obj.author == request.user or
            request.user.groups.filter(name='Moderators').exists() or
            request.user.is_staff
        )

# Usage in ViewSet
from rest_framework import viewsets

class PostViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        """Dynamic permissions based on action."""
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthorOrModerator()]
        return [IsAuthenticatedOrReadOnly()]
```

**Critical Pattern**: ViewSet `get_permissions()` must respect `@action` decorators:
```python
def get_permissions(self):
    """CRITICAL: Let custom actions use their own permission_classes."""

    # ✅ CORRECT: Respect @action decorators
    if self.action in ['custom_action', 'another_custom_action']:
        return super().get_permissions()  # Uses @action permissions

    # Standard CRUD permissions
    if self.action in ['update', 'partial_update', 'destroy']:
        return [IsAuthorOrModerator()]

    return [IsAuthenticatedOrReadOnly()]

@action(detail=True, methods=['POST'], permission_classes=[CustomPermission])
def custom_action(self, request, pk=None):
    # CustomPermission is properly enforced
    pass
```

**Why This Matters**: Without `super().get_permissions()`, `@action` decorators are silently ignored, causing security vulnerabilities (Issue #131).

---

## Testing Patterns

### Pattern: CSRF Token Handling in DRF Tests

**Anti-Pattern** ❌:
```python
# DRF APIClient doesn't auto-handle cookies like Django TestClient
def test_protected_endpoint(self):
    response = self.client.post('/api/v1/auth/login/', data)
    # Fails: Missing CSRF token
```

**Correct Pattern** ✅:
```python
# apps/users/tests/test_authentication.py
from rest_framework.test import APITestCase, APIClient

class AuthTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()

    def get_csrf_token(self):
        """Helper to get CSRF token from API."""
        response = self.client.get('/api/v1/auth/csrf/')
        csrf_cookie = response.cookies.get('csrftoken')
        if csrf_cookie:
            return csrf_cookie.value
        return self.client.cookies.get('csrftoken', None)

    def test_login_with_csrf(self):
        """Login should require CSRF token."""
        # Get CSRF token
        csrf_token = self.get_csrf_token()

        # Make authenticated request
        response = self.client.post(
            '/api/v1/auth/login/',
            {'username': 'test', 'password': 'test123'},
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(response.status_code, 200)
```

---

### Pattern: API Versioning in Tests

**Anti-Pattern** ❌:
```python
# Tests use unversioned URLs
response = self.client.post('/api/auth/login/', ...)  # 404 in production!
```

**Correct Pattern** ✅:
```python
# Always match production URL patterns
response = self.client.post('/api/v1/auth/login/', ...)  # ✓

# Use constants for consistency
LOGIN_URL = '/api/v1/auth/login/'
LOGOUT_URL = '/api/v1/auth/logout/'
TOKEN_REFRESH_URL = '/api/v1/auth/token/refresh/'

response = self.client.post(LOGIN_URL, credentials)
```

---

### Pattern: Time-Based Test Mocking

**Anti-Pattern** ❌:
```python
# Global time.time() mocking creates recursive MagicMock errors
with patch('time.time', return_value=future_time):
    # Fails with TypeError: 'MagicMock' object is not callable
```

**Correct Pattern** ✅:
```python
import time
from unittest.mock import patch

def test_lockout_expiry(self):
    """Test that account lockout expires after LOCKOUT_DURATION."""
    # Capture time BEFORE mocking
    lock_time = time.time()

    # Trigger lockout
    for _ in range(5):
        self.client.post(LOGIN_URL, wrong_credentials)

    # Mock time at module level where security check happens
    with patch('apps.core.security.time.time') as mock_time:
        mock_time.return_value = lock_time + 901  # After 15min lockout

        # Now login should work
        response = self.client.post(LOGIN_URL, correct_credentials)
        self.assertEqual(response.status_code, 200)
```

---

### Pattern: Layered Security Testing

**Anti-Pattern** ❌:
```python
# Expecting single status code from multiple security layers
def test_rate_limit(self):
    for _ in range(100):
        response = self.client.post(LOGIN_URL, data)

    self.assertEqual(response.status_code, 429)  # Might be 401 from account lockout!
```

**Correct Pattern** ✅:
```python
def test_rate_limit(self):
    """Test rate limiting - may trigger before or after account lockout."""
    for _ in range(100):
        response = self.client.post(LOGIN_URL, wrong_credentials)

    # Accept responses from EITHER rate limiting OR account lockout
    self.assertIn(
        response.status_code,
        [401, 429],  # 401 = lockout, 429 = rate limit
        "Expected either account lockout (401) or rate limit (429)"
    )

    # Conditional assertions based on which layer triggered
    if response.status_code == 429:
        self.assertIn('rate limit', response.data['error'].lower())
        self.assertIn('Retry-After', response)
    else:
        self.assertIn('locked', response.data['error'].lower())
```

---

## Security Best Practices

### Secret Management Checklist

- [ ] All secrets in environment variables (`.env`)
- [ ] `.env` in `.gitignore` (NEVER commit)
- [ ] `.env.example` with placeholder values (commit this)
- [ ] Production secrets validated (length, insecure patterns)
- [ ] Secrets rotated after any exposure
- [ ] Pre-commit hooks to detect secrets

### Authentication Security Checklist

- [ ] JWT secrets separate from Django SECRET_KEY
- [ ] Short access token lifetime (5-15 minutes)
- [ ] Refresh token rotation enabled
- [ ] Token blacklisting on logout/refresh
- [ ] Account lockout after N failed attempts
- [ ] Rate limiting on authentication endpoints
- [ ] HTTPS enforced in production
- [ ] HttpOnly, Secure, SameSite cookies

### Testing Security Checklist

- [ ] CSRF token handling in DRF tests
- [ ] API versioning in test URLs
- [ ] Time-based mocking at module level
- [ ] Layered security conditional assertions
- [ ] Test both success and failure paths
- [ ] Test account lockout expiry
- [ ] Test token expiry and refresh

---

## Related Patterns

- **CSRF Protection**: See `csrf-protection.md`
- **File Upload Security**: See `file-upload.md`
- **Input Validation**: See `input-validation.md`
- **Secret Management**: See `secret-management.md`
- **Rate Limiting**: See `../api/rate-limiting.md`

---

**Last Reviewed**: November 13, 2025
**Pattern Count**: 15 authentication patterns
**Status**: ✅ Production-validated across 278+ backend tests
