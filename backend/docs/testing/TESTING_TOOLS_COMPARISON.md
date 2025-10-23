# Testing Tools Comparison

**Quick Reference for Choosing the Right Testing Tools**

**Date:** October 23, 2025

---

## Test Client Comparison

### APIClient vs TestClient vs APIRequestFactory

| Feature | APIClient | TestClient | APIRequestFactory |
|---------|-----------|------------|-------------------|
| **Purpose** | REST API testing | Django view testing | Unit testing views |
| **Level** | Integration | Integration | Unit |
| **URL Resolution** | Yes | Yes | No (call view directly) |
| **Middleware** | Yes | Yes | No |
| **Session Support** | Yes | Yes | No |
| **CSRF Default** | Disabled | Enabled | N/A |
| **Authentication Methods** | 3 methods | login() only | force_authenticate() |
| **Default Format** | JSON | Form data | N/A |
| **Use Case** | DRF APIs | Template views | View logic testing |

### Authentication Methods Comparison

| Method | APIClient | TestClient | APIRequestFactory |
|--------|-----------|------------|-------------------|
| `login(username, password)` | ✅ | ✅ | ❌ |
| `credentials(HTTP_AUTHORIZATION=...)` | ✅ | ❌ | ❌ |
| `force_authenticate(user=...)` | ✅ | ❌ | ✅ (via helper) |

### Code Examples

```python
# APIClient (3 authentication methods)
from rest_framework.test import APIClient

client = APIClient()

# 1. Session auth
client.login(username='user', password='pass')

# 2. Token auth
client.credentials(HTTP_AUTHORIZATION='Token abc123')

# 3. Force auth
client.force_authenticate(user=user_obj)

# TestClient (1 authentication method)
from django.test import Client

client = Client()
client.login(username='user', password='pass')

# APIRequestFactory (view-level testing)
from rest_framework.test import APIRequestFactory, force_authenticate

factory = APIRequestFactory()
request = factory.get('/api/endpoint/')
force_authenticate(request, user=user_obj)
response = view(request)
```

### When to Use Each

**APIClient:**
- Testing DRF viewsets and API views ✅
- Need token-based authentication ✅
- Testing JSON APIs ✅
- Want simplified auth setup ✅
- Integration testing through URL routing ✅

**TestClient:**
- Testing Django template views ✅
- Testing form submissions ✅
- Need exact production CSRF behavior ✅
- Testing mixed Django/DRF apps ✅

**APIRequestFactory:**
- Unit testing view logic only ✅
- Don't need middleware ✅
- Don't need URL resolution ✅
- Testing view methods directly ✅
- Fastest tests (no overhead) ✅

---

## Time Mocking Library Comparison

### time-machine vs freezegun vs unittest.mock

| Feature | time-machine | freezegun | unittest.mock |
|---------|--------------|-----------|---------------|
| **Performance** | Fastest (100-200x) | Slow | Fast |
| **Method** | C-level hooks | Find-replace imports | Manual patching |
| **Django Support** | Excellent | Good | Manual setup |
| **timezone.now()** | ✅ Automatic | ✅ Automatic | ❌ Manual |
| **datetime.now()** | ✅ Automatic | ✅ Automatic | ✅ Manual |
| **time.time()** | ✅ Automatic | ✅ Automatic | ✅ Manual |
| **Pandas Support** | ✅ | ❌ | ❌ |
| **PyPy Support** | ❌ (CPython only) | ✅ | ✅ |
| **Setup Complexity** | Simple | Simple | Complex |
| **Maintenance** | Active (2020+) | Active (2012+) | Built-in |

### Performance Benchmarks

```
Test suite with 100 time-dependent tests:

time-machine:  1.2 seconds
freezegun:     240 seconds (200x slower)
unittest.mock: 2.5 seconds
```

### Code Examples

```python
# time-machine (Recommended for Django)
import time_machine

@time_machine.travel("2025-10-23 12:00:00", tick=False)
def test_expiry(self):
    # All time sources mocked automatically
    assert datetime.now().hour == 12
    assert timezone.now().hour == 12
    assert time.time() == 1729684800.0

# freezegun (Legacy projects)
from freezegun import freeze_time

@freeze_time("2025-10-23 12:00:00")
def test_expiry(self):
    # Slower but compatible with PyPy
    assert datetime.now().hour == 12

# unittest.mock (Manual control)
from unittest.mock import patch

@patch('myapp.services.time.time')
def test_expiry(self, mock_time):
    mock_time.return_value = 1729684800.0
    # Only mocks where explicitly patched
```

### Recommendation

**For Django projects starting in 2025:**
- Primary: `time-machine` (performance + automatic)
- Fallback: `freezegun` (if need PyPy)
- Avoid: `unittest.mock` for time (too manual)

---

## Test Framework Comparison

### Django TestCase vs pytest-django

