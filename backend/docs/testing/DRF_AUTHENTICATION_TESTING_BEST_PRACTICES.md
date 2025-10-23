# Django REST Framework Authentication Testing: Best Practices Guide

**Comprehensive Research Summary**
**Date:** October 23, 2025
**Status:** Authoritative Reference
**Version:** 1.0

---

## Table of Contents

1. [DRF APIClient vs Django TestClient](#drf-apiclient-vs-django-testclient)
2. [Testing Layered Security](#testing-layered-security)
3. [Time-Based Testing in Django](#time-based-testing-in-django)
4. [API Versioning in Tests](#api-versioning-in-tests)
5. [DRF Authentication Testing Patterns](#drf-authentication-testing-patterns)
6. [pytest-django Integration](#pytest-django-integration)
7. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
8. [Real-World Examples](#real-world-examples)

---

## DRF APIClient vs Django TestClient

### Official Guidance

**Source:** [Django REST Framework Testing Documentation](https://www.django-rest-framework.org/api-guide/testing/)

### Key Differences

| Feature | Django TestClient | DRF APIClient |
|---------|------------------|---------------|
| **Purpose** | General Django views | REST API endpoints |
| **Authentication** | `login()` method only | `credentials()`, `force_authenticate()`, `login()` |
| **Headers** | Manual HTTP_* setting | `credentials()` helper |
| **Default Format** | Form data | Configurable (JSON default) |
| **CSRF** | Always enforced (if enabled) | Optional via `enforce_csrf_checks=True` |
| **Session Support** | Yes | Yes |
| **Token Support** | Manual headers | Built-in `credentials()` |

### When to Use Each

**Use APIClient when:**
- Testing DRF viewsets and API views
- Need token-based authentication
- Testing JSON APIs
- Want simplified authentication setup
- Need to bypass authentication for specific tests

**Use Django TestClient when:**
- Testing Django template views
- Testing form submissions
- Need exact production CSRF behavior
- Testing mixed Django/DRF applications

### Basic APIClient Usage

```python
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

class BasicAPITests(TestCase):
    """Basic APIClient usage patterns."""

    def setUp(self):
        """Set up test client and user."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

    # Method 1: Session Authentication
    def test_session_login(self):
        """Use session-based authentication."""
        # Login via session
        self.client.login(username='testuser', password='TestPassword123!')

        response = self.client.get('/api/v1/protected/')
        self.assertEqual(response.status_code, 200)

        # Logout
        self.client.logout()

    # Method 2: Token Authentication
    def test_token_authentication(self):
        """Use token-based authentication."""
        from rest_framework.authtoken.models import Token

        # Create token
        token = Token.objects.create(user=self.user)

        # Set credentials for all subsequent requests
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get('/api/v1/protected/')
        self.assertEqual(response.status_code, 200)

        # Clear credentials
        self.client.credentials()

    # Method 3: Force Authentication (Bypass credentials)
    def test_force_authenticate(self):
        """Bypass authentication mechanism entirely."""
        # Force authenticate as user
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/v1/protected/')
        self.assertEqual(response.status_code, 200)

        # Unauthenticate
        self.client.force_authenticate(user=None)
```

### Cookie Handling Differences

**Critical Difference:** APIClient and TestClient handle cookies differently in CSRF scenarios.

```python
class CookieHandlingTests(TestCase):
    """Cookie and CSRF handling patterns."""

    def test_csrf_with_session_auth(self):
        """CSRF validation with SessionAuthentication."""
        # APIClient: CSRF disabled by default
        client_no_csrf = APIClient()
        client_no_csrf.login(username='testuser', password='TestPassword123!')

        response = client_no_csrf.post('/api/v1/data/', {'key': 'value'})
        self.assertEqual(response.status_code, 200)  # CSRF not enforced

        # APIClient: CSRF enabled
        client_with_csrf = APIClient(enforce_csrf_checks=True)
        client_with_csrf.login(username='testuser', password='TestPassword123!')

        response = client_with_csrf.post('/api/v1/data/', {'key': 'value'})
        self.assertEqual(response.status_code, 403)  # CSRF required

    def test_csrf_token_extraction(self):
        """Extract and use CSRF token in tests."""
        from django.middleware.csrf import get_token
        from django.test import RequestFactory

        client = APIClient(enforce_csrf_checks=True)
        client.login(username='testuser', password='TestPassword123!')

        # Get CSRF token
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.user
        csrf_token = get_token(request)

        # Include in request
        response = client.post(
            '/api/v1/data/',
            {'key': 'value'},
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(response.status_code, 200)
```

### Session Management in Tests

```python
class SessionManagementTests(TestCase):
    """Session-based authentication patterns."""

    def test_session_persistence(self):
        """Test that session persists across requests."""
        client = APIClient()

        # Login creates session
        login_response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })

        # Session cookie automatically included in subsequent requests
        response = client.get('/api/v1/user/profile/')
        self.assertEqual(response.status_code, 200)

        # Verify session data
        self.assertIn('_auth_user_id', client.session)

    def test_session_cleanup(self):
        """Test session cleanup on logout."""
        client = APIClient()
        client.login(username='testuser', password='TestPassword123!')

        # Session exists
        self.assertTrue('_auth_user_id' in client.session)

        # Logout clears session
        client.logout()
        self.assertFalse('_auth_user_id' in client.session)
```

### APIRequestFactory vs APIClient

**APIRequestFactory:** Low-level request creation (unit testing views directly)
**APIClient:** High-level client simulation (integration testing through URLs)

```python
from rest_framework.test import APIRequestFactory, force_authenticate
from myapp.views import MyAPIView

class FactoryVsClientTests(TestCase):
    """Compare APIRequestFactory and APIClient."""

    def test_with_factory(self):
        """Test view directly with APIRequestFactory."""
        factory = APIRequestFactory()
        view = MyAPIView.as_view()

        # Create request
        request = factory.get('/api/v1/data/')

        # Force authentication
        force_authenticate(request, user=self.user)

        # Call view directly
        response = view(request)

        self.assertEqual(response.status_code, 200)

    def test_with_client(self):
        """Test through URL routing with APIClient."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        # Goes through URL routing
        response = client.get('/api/v1/data/')

        self.assertEqual(response.status_code, 200)
```

**When to use APIRequestFactory:**
- Unit testing views in isolation
- Don't need middleware processing
- Don't need URL resolution
- Testing view logic only

**When to use APIClient:**
- Integration testing with middleware
- Testing URL routing
- Testing full request/response cycle
- More realistic testing scenario

---

## Testing Layered Security

### Defense-in-Depth Pattern

Multiple security layers should work independently and reinforce each other.

**Source:** OWASP Django REST Framework Cheat Sheet

### Testing Multiple Security Decorators

```python
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes

class LayeredSecurityTests(TestCase):
    """Test interaction of multiple security layers."""

    def test_unauthenticated_blocked_before_rate_limit(self):
        """Test authentication blocks before rate limiting."""
        client = APIClient()

        # No authentication - should get 401, not 429
        response = client.post('/api/v1/protected/', {'data': 'value'})
        self.assertEqual(response.status_code, 401)
        # NOT 403 (CSRF) or 429 (rate limit)

    def test_rate_limit_after_authentication(self):
        """Test rate limiting applies to authenticated users."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        # Clear rate limit cache
        from django.core.cache import cache
        cache.clear()

        # Make requests up to limit (e.g., 5 per 15 min)
        for i in range(5):
            response = client.post('/api/v1/login/', {
                'username': 'testuser',
                'password': 'wrong'
            })
            # May get 401 (wrong password) but not 429 yet
            self.assertIn(response.status_code, [401, 200])

        # Next request should be rate limited
        response = client.post('/api/v1/login/', {
            'username': 'testuser',
            'password': 'wrong'
        })
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)

    def test_account_lockout_overrides_rate_limit(self):
        """Test account lockout takes precedence."""
        client = APIClient()

        # Trigger account lockout (e.g., 10 failed attempts)
        for i in range(10):
            client.post('/api/v1/auth/login/', {
                'username': 'testuser',
                'password': 'wrong'
            })

        # Account locked - specific error, not rate limit
        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'  # Correct password
        })
        self.assertEqual(response.status_code, 403)
        self.assertIn('account is locked', response.data['detail'].lower())
```

### Conditional Assertions for Security Layers

```python
class ConditionalSecurityTests(TestCase):
    """Test conditional security behavior."""

    def test_anonymous_stricter_rate_limit(self):
        """Test anonymous users have stricter rate limits."""
        from django.core.cache import cache

        # Test anonymous limit (e.g., 3/hour)
        anon_client = APIClient()
        cache.clear()

        for i in range(3):
            response = anon_client.post('/api/v1/public-endpoint/', {})
            self.assertIn(response.status_code, [200, 201])

        # 4th request blocked
        response = anon_client.post('/api/v1/public-endpoint/', {})
        self.assertEqual(response.status_code, 429)

        # Test authenticated limit (e.g., 100/hour)
        auth_client = APIClient()
        auth_client.force_authenticate(user=self.user)
        cache.clear()

        # Can make more requests
        for i in range(10):
            response = auth_client.post('/api/v1/public-endpoint/', {})
            self.assertIn(response.status_code, [200, 201])

    def test_ip_based_rate_limiting(self):
        """Test IP-based rate limiting."""
        client = APIClient()

        # Same IP, different users - share rate limit
        cache.clear()

        # User 1 makes requests
        client.force_authenticate(user=self.user)
        for i in range(3):
            response = client.post('/api/v1/endpoint/', {})

        # User 2 from same IP - rate limit shared
        user2 = User.objects.create_user(
            username='user2',
            password='Pass123!'
        )
        client.force_authenticate(user=user2)

        # Immediately hits rate limit
        response = client.post('/api/v1/endpoint/', {})
        self.assertEqual(response.status_code, 429)
```

### Testing Decorator Stacking

```python
class DecoratorStackingTests(TestCase):
    """Test multiple @ratelimit decorators."""

    def test_multiple_rate_limit_windows(self):
        """Test stacked rate limits (10/min, 100/hour, 1000/day)."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        from django.core.cache import cache
        cache.clear()

        # Test minute limit
        for i in range(10):
            response = client.post('/api/v1/strict-endpoint/', {})
            self.assertEqual(response.status_code, 200)

        # 11th request in same minute - blocked
        response = client.post('/api/v1/strict-endpoint/', {})
        self.assertEqual(response.status_code, 429)

        # Verify error message indicates minute limit
        self.assertIn('minute', response.data['detail'].lower())
```

### Security Layer Priority Testing

```python
class SecurityPriorityTests(TestCase):
    """Test order of security checks."""

    def test_security_check_order(self):
        """
        Expected order:
        1. CSRF (if session auth)
        2. Authentication
        3. Permissions
        4. Rate limiting
        5. Account lockout
        6. Business logic
        """
        client = APIClient(enforce_csrf_checks=True)

        # 1. Missing CSRF should fail first (if using session auth)
        client.login(username='testuser', password='TestPassword123!')
        response = client.post('/api/v1/protected/', {})
        self.assertEqual(response.status_code, 403)  # CSRF

        # 2. Missing authentication (no CSRF required for token auth)
        client_no_csrf = APIClient()
        response = client_no_csrf.post('/api/v1/protected/', {})
        self.assertEqual(response.status_code, 401)  # Authentication

        # 3. Insufficient permissions
        basic_user = User.objects.create_user(
            username='basic',
            password='Pass123!'
        )
        client_no_csrf.force_authenticate(user=basic_user)
        response = client_no_csrf.post('/api/v1/admin-only/', {})
        self.assertEqual(response.status_code, 403)  # Permission
```

---

## Time-Based Testing in Django

### Recommended Library: time-machine

**Why time-machine over freezegun:**
- 100-200x faster (critical for large test suites)
- Mocks at C-level (consistent across all time sources)
- Better Django integration
- Handles `django.utils.timezone.now()` correctly

**Source:** [time-machine documentation](https://time-machine.readthedocs.io/)

### Installation

```bash
pip install time-machine
```

### Basic Usage

```python
import time_machine
from datetime import datetime, timedelta
from django.utils import timezone

class TimeBasedTests(TestCase):
    """Test time-dependent features."""

    @time_machine.travel("2025-10-23 12:00:00", tick=False)
    def test_token_expiration(self):
        """Test JWT token expiration."""
        # Create token at fixed time
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        access_token = response.data['access']

        # Token valid at current time
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get('/api/v1/protected/')
        self.assertEqual(response.status_code, 200)

    @time_machine.travel("2025-10-23 12:00:00", tick=False)
    def test_token_expired(self):
        """Test expired token rejection."""
        # Create token
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        access_token = response.data['access']

        # Move time forward past expiration (e.g., 1 hour)
        with time_machine.travel("2025-10-23 13:30:00", tick=False):
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
            response = self.client.get('/api/v1/protected/')
            self.assertEqual(response.status_code, 401)
            self.assertIn('expired', response.data['detail'].lower())
```

### Testing Account Lockout Expiry

```python
class AccountLockoutTimeTests(TestCase):
    """Test time-based account lockout."""

    @time_machine.travel("2025-10-23 12:00:00", tick=False)
    def test_lockout_duration(self):
        """Test account lockout expires after 1 hour."""
        from apps.core.security import SecurityMonitor

        # Trigger lockout (10 failed attempts)
        for i in range(10):
            SecurityMonitor.track_failed_login_attempt('testuser')

        # Verify locked
        is_locked, attempts = SecurityMonitor.is_account_locked('testuser')
        self.assertTrue(is_locked)

        # Move time forward 59 minutes - still locked
        with time_machine.travel("2025-10-23 12:59:00", tick=False):
            is_locked, attempts = SecurityMonitor.is_account_locked('testuser')
            self.assertTrue(is_locked)

        # Move time forward 61 minutes - unlocked
        with time_machine.travel("2025-10-23 13:01:00", tick=False):
            is_locked, attempts = SecurityMonitor.is_account_locked('testuser')
            self.assertFalse(is_locked)
            self.assertEqual(attempts, 0)
```

### Avoiding Recursive Mocking Issues

**Problem:** Mocking `time.time()` or `datetime.now()` at module level can cause recursive imports.

**Solution:** Mock where it's used, not where it's defined.

```python
# BAD: Mocking in the wrong namespace
from unittest.mock import patch
import time

@patch('time.time')  # DON'T do this
def test_something(mock_time):
    pass

# GOOD: Mock where it's imported
@patch('myapp.services.time.time')  # DO this
def test_something(mock_time):
    mock_time.return_value = 1698067200.0
    # Test code
```

**Best Practice:** Use time-machine to avoid namespace issues entirely.

```python
@time_machine.travel("2025-10-23 12:00:00", tick=False)
def test_with_time_machine(self):
    """time-machine handles all time sources automatically."""
    import time
    from datetime import datetime
    from django.utils import timezone

    # All return mocked time
    self.assertEqual(time.time(), 1729684800.0)
    self.assertEqual(datetime.now().hour, 12)
    self.assertEqual(timezone.now().hour, 12)
```

### Module-Specific vs Global Patching

```python
# services.py
import time

def check_timestamp():
    return time.time()

# tests.py
from unittest.mock import patch

class PatchingTests(TestCase):
    """Demonstrate correct patching patterns."""

    # WRONG: Patch at definition
    @patch('time.time')
    def test_wrong_patching(self, mock_time):
        """This may not work - time.time already imported."""
        mock_time.return_value = 1234567890
        from myapp.services import check_timestamp

        # May use real time.time, not mocked
        result = check_timestamp()

    # CORRECT: Patch where used
    @patch('myapp.services.time')
    def test_correct_patching(self, mock_time):
        """Patch in the module that uses it."""
        mock_time.time.return_value = 1234567890
        from myapp.services import check_timestamp

        # Uses mocked time
        result = check_timestamp()
        self.assertEqual(result, 1234567890)

    # BEST: Use time-machine
    @time_machine.travel("2009-02-13 23:31:30", tick=False)
    def test_best_patching(self):
        """time-machine handles everything."""
        from myapp.services import check_timestamp

        result = check_timestamp()
        self.assertEqual(result, 1234567890.0)
```

### Testing Rate Limit Window Expiry

```python
class RateLimitTimeTests(TestCase):
    """Test rate limit window expiry."""

    @time_machine.travel("2025-10-23 12:00:00", tick=False)
    def test_rate_limit_window_reset(self):
        """Test rate limit resets after time window."""
        from django.core.cache import cache

        client = APIClient()
        cache.clear()

        # Make 5 requests (at limit)
        for i in range(5):
            response = client.post('/api/v1/endpoint/', {})
            self.assertEqual(response.status_code, 200)

        # 6th request blocked
        response = client.post('/api/v1/endpoint/', {})
        self.assertEqual(response.status_code, 429)

        # Move time forward 14 minutes - still blocked (15 min window)
        with time_machine.travel("2025-10-23 12:14:00", tick=False):
            response = client.post('/api/v1/endpoint/', {})
            self.assertEqual(response.status_code, 429)

        # Move time forward 16 minutes - window reset
        with time_machine.travel("2025-10-23 12:16:00", tick=False):
            cache.clear()  # Simulate cache expiry
            response = client.post('/api/v1/endpoint/', {})
            self.assertEqual(response.status_code, 200)
```

---

## API Versioning in Tests

### URL Pattern Consistency

**Source:** [Django REST Framework Versioning](https://www.django-rest-framework.org/api-guide/versioning/)

### Recommended: NamespaceVersioning

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    path('api/v1/', include(('myapp.api.v1.urls', 'v1'))),
    path('api/v2/', include(('myapp.api.v2.urls', 'v2'))),
]

# settings.py
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
}
```

### Testing Versioned Endpoints

```python
from django.urls import reverse

class VersioningTests(TestCase):
    """Test API versioning."""

    def test_v1_endpoint(self):
        """Test version 1 API."""
        url = reverse('v1:plant-identification-identify')

        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.post(url, {
            'image': self.test_image
        })

        self.assertEqual(response.status_code, 200)
        # v1 specific assertions
        self.assertIn('plant_name', response.data)

    def test_v2_endpoint(self):
        """Test version 2 API with breaking changes."""
        url = reverse('v2:plant-identification-identify')

        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.post(url, {
            'image': self.test_image,
            'include_diseases': True  # v2 feature
        })

        self.assertEqual(response.status_code, 200)
        # v2 specific assertions
        self.assertIn('identification', response.data)
        self.assertIn('diseases', response.data)

    def test_version_not_allowed(self):
        """Test that disallowed versions are rejected."""
        # Try to access non-existent v3
        try:
            url = reverse('v3:plant-identification-identify')
            self.fail("v3 namespace should not exist")
        except Exception:
            pass  # Expected
```

### Version Namespace Testing

```python
class NamespaceVersionTests(TestCase):
    """Test namespace-based versioning."""

    def test_version_in_namespace(self):
        """Test version extracted from URL namespace."""
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()

        # Create request through v1 namespace
        request = factory.get('/api/v1/endpoint/')
        request.versioning_scheme = NamespaceVersioning()

        # Version determined by namespace
        version = request.versioning_scheme.determine_version(
            request,
            view=None
        )
        self.assertEqual(version, 'v1')

    def test_backward_compatibility(self):
        """Test that v1 endpoints remain stable."""
        # v1 must not break when v2 is added
        url_v1 = reverse('v1:user-list')
        url_v2 = reverse('v2:user-list')

        client = APIClient()
        client.force_authenticate(user=self.user)

        # v1 response format unchanged
        response_v1 = client.get(url_v1)
        self.assertIn('username', response_v1.data[0])

        # v2 may have different format
        response_v2 = client.get(url_v2)
        self.assertIn('user_name', response_v2.data[0])  # Breaking change OK in v2
```

### Maintaining Test URLs When APIs Evolve

```python
class APIEvolutionTests(TestCase):
    """Test API evolution patterns."""

    def setUp(self):
        """Set up versioned URLs."""
        # Store versioned URLs as class attributes
        self.url_v1_identify = reverse('v1:plant-identification-identify')
        self.url_v2_identify = reverse('v2:plant-identification-identify')

    def test_deprecated_field_v1(self):
        """Test v1 includes deprecated field."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.post(self.url_v1_identify, {
            'image': self.test_image
        })

        # v1 includes deprecated 'plant_name' for backward compatibility
        self.assertIn('plant_name', response.data)
        self.assertIn('scientific_name', response.data)

    def test_deprecated_field_removed_v2(self):
        """Test v2 removes deprecated field."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.post(self.url_v2_identify, {
            'image': self.test_image
        })

        # v2 removes 'plant_name', uses only 'scientific_name'
        self.assertNotIn('plant_name', response.data)
        self.assertIn('scientific_name', response.data)

    def test_migration_path_documented(self):
        """Test migration guidance provided."""
        # v1 response includes migration hints
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.get(self.url_v1_identify + '?help=migration')

        self.assertIn('deprecated_fields', response.data)
        self.assertIn('plant_name', response.data['deprecated_fields'])
        self.assertIn('use_instead', response.data['deprecated_fields']['plant_name'])
```

---

## DRF Authentication Testing Patterns

### JWT Token Testing

```python
from rest_framework_simplejwt.tokens import RefreshToken

class JWTAuthenticationTests(TestCase):
    """JWT authentication testing patterns."""

    def test_obtain_token_pair(self):
        """Test obtaining access and refresh tokens."""
        client = APIClient()

        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        # Tokens should be different
        self.assertNotEqual(response.data['access'], response.data['refresh'])

    def test_access_token_usage(self):
        """Test using access token for authentication."""
        # Get token
        client = APIClient()
        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        access_token = response.data['access']

        # Use token (Bearer, not Token)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = client.get('/api/v1/user/profile/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'testuser')

    def test_refresh_token_rotation(self):
        """Test refresh token rotation on refresh."""
        client = APIClient()

        # Get initial tokens
        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        refresh_token = response.data['refresh']

        # Refresh to get new access token
        response = client.post('/api/v1/auth/token/refresh/', {
            'refresh': refresh_token
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)

        # If rotation enabled, new refresh token provided
        if 'refresh' in response.data:
            self.assertNotEqual(response.data['refresh'], refresh_token)
```

### CSRF Protection Testing

```python
class CSRFProtectionTests(TestCase):
    """CSRF protection with cookie-based JWT."""

    def test_csrf_required_for_state_changing(self):
        """Test CSRF required for POST/PUT/DELETE."""
        client = APIClient(enforce_csrf_checks=True)
        client.login(username='testuser', password='TestPassword123!')

        # POST without CSRF token - rejected
        response = client.post('/api/v1/data/', {'key': 'value'})
        self.assertEqual(response.status_code, 403)

    def test_csrf_not_required_for_get(self):
        """Test CSRF not required for GET requests."""
        client = APIClient(enforce_csrf_checks=True)
        client.login(username='testuser', password='TestPassword123!')

        # GET without CSRF token - allowed
        response = client.get('/api/v1/data/')
        self.assertEqual(response.status_code, 200)

    def test_csrf_token_in_cookie_and_header(self):
        """Test CSRF token must match cookie and header."""
        from django.middleware.csrf import get_token
        from django.test import RequestFactory

        client = APIClient(enforce_csrf_checks=True)
        client.login(username='testuser', password='TestPassword123!')

        # Get CSRF token from cookie
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.user
        csrf_token = get_token(request)

        # Include token in header
        response = client.post(
            '/api/v1/data/',
            {'key': 'value'},
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, 200)
```

### Account Lockout Testing

```python
class AccountLockoutTests(TestCase):
    """Account lockout mechanism testing."""

    def test_lockout_after_failed_attempts(self):
        """Test account locks after threshold (e.g., 10 attempts)."""
        client = APIClient()

        # Make failed login attempts
        for i in range(10):
            response = client.post('/api/v1/auth/login/', {
                'username': 'testuser',
                'password': 'WrongPassword!'
            })
            self.assertEqual(response.status_code, 401)

        # 11th attempt - account locked
        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'  # Even correct password
        })

        self.assertEqual(response.status_code, 403)
        self.assertIn('locked', response.data['detail'].lower())

    def test_lockout_cleared_on_successful_login(self):
        """Test failed attempts reset after successful login."""
        client = APIClient()

        # Make 5 failed attempts
        for i in range(5):
            client.post('/api/v1/auth/login/', {
                'username': 'testuser',
                'password': 'WrongPassword!'
            })

        # Successful login clears counter
        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        self.assertEqual(response.status_code, 200)

        # Counter reset - can make more failed attempts
        for i in range(5):
            client.post('/api/v1/auth/login/', {
                'username': 'testuser',
                'password': 'WrongPassword!'
            })

        # Not locked yet (counter was reset)
        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        self.assertEqual(response.status_code, 200)

    def test_lockout_email_notification(self):
        """Test email sent when account locked."""
        from django.core import mail

        client = APIClient()

        # Trigger lockout
        for i in range(10):
            client.post('/api/v1/auth/login/', {
                'username': 'testuser',
                'password': 'WrongPassword!'
            })

        # Verify email sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('locked', mail.outbox[0].subject.lower())
        self.assertEqual(mail.outbox[0].to, [self.user.email])
```

### Rate Limiting Testing

```python
class RateLimitingTests(TestCase):
    """Rate limiting testing patterns."""

    def test_rate_limit_per_ip(self):
        """Test IP-based rate limiting."""
        from django.core.cache import cache

        client = APIClient()
        cache.clear()

        # Make requests from same IP
        for i in range(5):
            response = client.post('/api/v1/auth/login/', {
                'username': 'testuser',
                'password': 'WrongPassword!'
            })
            self.assertIn(response.status_code, [401, 200])

        # Exceeded rate limit
        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'WrongPassword!'
        })

        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)

    def test_rate_limit_retry_after_header(self):
        """Test Retry-After header present when rate limited."""
        from django.core.cache import cache

        client = APIClient()
        cache.clear()

        # Exceed rate limit
        for i in range(6):
            response = client.post('/api/v1/auth/login/', {
                'username': 'test',
                'password': 'wrong'
            })

        # Check Retry-After header
        self.assertIn('Retry-After', response)
        retry_after = int(response['Retry-After'])
        self.assertGreater(retry_after, 0)
        self.assertLessEqual(retry_after, 900)  # Max 15 minutes

    def test_rate_limit_different_endpoints(self):
        """Test separate rate limits per endpoint."""
        from django.core.cache import cache

        client = APIClient()
        cache.clear()

        # Exhaust login rate limit
        for i in range(5):
            client.post('/api/v1/auth/login/', {})

        # Registration endpoint has separate limit
        response = client.post('/api/v1/auth/register/', {
            'username': 'newuser',
            'password': 'Pass123!',
            'email': 'new@example.com'
        })

        # Should not be rate limited (separate counter)
        self.assertNotEqual(response.status_code, 429)
```

---

## pytest-django Integration

### Recommended Fixtures

```python
# conftest.py
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def api_client():
    """Provide APIClient instance."""
    return APIClient()

@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='TestPassword123!'
    )

@pytest.fixture
def admin_user(db):
    """Create admin user."""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='AdminPassword123!'
    )

