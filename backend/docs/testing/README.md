# Testing Documentation

**Comprehensive Testing Guide for Plant ID Community Backend**

**Last Updated:** October 23, 2025
**Status:** Complete
**Coverage:** 96%+ for security modules

---

## Quick Navigation

### Start Here

**New to Django testing?**
→ Start with [Testing Best Practices Summary](./TESTING_BEST_PRACTICES_SUMMARY.md)

**Need to choose testing tools?**
→ See [Testing Tools Comparison](./TESTING_TOOLS_COMPARISON.md)

**Writing DRF authentication tests?**
→ Read [DRF Authentication Testing Best Practices](./DRF_AUTHENTICATION_TESTING_BEST_PRACTICES.md)

**Understanding existing tests?**
→ Check [Authentication Tests Guide](./AUTHENTICATION_TESTS.md)

---

## Documentation Overview

### 1. Testing Best Practices Summary
**File:** `TESTING_BEST_PRACTICES_SUMMARY.md`
**Size:** 8KB
**Purpose:** Quick reference guide

**Contains:**
- Quick decision trees (which client? which library?)
- Essential patterns (authentication, time mocking, rate limiting)
- Critical "always do this" checklist
- Common pitfalls and solutions
- Test organization best practices
- pytest-django quick start

**Use this when:**
- Starting a new test file
- Stuck on a testing decision
- Need a quick pattern reference
- Writing tests for the first time

---

### 2. DRF Authentication Testing Best Practices
**File:** `DRF_AUTHENTICATION_TESTING_BEST_PRACTICES.md`
**Size:** 72KB (comprehensive)
**Purpose:** Authoritative reference based on official docs

**Contains:**
- APIClient vs TestClient (detailed comparison)
- Testing layered security (defense-in-depth)
- Time-based testing (time-machine vs freezegun)
- API versioning in tests
- DRF authentication patterns (JWT, CSRF, lockout, rate limiting)
- pytest-django integration
- Common pitfalls with solutions
- Real-world examples

**Use this when:**
- Need deep understanding of a topic
- Implementing complex authentication
- Troubleshooting failing tests
- Learning best practices
- Need official source citations

---

### 3. Testing Tools Comparison
**File:** `TESTING_TOOLS_COMPARISON.md`
**Size:** 18KB
**Purpose:** Side-by-side tool comparisons

**Contains:**
- APIClient vs TestClient vs APIRequestFactory
- time-machine vs freezegun vs unittest.mock
- Django TestCase vs pytest-django
- DRF Token vs JWT vs Session
- Rate limiting strategies
- API versioning strategies
- Recommended stack for 2025
- Quick reference cards

**Use this when:**
- Choosing between testing tools
- Evaluating alternatives
- Need performance comparisons
- Making architecture decisions
- Onboarding new developers

---

### 4. Authentication Tests Guide
**File:** `AUTHENTICATION_TESTS.md`
**Size:** 22KB
**Purpose:** Document existing test suite

**Contains:**
- Test suite summary (63+ tests, 1,810 lines)
- Test file descriptions
- Running tests (commands, flags)
- Test coverage report (96%)
- Test patterns used in project
- Writing new tests (templates)
- Troubleshooting guide

**Use this when:**
- Running existing tests
- Understanding test coverage
- Debugging test failures
- Contributing new tests
- Reviewing test suite status

---

## Quick Reference

### Essential Commands

```bash
# Run all authentication tests
python manage.py test apps.users.tests -v 2

# Run specific test file
python manage.py test apps.users.tests.test_rate_limiting -v 2

# Run with coverage
coverage run --source='apps' manage.py test apps.users.tests
coverage report

# Parallel tests (faster)
python manage.py test apps.users.tests --parallel=4

# Keep database (faster subsequent runs)
python manage.py test apps.users.tests --keepdb
```

### Essential Patterns

