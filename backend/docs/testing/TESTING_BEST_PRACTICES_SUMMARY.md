# Testing Best Practices Summary

**Quick Reference Guide for Django REST Framework Authentication Testing**

**Date:** October 23, 2025
**For:** Plant ID Community Backend Development

---

## Quick Decision Guide

### Which Test Client Should I Use?

```
Testing REST API endpoints? → APIClient
Testing Django template views? → TestClient
Testing view logic directly? → APIRequestFactory
Need exact production CSRF? → TestClient
Want simplified auth setup? → APIClient
```

### Which Time Mocking Library?

```
Simple datetime mocking? → time-machine (100-200x faster)
Need PyPy support? → freezegun
Testing Django timezone-aware code? → time-machine
Legacy project with freezegun? → Consider migrating to time-machine
```

### Which Test Framework?

```
Existing Django project? → Keep using TestCase
New project starting from scratch? → pytest-django
Need parametrized tests? → pytest-django
Want fixtures reuse? → pytest-django
Working with existing Django tests? → TestCase (easier migration)
```

---

## Essential Patterns

### 1. APIClient Authentication (3 Methods)

```python
from rest_framework.test import APIClient

client = APIClient()

# Method 1: Session authentication
client.login(username='user', password='pass')

# Method 2: Token authentication
client.credentials(HTTP_AUTHORIZATION='Token abc123')

# Method 3: Force authentication (bypass)
client.force_authenticate(user=user_obj)
```

### 2. CSRF Testing

```python
# Production-like CSRF enforcement
client = APIClient(enforce_csrf_checks=True)
client.login(username='user', password='pass')

# Must include CSRF token
response = client.post('/api/endpoint/', data, HTTP_X_CSRFTOKEN=token)
```

### 3. Time-Based Testing

```python
import time_machine

@time_machine.travel("2025-10-23 12:00:00", tick=False)
def test_token_expiry(self):
    # Test at fixed time
    token = create_token()

    # Jump forward 1 hour
    with time_machine.travel("2025-10-23 13:00:00", tick=False):
        # Token expired
        assert_expired(token)
```

### 4. Rate Limiting Tests

```python
from django.core.cache import cache

def test_rate_limit(self):
    cache.clear()  # CRITICAL: Clear before test

    # Make requests up to limit
    for i in range(5):
        response = client.post('/api/endpoint/', {})

    # Next request rate limited
    response = client.post('/api/endpoint/', {})
    assert response.status_code == 429
    assert 'Retry-After' in response
```

### 5. API Versioning Tests

```python
from django.urls import reverse

def test_v1_vs_v2(self):
    # Test v1 endpoint
    url_v1 = reverse('v1:plant-identification-identify')
    response_v1 = client.post(url_v1, data)
    assert 'plant_name' in response_v1.data

    # Test v2 endpoint (breaking change)
    url_v2 = reverse('v2:plant-identification-identify')
    response_v2 = client.post(url_v2, data)
    assert 'plant_name' not in response_v2.data
    assert 'scientific_name' in response_v2.data
```

---

## Critical "Always Do This" Checklist

### Before Every Test Method

```python
def setUp(self):
    """Always include these."""
    from django.core.cache import cache

    # 1. Clear cache (rate limits, lockouts)
    cache.clear()

    # 2. Create fresh APIClient
    self.client = APIClient()

    # 3. Create test user
    self.user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='TestPassword123!'
    )
```

### After Every Test Method

```python
def tearDown(self):
    """Always clean up."""
    from django.core.cache import cache

    # Clear cache to prevent pollution
    cache.clear()
```

### For Time-Based Tests

```python
# Always use timezone-aware datetime
from django.utils import timezone

now = timezone.now()  # Good
now = datetime.now()  # Bad (timezone naive)
```

### For Rate Limit Tests

```python
# Always clear cache
from django.core.cache import cache

cache.clear()  # Before test
# Run test
cache.clear()  # After test
```

---

## Common Pitfalls (and Solutions)

### Pitfall 1: "Tests pass, production fails with 403 CSRF"

**Problem:**
```python
client = APIClient()  # CSRF disabled by default
response = client.post('/api/endpoint/', {})
assert response.status_code == 200  # Passes
```

**Solution:**
```python
client = APIClient(enforce_csrf_checks=True)
response = client.post('/api/endpoint/', {}, HTTP_X_CSRFTOKEN=token)
assert response.status_code == 200  # Production-like
```

### Pitfall 2: "Rate limit tests interfere with each other"

**Problem:**
```python
def test_rate_limit_1(self):
    # Makes 5 requests
    pass

def test_rate_limit_2(self):
    # Fails - previous test used 5 requests
    pass
```

**Solution:**
```python
def setUp(self):
    cache.clear()

def tearDown(self):
    cache.clear()
```

### Pitfall 3: "Time-based tests fail in production"

**Problem:**
```python
from datetime import datetime
now = datetime.now()  # No timezone
```

**Solution:**
```python
from django.utils import timezone
now = timezone.now()  # Timezone-aware
```

### Pitfall 4: "Wrong authorization header type"

**Problem:**
```python
# DRF Token Auth
client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)  # Wrong
```