@pytest.fixture
def authenticated_client(api_client, user):
    """Provide authenticated APIClient."""
    api_client.force_authenticate(user=user)
    return api_client

@pytest.fixture
def admin_client(api_client, admin_user):
    """Provide admin authenticated APIClient."""
    api_client.force_authenticate(user=admin_user)
    return api_client

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
```

### Using Fixtures in Tests

```python
# test_authentication.py
import pytest
from rest_framework import status

@pytest.mark.django_db
class TestAuthentication:
    """Authentication tests using pytest."""

    def test_login_success(self, api_client, user):
        """Test successful login."""
        response = api_client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_protected_endpoint_authenticated(self, authenticated_client):
        """Test authenticated access to protected endpoint."""
        response = authenticated_client.get('/api/v1/user/profile/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == 'testuser'

    def test_protected_endpoint_unauthenticated(self, api_client):
        """Test unauthenticated access denied."""
        response = api_client.get('/api/v1/user/profile/')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

### Parametrized Testing

```python
import pytest
from rest_framework import status

@pytest.mark.django_db
class TestPermissions:
    """Test permissions with parametrization."""

    @pytest.mark.parametrize('user_fixture,expected_status', [
        ('api_client', status.HTTP_401_UNAUTHORIZED),  # Anonymous
        ('authenticated_client', status.HTTP_403_FORBIDDEN),  # Regular user
        ('admin_client', status.HTTP_200_OK),  # Admin
    ])
    def test_admin_endpoint_permissions(
        self,
        user_fixture,
        expected_status,
        request
    ):
        """Test admin endpoint permissions for different user types."""
        client = request.getfixturevalue(user_fixture)

        response = client.get('/api/v1/admin/users/')
        assert response.status_code == expected_status

    @pytest.mark.parametrize('password,expected_status,error_field', [
        ('short', status.HTTP_400_BAD_REQUEST, 'password'),  # Too short
        ('NoNumbers!', status.HTTP_400_BAD_REQUEST, 'password'),  # No numbers
        ('nonumbers123', status.HTTP_400_BAD_REQUEST, 'password'),  # No uppercase
        ('NOLOWERCASE123!', status.HTTP_400_BAD_REQUEST, 'password'),  # No lowercase
        ('ValidPass123!', status.HTTP_201_CREATED, None),  # Valid
    ])
    def test_password_validation(
        self,
        api_client,
        password,
        expected_status,
        error_field
    ):
        """Test password validation rules."""
        response = api_client.post('/api/v1/auth/register/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': password,
            'password_confirm': password
        })

        assert response.status_code == expected_status

        if error_field:
            assert error_field in response.data
```

### Markers for Test Organization

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks integration tests",
    "unit: marks unit tests",
    "security: marks security-related tests",
]