```python
# 1. APIClient authentication
from rest_framework.test import APIClient

client = APIClient()
client.force_authenticate(user=user)

# 2. Time mocking
import time_machine

@time_machine.travel("2025-10-23 12:00:00", tick=False)
def test_expiry(self):
    pass

# 3. Rate limiting
from django.core.cache import cache

cache.clear()  # Before test
# Make requests
cache.clear()  # After test

# 4. API versioning
from django.urls import reverse

url = reverse('v1:endpoint-name')
```

---

## Testing Standards

### File Organization

```
apps/users/tests/
├── __init__.py
├── test_cookie_jwt_authentication.py  # 338 lines, 14 tests
├── test_token_refresh.py              # 364 lines, 11 tests
├── test_rate_limiting.py              # 382 lines, 15 tests
├── test_ip_spoofing_protection.py     # 277 lines, 11 tests
└── test_account_lockout.py            # 449 lines, 12 tests
```

### Naming Conventions

```python
# Test files
test_<feature>.py

# Test classes
class <Feature>TestCase(TestCase):

# Test methods
def test_<feature>_<scenario>_<expected_result>(self):
    """Test <what is being tested>."""
```

### Test Structure

```python
class MyTestCase(TestCase):
    """Test <feature> functionality."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(...)

    def test_success_case(self):
        """Test successful <scenario>."""
        # Arrange
        data = {...}

        # Act
        response = self.client.post('/api/endpoint/', data)

        # Assert
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        """Clean up after test."""
        cache.clear()
```

---

## Test Coverage Goals

### Current Status

| Module | Coverage | Tests | Status |
|--------|----------|-------|--------|
| `apps/core/security.py` | 98% | 35 | ✅ Excellent |
| `apps/users/api/views.py` | 96% | 20 | ✅ Excellent |
| `apps/core/middleware.py` | 94% | 8 | ✅ Good |
| **Overall** | **96%** | **63** | ✅ Excellent |

### Coverage Requirements

- **Security modules:** 95%+ (critical)
- **API views:** 90%+ (important)
- **Utilities:** 80%+ (good to have)
- **Overall project:** 85%+ (target)

### Checking Coverage

```bash
# Generate coverage report
coverage run --source='apps' manage.py test apps.users.tests
coverage report

# Generate HTML report
coverage html
open htmlcov/index.html  # macOS
```

---

## Common Testing Scenarios

### 1. Testing Authentication Flow

```python
def test_complete_auth_flow(self):
    """Test registration → login → access → logout."""
    # 1. Register
    response = self.client.post('/api/v1/auth/register/', {...})

    # 2. Login
    response = self.client.post('/api/v1/auth/login/', {...})
    access_token = response.data['access']

    # 3. Access protected endpoint
    self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    response = self.client.get('/api/v1/user/profile/')

    # 4. Logout
    response = self.client.post('/api/v1/auth/logout/', {...})
```

### 2. Testing Rate Limiting

```python
def test_rate_limit(self):
    """Test rate limit enforcement."""
    cache.clear()

    # Make requests up to limit
    for i in range(5):
        response = self.client.post('/api/endpoint/', {})

    # Exceed limit
    response = self.client.post('/api/endpoint/', {})
    self.assertEqual(response.status_code, 429)
    self.assertIn('Retry-After', response)
```

### 3. Testing Account Lockout

```python
def test_account_lockout(self):
    """Test account locks after 10 failed attempts."""
    # 10 failed attempts
    for i in range(10):
        self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'wrong'
        })

    # Account locked
    response = self.client.post('/api/v1/auth/login/', {
        'username': 'testuser',
        'password': 'TestPassword123!'  # Correct password
    })
    self.assertEqual(response.status_code, 403)
    self.assertIn('locked', response.data['detail'].lower())
```

### 4. Testing Time-Based Expiry