| Feature | Django TestCase | pytest-django |
|---------|-----------------|---------------|
| **Setup** | Built-in | Requires installation |
| **Syntax** | Class-based | Function or class |
| **Fixtures** | setUp/tearDown | @pytest.fixture |
| **Fixtures Reuse** | Limited | Excellent |
| **Parametrization** | Manual | @pytest.mark.parametrize |
| **Markers** | No | Yes (@pytest.mark.slow) |
| **Discovery** | test*.py | test_*.py or *_test.py |
| **Database** | Automatic | @pytest.mark.django_db |
| **Learning Curve** | Low | Medium |
| **Migration Path** | N/A | Can run TestCase tests |

### Code Examples

```python
# Django TestCase
from django.test import TestCase

class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(...)

    def test_login_success(self):
        response = self.client.post('/api/auth/login/', {})
        self.assertEqual(response.status_code, 200)

    def test_login_invalid(self):
        response = self.client.post('/api/auth/login/', {})
        self.assertEqual(response.status_code, 401)

# pytest-django
import pytest
from rest_framework import status

@pytest.fixture
def user(db):
    return User.objects.create_user(...)

@pytest.mark.django_db
def test_login_success(api_client, user):
    response = api_client.post('/api/auth/login/', {})
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.django_db
def test_login_invalid(api_client):
    response = api_client.post('/api/auth/login/', {})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

### Parametrized Testing

```python
# Django TestCase (manual)
class PasswordValidationTests(TestCase):
    def test_short_password(self):
        response = self.client.post('/api/auth/register/', {
            'password': 'short'
        })
        self.assertEqual(response.status_code, 400)

    def test_no_numbers_password(self):
        response = self.client.post('/api/auth/register/', {
            'password': 'NoNumbers!'
        })
        self.assertEqual(response.status_code, 400)

    def test_valid_password(self):
        response = self.client.post('/api/auth/register/', {
            'password': 'ValidPass123!'
        })
        self.assertEqual(response.status_code, 201)

# pytest-django (parametrized)
@pytest.mark.django_db
@pytest.mark.parametrize('password,expected_status', [
    ('short', 400),
    ('NoNumbers!', 400),
    ('ValidPass123!', 201),
])
def test_password_validation(api_client, password, expected_status):
    response = api_client.post('/api/auth/register/', {
        'password': password
    })
    assert response.status_code == expected_status
```

### Recommendation

**For existing Django projects:**
- Keep using `TestCase` (easier, no migration needed)
- Consider pytest-django for new test files

**For new projects:**
- Use `pytest-django` (better fixtures, parametrization)
- More powerful, industry standard

**Migration strategy:**
- pytest-django can run existing TestCase tests
- Migrate incrementally, no need to rewrite everything

---

## Authentication Token Type Comparison

### DRF Token vs JWT vs Session

| Feature | DRF Token | JWT (Simple) | JWT (Cookie) | Session |
|---------|-----------|--------------|--------------|---------|
| **Storage** | Database | No database | Cookie | Database |
| **Stateless** | ❌ | ✅ | ✅ | ❌ |
| **Expiry** | Manual | Built-in | Built-in | Built-in |
| **Refresh** | No | Yes | Yes | N/A |
| **CSRF Required** | No | No | Yes | Yes |
| **Mobile Apps** | ✅ Excellent | ✅ Excellent | ⚠️ Cookies tricky | ❌ Not ideal |
| **Web Apps** | ✅ Good | ✅ Good | ✅ Excellent | ✅ Excellent |
| **Header** | `Token abc123` | `Bearer abc123` | Auto (cookie) | Auto (cookie) |
| **Blacklist** | Delete DB row | Requires setup | Requires setup | Logout |

### Test Code Examples

```python
# DRF Token Authentication
from rest_framework.authtoken.models import Token

token = Token.objects.create(user=user)
client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

# JWT (Header)
response = client.post('/api/auth/login/', {...})
access_token = response.data['access']
client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

# JWT (Cookie) - Auto included
response = client.post('/api/auth/login/', {...})
# Cookie automatically set and included in subsequent requests
response = client.get('/api/user/profile/')  # Cookie auto-sent

# Session Authentication
client.login(username='user', password='pass')
response = client.get('/api/protected/')  # Session auto-sent
```

### When to Use Each

**DRF Token:**
- Simple mobile apps ✅
- No token expiry needed ✅
- Don't need refresh tokens ✅
- Simplest implementation ✅

**JWT (Header):**
- Mobile apps ✅
- Need token expiry ✅
- Want stateless auth ✅
- Microservices architecture ✅

**JWT (Cookie):**
- Web applications ✅
- Need CSRF protection ✅
- Want automatic token management ✅
- Best security for browsers ✅

**Session:**
- Traditional Django apps ✅
- Monolithic architecture ✅
- Server-side session storage OK ✅
- Don't need mobile support ✅

---

## Rate Limiting Strategy Comparison

### DRF Throttling vs django-ratelimit vs Custom Redis

| Feature | DRF Throttling | django-ratelimit | Custom Redis |
|---------|----------------|------------------|--------------|
| **Integration** | Built-in DRF | Decorator | Manual |
| **Scope** | DRF views only | Any view | Any code |
| **Storage** | Cache (any) | Cache (any) | Redis only |
| **Granularity** | Per-user, Anon | IP, User, Custom | Full control |
| **Configuration** | Settings | Decorator args | Code |
| **Flexibility** | Medium | High | Highest |
| **Complexity** | Low | Low | High |
| **Performance** | Good | Good | Best |

### Code Examples

```python
# DRF Throttling (settings.py)
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    }
}