# test_authentication.py
import pytest

@pytest.mark.security
@pytest.mark.django_db
class TestRateLimiting:
    """Rate limiting tests."""

    @pytest.mark.slow
    def test_rate_limit_window_expiry(self, api_client):
        """Test rate limit resets (requires time manipulation)."""
        # Time-consuming test
        pass

    @pytest.mark.unit
    def test_rate_limit_calculation(self):
        """Test rate limit calculation logic."""
        # Fast unit test
        pass

# Run only fast tests
# pytest -m "not slow"

# Run only security tests
# pytest -m security
```

---

## Common Pitfalls and Solutions

### Pitfall 1: CSRF Confusion

**Problem:** Tests pass but production fails with 403 CSRF errors.

**Cause:** APIClient disables CSRF by default.

**Solution:**

```python
# tests.py - WRONG
class MyTests(TestCase):
    def test_post(self):
        client = APIClient()  # CSRF disabled
        client.login(username='user', password='pass')

        response = client.post('/api/endpoint/', {})
        self.assertEqual(response.status_code, 200)  # Passes in test

# Production: 403 Forbidden (CSRF required)

# tests.py - CORRECT
class MyTests(TestCase):
    def test_post_with_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username='user', password='pass')

        # Must include CSRF token
        from django.middleware.csrf import get_token
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.user
        csrf_token = get_token(request)

        response = client.post(
            '/api/endpoint/',
            {},
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(response.status_code, 200)
```

### Pitfall 2: Rate Limit Cache Pollution

**Problem:** Rate limit tests interfere with each other.

**Cause:** Rate limit counters persist in cache between tests.

**Solution:**

```python
# WRONG
class RateLimitTests(TestCase):
    def test_rate_limit_1(self):
        # Makes 5 requests
        pass

    def test_rate_limit_2(self):
        # Makes 2 requests - fails because previous test used 5
        pass

# CORRECT
class RateLimitTests(TestCase):
    def setUp(self):
        """Clear cache before each test."""
        from django.core.cache import cache
        cache.clear()

    def tearDown(self):
        """Clear cache after each test."""
        from django.core.cache import cache
        cache.clear()

    def test_rate_limit_1(self):
        # Starts with clean cache
        pass

    def test_rate_limit_2(self):
        # Starts with clean cache
        pass
```

### Pitfall 3: Time Zone Issues

**Problem:** Time-based tests fail in different time zones.

**Cause:** Using `datetime.now()` instead of `timezone.now()`.

**Solution:**

```python
# WRONG
from datetime import datetime

def test_token_expiry(self):
    # Naive datetime (no timezone)
    now = datetime.now()
    # Fails in production with different TZ

# CORRECT
from django.utils import timezone

def test_token_expiry(self):
    # Timezone-aware datetime
    now = timezone.now()
    # Works in all time zones
```

### Pitfall 4: Token Type Mismatch

**Problem:** Authorization header rejected.

**Cause:** Using wrong prefix (Token vs Bearer).

**Solution:**

```python
# WRONG - DRF Token Authentication
client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)  # Wrong prefix