**Solution:**
```python
# DRF Token Auth
client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

# JWT Auth
client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)
```

### Pitfall 5: "force_authenticate doesn't persist"

**Problem:**
```python
factory = APIRequestFactory()
request1 = factory.get('/api/endpoint1/')
force_authenticate(request1, user=user)  # Only affects request1

request2 = factory.get('/api/endpoint2/')  # NOT authenticated
```

**Solution:**
```python
client = APIClient()
client.force_authenticate(user=user)  # Persists across requests

response1 = client.get('/api/endpoint1/')  # Authenticated
response2 = client.get('/api/endpoint2/')  # Authenticated
```

---

## Test Organization Best Practices

### File Structure

```
apps/users/tests/
├── __init__.py
├── test_cookie_jwt_authentication.py  # Auth flow tests
├── test_token_refresh.py              # Token lifecycle
├── test_rate_limiting.py              # Rate limiting
├── test_ip_spoofing_protection.py     # IP handling
└── test_account_lockout.py            # Lockout mechanism
```

### Test Class Organization

```python
class LoginTests(TestCase):
    """Test login endpoint."""

    def setUp(self):
        """Common setup."""
        pass

    def test_login_success(self):
        """Test successful login."""
        pass

    def test_login_invalid_password(self):
        """Test invalid password."""
        pass

    def test_login_missing_username(self):
        """Test missing username."""
        pass
```

### Test Naming Convention

```python
# Good - Descriptive
def test_login_with_invalid_password_returns_401(self):
    pass

def test_account_locked_after_10_failed_attempts(self):
    pass

# Bad - Vague
def test_login_error(self):
    pass

def test_lockout(self):
    pass
```

---

## pytest-django Quick Start

### conftest.py

```python
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='TestPassword123!'
    )

@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client

@pytest.fixture(autouse=True)
def clear_cache():
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
```

### Using Fixtures

```python
import pytest
from rest_framework import status

@pytest.mark.django_db
def test_login(api_client, user):
    response = api_client.post('/api/v1/auth/login/', {
        'username': 'testuser',
        'password': 'TestPassword123!'
    })
    assert response.status_code == status.HTTP_200_OK
```

### Parametrized Tests

```python
@pytest.mark.django_db
@pytest.mark.parametrize('password,expected_status', [
    ('short', 400),
    ('NoNumbers!', 400),
    ('ValidPass123!', 201),
])
def test_password_validation(api_client, password, expected_status):
    response = api_client.post('/api/v1/auth/register/', {
        'username': 'newuser',
        'email': 'new@example.com',
        'password': password,
    })
    assert response.status_code == expected_status
```

---

## Testing Checklist

### For Every New Endpoint

- [ ] Test successful case (200/201)
- [ ] Test authentication required (401)
- [ ] Test permission denied (403)
- [ ] Test not found (404)
- [ ] Test invalid data (400)
- [ ] Test rate limiting (429)
- [ ] Test CSRF protection (403)

### For Authentication Endpoints

- [ ] Test successful login
- [ ] Test invalid credentials
- [ ] Test missing fields
- [ ] Test account lockout
- [ ] Test rate limiting
- [ ] Test email notification
- [ ] Test token expiry
- [ ] Test token refresh
- [ ] Test token blacklist

### For Time-Based Features

- [ ] Use time-machine for mocking
- [ ] Test expiry/timeout logic
- [ ] Use timezone-aware datetime
- [ ] Test before/at/after expiry

### For Rate Limiting

- [ ] Clear cache in setUp/tearDown
- [ ] Test up to limit (success)
- [ ] Test exceeding limit (429)
- [ ] Test Retry-After header
- [ ] Test window reset

---

## Performance Tips

### Parallel Testing

```bash
# Run tests in parallel (4 processes)
python manage.py test apps.users.tests --parallel=4

# 12 seconds → 4 seconds
```

### Keep Test Database

```bash
# Reuse test database between runs
python manage.py test apps.users.tests --keepdb

# 12 seconds → 6 seconds (subsequent runs)
```

### Use setUpTestData for Shared Fixtures

```python
class MyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Create once for all tests in class."""
        cls.user = User.objects.create_user(...)

    def setUp(self):
        """Create before each test."""
        self.client = APIClient()
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run tests
        run: |
          python manage.py test apps.users.tests --parallel=4

      - name: Coverage
        run: |
          coverage run --source='apps' manage.py test apps.users.tests
          coverage report --fail-under=95
```

---

## Additional Resources

### Official Documentation

- [Django REST Framework Testing](https://www.django-rest-framework.org/api-guide/testing/)
- [time-machine Documentation](https://time-machine.readthedocs.io/)
- [pytest-django Documentation](https://pytest-django.readthedocs.io/)

### Project Documentation

- `DRF_AUTHENTICATION_TESTING_BEST_PRACTICES.md` - Comprehensive guide (this summary's source)
- `AUTHENTICATION_TESTS.md` - Current test suite documentation
- `AUTHENTICATION_SECURITY.md` - Security implementation details

---

**Document Version:** 1.0
**Last Updated:** October 23, 2025
**Quick Reference:** Keep this open while writing tests