```python
@time_machine.travel("2025-10-23 12:00:00", tick=False)
def test_token_expiry(self):
    """Test token expires after 1 hour."""
    # Create token at 12:00
    response = self.client.post('/api/v1/auth/login/', {...})
    access_token = response.data['access']

    # Token valid at 12:00
    self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    response = self.client.get('/api/v1/protected/')
    self.assertEqual(response.status_code, 200)

    # Move to 13:01 (expired)
    with time_machine.travel("2025-10-23 13:01:00", tick=False):
        response = self.client.get('/api/v1/protected/')
        self.assertEqual(response.status_code, 401)
```

---

## Troubleshooting

### Tests Fail: Redis Connection Error

```bash
# Start Redis
brew services start redis  # macOS
sudo systemctl start redis  # Linux

# Verify
redis-cli ping  # Should return "PONG"
```

### Tests Interfere with Each Other

```python
# Add to setUp and tearDown
def setUp(self):
    cache.clear()

def tearDown(self):
    cache.clear()
```

### CSRF Errors in Tests but Not Production

```python
# Enable CSRF in tests
client = APIClient(enforce_csrf_checks=True)
```

### Time-Based Tests Fail Randomly

```python
# Use timezone-aware datetime
from django.utils import timezone

now = timezone.now()  # Good
now = datetime.now()  # Bad
```

### Coverage Lower Than Expected

```bash
# Check what's not covered
coverage report --show-missing

# Focus on critical paths first
# Aim for 95%+ on security modules
```

---

## CI/CD Integration

### GitHub Actions

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
      redis:
        image: redis:7

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python manage.py test apps.users.tests --parallel=4
      - name: Coverage
        run: |
          coverage run --source='apps' manage.py test apps.users.tests
          coverage report --fail-under=95
```

---

## Related Documentation

### Security

- `/backend/docs/security/AUTHENTICATION_SECURITY.md` - Security implementation (38KB)
- `/backend/docs/development/AUTHENTICATION_TESTING_SECURITY_BEST_PRACTICES.md` - Research notes (72KB)

### Architecture

- `/backend/docs/architecture/analysis.md` - Design patterns
- `/backend/docs/architecture/recommendations.md` - Best practices

### Development

- `/backend/docs/development/session-summaries.md` - Implementation notes
- `/backend/docs/development/github-issue-best-practices.md` - Issue templates

---

## Getting Help

### Internal Resources

1. Check this documentation first
2. Review existing tests in `apps/users/tests/`
3. Read code comments in test files

### External Resources

1. [Django REST Framework Testing Docs](https://www.django-rest-framework.org/api-guide/testing/)
2. [pytest-django Documentation](https://pytest-django.readthedocs.io/)
3. [time-machine Documentation](https://time-machine.readthedocs.io/)
4. [OWASP Django REST Framework Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Django_REST_Framework_Cheat_Sheet.html)

### Questions?

- Check the comprehensive guide: `DRF_AUTHENTICATION_TESTING_BEST_PRACTICES.md`
- Look at real examples in existing test files
- Review the tools comparison: `TESTING_TOOLS_COMPARISON.md`

---

## Document Index

| Document | Size | Purpose | When to Use |
|----------|------|---------|-------------|
| **README.md** (this file) | 8KB | Navigation | Finding the right doc |
| **TESTING_BEST_PRACTICES_SUMMARY.md** | 8KB | Quick reference | Writing tests |
| **DRF_AUTHENTICATION_TESTING_BEST_PRACTICES.md** | 72KB | Comprehensive guide | Deep understanding |
| **TESTING_TOOLS_COMPARISON.md** | 18KB | Tool comparison | Choosing tools |
| **AUTHENTICATION_TESTS.md** | 22KB | Existing tests | Running/understanding tests |

**Total Documentation:** 128KB of testing best practices

---

## Version History

### Version 1.0 (October 23, 2025)
- Initial comprehensive testing documentation
- Research from official Django/DRF sources
- Community best practices integrated
- Real-world examples from project
- Complete tool comparisons
- pytest-django integration guide

---

**Maintained by:** Backend Development Team
**Last Review:** October 23, 2025
**Next Review:** January 2026 (or when Django/DRF major version updates)