# CORRECT - DRF Token Authentication
from rest_framework.authtoken.models import Token
token = Token.objects.create(user=user)
client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

# CORRECT - JWT Authentication
client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)
```

### Pitfall 5: Force Authenticate Scope

**Problem:** Force authenticate doesn't persist across requests.

**Cause:** Misunderstanding force_authenticate lifecycle.

**Solution:**

```python
# WRONG
def test_multiple_requests(self):
    factory = APIRequestFactory()

    request1 = factory.get('/api/endpoint1/')
    force_authenticate(request1, user=self.user)
    # request1 authenticated

    request2 = factory.get('/api/endpoint2/')
    # request2 NOT authenticated (force_authenticate doesn't persist)

# CORRECT - Use APIClient for persistence
def test_multiple_requests(self):
    client = APIClient()
    client.force_authenticate(user=self.user)

    response1 = client.get('/api/endpoint1/')
    response2 = client.get('/api/endpoint2/')
    # Both authenticated
```

### Pitfall 6: Database Transaction Isolation

**Problem:** Tests see data from other tests.

**Cause:** Not using TestCase (uses transactions).

**Solution:**

```python
# WRONG - unittest.TestCase
import unittest

class MyTests(unittest.TestCase):
    def test_1(self):
        User.objects.create(username='test')
        # Data persists

    def test_2(self):
        # Sees user from test_1
        self.assertEqual(User.objects.count(), 1)