# django-ratelimit (decorator)
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/15m', method='POST')
def login_view(request):
    pass

# Custom Redis (full control)
from django.core.cache import cache

def check_rate_limit(key, limit, window):
    current = cache.get(key, 0)
    if current >= limit:
        return False
    cache.set(key, current + 1, window)
    return True
```

### Testing Comparison

```python
# DRF Throttling Test
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {'anon': '5/15m'}

# django-ratelimit Test
@override_settings(CACHES={'default': {...}})
def test_rate_limit(self):
    cache.clear()

# Custom Redis Test
cache.clear()
for i in range(5):
    assert check_rate_limit('test', 5, 900)
assert not check_rate_limit('test', 5, 900)
```

### Recommendation

**For DRF APIs only:**
- Use DRF Throttling (simplest)

**For mixed Django/DRF:**
- Use django-ratelimit (more flexible)

**For complex rate limiting:**
- Custom Redis (full control, best performance)

---

## API Versioning Strategy Comparison

### URL vs Header vs Accept Header

| Strategy | URL Versioning | Header Versioning | Accept Header |
|----------|----------------|-------------------|---------------|
| **Example** | `/api/v1/users/` | `X-API-Version: 1` | `Accept: application/vnd.api+json; version=1` |
| **Visibility** | ✅ Obvious | ⚠️ Hidden | ⚠️ Hidden |
| **Caching** | ✅ Easy | ❌ Difficult | ❌ Difficult |
| **Documentation** | ✅ Clear | ⚠️ Needs docs | ⚠️ Needs docs |
| **Browser Testing** | ✅ Easy | ❌ Need tools | ❌ Need tools |
| **Client Code** | ✅ Simple | ⚠️ Set headers | ⚠️ Set headers |
| **Migration** | ✅ Clear path | ⚠️ Complex | ⚠️ Complex |
| **DRF Support** | ✅ Built-in | ✅ Built-in | ✅ Built-in |

### Code Examples

```python
# URL Versioning (Recommended)
# urls.py
urlpatterns = [
    path('api/v1/', include(('myapp.api.v1.urls', 'v1'))),
    path('api/v2/', include(('myapp.api.v2.urls', 'v2'))),
]

# Test
url = reverse('v1:user-list')
response = client.get(url)

# Header Versioning
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
}

# Test
response = client.get('/api/users/', HTTP_ACCEPT='application/json; version=1')

# Accept Header Versioning
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
}

# Test
response = client.get(
    '/api/users/',
    HTTP_ACCEPT='application/vnd.myapp.v1+json'
)
```

### Recommendation

**For most projects:**
- Use URL Versioning (clearest, easiest to test)

**For strict REST purists:**
- Use Accept Header Versioning (more "REST-ful")

**For internal APIs:**
- Consider no versioning (can always add later)

---

## Summary: Recommended Stack for Django/DRF in 2025

### Testing Tools

| Purpose | Recommended Tool | Alternative |
|---------|------------------|-------------|
| **Test Client** | APIClient | TestClient (for templates) |
| **Time Mocking** | time-machine | freezegun |
| **Test Framework** | TestCase (existing) / pytest-django (new) | Either works |
| **Authentication** | JWT (Cookie) | JWT (Header) for mobile |
| **Rate Limiting** | django-ratelimit | DRF Throttling |
| **API Versioning** | URL (NamespaceVersioning) | Accept Header |

### Installation

```bash
# Core
pip install djangorestframework
pip install djangorestframework-simplejwt

# Testing
pip install pytest-django
pip install time-machine
pip install coverage

# Rate Limiting
pip install django-ratelimit

# Development
pip install django-debug-toolbar
pip install ipython
```

### Settings Template

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}
```

---

## Quick Reference Cards

### APIClient Authentication Card

```python
# Choose ONE method per test

# Method 1: Session (for session auth)
client.login(username='user', password='pass')

# Method 2: Token (for token auth)
client.credentials(HTTP_AUTHORIZATION='Token abc123')

# Method 3: Force (bypass auth)
client.force_authenticate(user=user_obj)
```

### Time Mocking Card

```python
# Use time-machine for all time mocking

import time_machine

@time_machine.travel("2025-10-23 12:00:00", tick=False)
def test_expiry(self):
    # All time sources automatically mocked
    pass
```

### Rate Limiting Test Card

```python
# Always clear cache

from django.core.cache import cache

def setUp(self):
    cache.clear()

def test_rate_limit(self):
    # Make requests
    pass

def tearDown(self):
    cache.clear()
```

---

**Document Version:** 1.0
**Last Updated:** October 23, 2025
**Purpose:** Quick reference for choosing testing tools