# CORRECT - Django TestCase
from django.test import TestCase

class MyTests(TestCase):
    def test_1(self):
        User.objects.create(username='test')
        # Data rolled back after test

    def test_2(self):
        # Clean database
        self.assertEqual(User.objects.count(), 0)
```

### Pitfall 7: Parallel Test Race Conditions

**Problem:** Tests fail when run in parallel.

**Cause:** Shared resources (cache keys, database rows).

**Solution:**

```python
# WRONG - Shared cache key
def test_rate_limit_1(self):
    cache.set('rate_limit', 5)  # Conflicts with parallel test

# CORRECT - Unique cache keys
def test_rate_limit_1(self):
    import uuid
    cache_key = f'rate_limit_{uuid.uuid4()}'
    cache.set(cache_key, 5)

# Or use TransactionTestCase for isolation
from django.test import TransactionTestCase

class IsolatedTests(TransactionTestCase):
    # Each test gets isolated database transaction
    pass
```

---

## Real-World Examples

### Example 1: Complete Authentication Flow

```python
class CompleteAuthFlowTests(TestCase):
    """Test complete authentication workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

    def test_registration_login_access_logout(self):
        """Test complete user journey."""
        client = APIClient()

        # 1. Register new user
        response = client.post('/api/v1/auth/register/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'NewPassword123!',
            'password_confirm': 'NewPassword123!'
        })
        self.assertEqual(response.status_code, 201)

        # 2. Login
        response = client.post('/api/v1/auth/login/', {
            'username': 'newuser',
            'password': 'NewPassword123!'
        })
        self.assertEqual(response.status_code, 200)
        access_token = response.data['access']
        refresh_token = response.data['refresh']

        # 3. Access protected endpoint
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = client.get('/api/v1/user/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'newuser')

        # 4. Refresh token
        client.credentials()  # Clear old token
        response = client.post('/api/v1/auth/token/refresh/', {
            'refresh': refresh_token
        })
        self.assertEqual(response.status_code, 200)
        new_access_token = response.data['access']

        # 5. Use new token
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access_token}')
        response = client.get('/api/v1/user/profile/')
        self.assertEqual(response.status_code, 200)

        # 6. Logout (blacklist refresh token)
        response = client.post('/api/v1/auth/logout/', {
            'refresh': refresh_token
        })
        self.assertEqual(response.status_code, 200)

        # 7. Verify token blacklisted
        response = client.post('/api/v1/auth/token/refresh/', {
            'refresh': refresh_token
        })
        self.assertEqual(response.status_code, 401)
```

### Example 2: Security Layer Integration

```python
class SecurityLayerIntegrationTests(TestCase):
    """Test multiple security layers working together."""

    def test_brute_force_protection_flow(self):
        """Test rate limiting -> account lockout -> email notification."""
        from django.core import mail
        from django.core.cache import cache

        client = APIClient()
        cache.clear()

        # 1. First 5 attempts - rate limit NOT triggered yet
        for i in range(5):
            response = client.post('/api/v1/auth/login/', {
                'username': 'testuser',
                'password': 'WrongPassword!'
            })
            self.assertEqual(response.status_code, 401)
            self.assertNotIn('rate limit', response.data.get('detail', '').lower())

        # 2. Next attempt - rate limited
        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'WrongPassword!'
        })
        self.assertEqual(response.status_code, 429)

        # 3. Clear rate limit, continue to lockout
        cache.clear()

        for i in range(5):  # 5 more attempts (total 10)
            client.post('/api/v1/auth/login/', {
                'username': 'testuser',
                'password': 'WrongPassword!'
            })

        # 4. Account locked
        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'  # Even correct password
        })
        self.assertEqual(response.status_code, 403)
        self.assertIn('locked', response.data['detail'].lower())

        # 5. Email notification sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('locked', mail.outbox[0].subject.lower())
        self.assertEqual(mail.outbox[0].to, [self.user.email])

        # 6. Verify lockout persists
        response = client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        self.assertEqual(response.status_code, 403)
```

### Example 3: pytest-django Real-World Test

```python
import pytest
from rest_framework import status
from django.core import mail
import time_machine

@pytest.mark.django_db
class TestAuthenticationSecurity:
    """Real-world authentication security tests."""

    def test_ip_spoofing_prevention(self, api_client):
        """Test IP spoofing prevention in rate limiting."""
        # Attacker tries to spoof IP
        response = api_client.post(
            '/api/v1/auth/login/',
            {'username': 'victim', 'password': 'wrong'},
            HTTP_X_FORWARDED_FOR='999.999.999.999',  # Invalid IP
            REMOTE_ADDR='192.168.1.100'
        )

        # System falls back to REMOTE_ADDR (valid IP)
        # Rate limit tracked under 192.168.1.100
        assert response.status_code in [401, 429]

    @time_machine.travel("2025-10-23 12:00:00", tick=False)
    def test_token_expiry_and_refresh(self, api_client, user):
        """Test token expiry with time manipulation."""
        # Login at 12:00
        response = api_client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        access_token = response.data['access']
        refresh_token = response.data['refresh']

        # Token valid at 12:00
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = api_client.get('/api/v1/user/profile/')
        assert response.status_code == status.HTTP_200_OK

        # Move to 13:30 (access token expired after 1 hour)
        with time_machine.travel("2025-10-23 13:30:00", tick=False):
            response = api_client.get('/api/v1/user/profile/')
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

            # Refresh still valid (24 hour lifespan)
            api_client.credentials()
            response = api_client.post('/api/v1/auth/token/refresh/', {
                'refresh': refresh_token
            })
            assert response.status_code == status.HTTP_200_OK

            new_access_token = response.data['access']
            api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access_token}')
            response = api_client.get('/api/v1/user/profile/')
            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize('endpoint,method,rate_limit', [
        ('/api/v1/auth/login/', 'POST', 5),
        ('/api/v1/auth/register/', 'POST', 3),
        ('/api/v1/auth/token/refresh/', 'POST', 10),
    ])
    def test_endpoint_specific_rate_limits(
        self,
        api_client,
        endpoint,
        method,
        rate_limit,
        django_cache
    ):
        """Test different rate limits per endpoint."""
        # Clear cache
        django_cache.clear()

        # Make requests up to limit
        for i in range(rate_limit):
            if method == 'POST':
                response = api_client.post(endpoint, {})
            else:
                response = api_client.get(endpoint)

        # Next request should be rate limited
        if method == 'POST':
            response = api_client.post(endpoint, {})
        else:
            response = api_client.get(endpoint)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert 'Retry-After' in response
```

---

## Summary: Key Takeaways

### 1. APIClient vs TestClient

- Use APIClient for REST APIs (built-in auth helpers)
- CSRF disabled by default (enable with `enforce_csrf_checks=True`)
- `force_authenticate()` for bypassing auth in tests

### 2. Layered Security Testing

- Test each layer independently
- Test layers in combination
- Clear cache between tests to avoid interference
- Use conditional assertions (rate limit may or may not trigger first)

### 3. Time-Based Testing

- Use `time-machine` (100-200x faster than freezegun)
- Mock where time is used, not where it's defined
- Use Django's `timezone.now()` for TZ-aware tests

### 4. API Versioning

- Use NamespaceVersioning for URL-based versions
- Test backward compatibility when adding versions
- Use `reverse('v1:endpoint')` in tests

### 5. pytest-django

- Create reusable fixtures in conftest.py
- Use parametrize for testing multiple scenarios
- Mark tests for organization (@pytest.mark.security)
- Use `@pytest.mark.django_db` for database access

### 6. Common Pitfalls

- CSRF confusion (disabled in APIClient by default)
- Cache pollution between tests
- Time zone issues (use timezone.now())
- Token type mismatch (Token vs Bearer)
- Database isolation (use TestCase)

---

**Document Status:** Complete
**Last Updated:** October 23, 2025
**Authority Level:** Authoritative (based on official docs + community best practices)
**Next Steps:** Apply these patterns to existing test suite

---

## Additional Resources

### Official Documentation

- [Django REST Framework Testing](https://www.django-rest-framework.org/api-guide/testing/)
- [Django REST Framework Authentication](https://www.django-rest-framework.org/api-guide/authentication/)
- [Django Testing Tools](https://docs.djangoproject.com/en/5.0/topics/testing/tools/)
- [pytest-django Documentation](https://pytest-django.readthedocs.io/)
- [time-machine Documentation](https://time-machine.readthedocs.io/)

### Community Resources

- [OWASP Django REST Framework Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Django_REST_Framework_Cheat_Sheet.html)
- [DRF Official Tests (GitHub)](https://github.com/encode/django-rest-framework/tree/master/tests)
- [Real Python: Python Mock Library](https://realpython.com/python-mock-library/)

### Project-Specific Documentation

- `/backend/docs/testing/AUTHENTICATION_TESTS.md` - Current test suite (63+ tests)
- `/backend/docs/security/AUTHENTICATION_SECURITY.md` - Security implementation
- `/backend/docs/development/AUTHENTICATION_TESTING_SECURITY_BEST_PRACTICES.md` - Research notes
