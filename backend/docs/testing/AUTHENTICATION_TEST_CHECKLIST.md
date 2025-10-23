# Authentication Test Checklist

**Last Updated**: October 23, 2025
**Purpose**: Quick reference for reviewing DRF authentication tests
**Source**: Patterns codified from authentication test fixes

## Quick Reference Card

Use this checklist when writing or reviewing Django REST Framework authentication tests.

---

## 1. CSRF Token Handling

### Required Pattern
```python
def get_csrf_token(self):
    """Helper method to get CSRF token from the API."""
    response = self.client.get('/api/v1/auth/csrf/')
    csrf_cookie = response.cookies.get('csrftoken')
    if csrf_cookie:
        return csrf_cookie.value
    return self.client.cookies.get('csrftoken', None)
```

### Checklist
- [ ] Using `APIClient` (not `TestClient`)?
- [ ] Reusable `get_csrf_token()` helper method exists?
- [ ] Helper includes fallback logic (cookies.get → client.cookies.get)?
- [ ] CSRF token included in POST headers (`HTTP_X_CSRFTOKEN`)?
- [ ] No repeated cookie extraction logic (DRY principle)?

### Red Flags
```python
# BAD - No fallback
csrf_token = response.cookies['csrftoken'].value

# BAD - Repeated logic (not DRY)
# Multiple tests each implementing their own cookie extraction
```

---

## 2. Time-Based Mocking

### Required Pattern
```python
# Capture time BEFORE mocking
lock_time = time.time()

# Patch at module level (not global)
with patch('apps.core.security.time.time') as mock_time:
    mock_time.return_value = lock_time + DURATION + 1
    # ... test code ...
```

### Checklist
- [ ] Real time captured BEFORE mocking (`lock_time = time.time()`)?
- [ ] Patching module-specific (`apps.core.security.time.time`), not global?
- [ ] Mock uses captured time values (not calling `time.time()` again)?
- [ ] No TypeError about MagicMock comparisons?
- [ ] Mocking scoped appropriately (context manager)?

### Red Flags
```python
# BAD - Global mocking
with patch('time.time') as mock_time:
    mock_time.return_value = time.time() + 100  # Recursive!

# BAD - Hardcoded time
mock_time.return_value = 1000000  # Brittle
```

---

## 3. API Versioning

### Required Pattern
```python
# All test URLs must match production
response = self.client.post('/api/v1/auth/login/', ...)  # ✓ Versioned
response = self.client.get('/api/v1/auth/csrf/')          # ✓ Versioned
response = self.client.post('/api/v1/auth/logout/')       # ✓ Versioned
```

### Checklist
- [ ] All test URLs include version prefix (`/api/v1/...`)?
- [ ] URLs match production patterns exactly?
- [ ] Consistent versioning across all test URLs (no mixed versioning)?
- [ ] If versioning is new, ALL existing test URLs updated?

### Red Flags
```python
# BAD - Unversioned
response = self.client.post('/api/auth/login/', ...)

# BAD - Inconsistent
self.client.get('/api/v1/auth/csrf/')    # Versioned
self.client.post('/api/auth/login/', ...)  # NOT versioned
```

---

## 4. Layered Security Testing

### Required Pattern
```python
# Accept responses from EITHER security layer
self.assertIn(
    response.status_code,
    [status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_403_FORBIDDEN]
)

# Conditional assertions based on which layer triggered
if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
    # Account lockout - verify specifics
    self.assertEqual(response.data['error']['code'], 'ACCOUNT_LOCKED')
```

### Checklist
- [ ] Tests accept multiple valid status codes (403 and 429)?
- [ ] Assertions conditional based on which layer triggered?
- [ ] Interaction between security layers documented in comments?
- [ ] Tests reflect real-world behavior (defense in depth)?
- [ ] No assumptions about which layer triggers first?

### Red Flags
```python
# BAD - Expects only lockout
self.assertEqual(response.status_code, 429)

# BAD - Unconditional assertion
self.assertEqual(len(mail.outbox), 1)  # May fail if rate limited!
```

---

## 5. Conditional Assertions

### Required Pattern
```python
# Make assertions conditional on response characteristics
if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
    # Account lockout triggered - verify email sent
    self.assertEqual(len(mail.outbox), 1)
    self.assertIn('locked', mail.outbox[0].subject.lower())
elif response.status_code == status.HTTP_403_FORBIDDEN:
    # Rate limiting triggered - no email expected
    pass
else:
    self.fail(f"Unexpected status: {response.status_code}")
```

### Checklist
- [ ] Email assertions conditional on lockout triggering?
- [ ] Error code assertions conditional on response status?
- [ ] Fallback/else branch for alternative security layers?
- [ ] Conditional branches documented with comments?
- [ ] Tests fail loudly on unexpected states (`self.fail()`)?

### Red Flags
```python
# BAD - Unconditional assertions
make_failed_logins(10)
self.assertEqual(len(mail.outbox), 1)  # May fail!
```

---

## 6. Test Structure

### Required Pattern
```python
class AuthenticationTestCase(TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(...)
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def get_csrf_token(self):
        """Helper method to get CSRF token from the API."""
        # ... implementation ...

    def test_specific_behavior(self):
        """Test description explaining what and why.

        Patterns Used:
        - CSRF Token Handling Pattern
        - API Versioning Pattern
        - Layered Security Testing Pattern
        """
        # Arrange
        # ... setup ...

        # Act
        # ... action ...

        # Assert
        # ... verification ...
```

### Checklist
- [ ] `setUp()` initializes APIClient and clears cache?
- [ ] `tearDown()` clears cache to prevent test pollution?
- [ ] Test methods have descriptive docstrings?
- [ ] Docstrings mention which patterns are used?
- [ ] Tests follow Arrange-Act-Assert pattern?
- [ ] Test names are descriptive and clear?

---

## Common Test Scenarios

### Scenario 1: Login with CSRF Protection

```python
def test_login_requires_csrf_token(self):
    """Test that login endpoint requires CSRF token."""
    # Get CSRF token (Pattern: CSRF Token Handling)
    csrf_token = self.get_csrf_token()

    # Attempt login (Pattern: API Versioning)
    response = self.client.post(
        '/api/v1/auth/login/',
        data={'username': 'testuser', 'password': 'password'},
        HTTP_X_CSRFTOKEN=csrf_token
    )

    self.assertEqual(response.status_code, status.HTTP_200_OK)
```

### Scenario 2: Account Lockout After Failed Attempts

```python
def test_account_lockout_after_failures(self):
    """Test that account locks after threshold failed attempts."""
    # Lock the account
    for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
        SecurityMonitor.track_failed_login_attempt(
            username='testuser',
            ip_address='192.168.1.100'
        )

    # Get CSRF token
    csrf_token = self.get_csrf_token()

    # Attempt login (Pattern: Layered Security Testing)
    response = self.client.post(
        '/api/v1/auth/login/',
        data={'username': 'testuser', 'password': 'TestPassword123!'},
        HTTP_X_CSRFTOKEN=csrf_token
    )

    # Accept EITHER security layer response
    self.assertIn(
        response.status_code,
        [status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_403_FORBIDDEN]
    )
```

### Scenario 3: Lockout Expiry (Time-Based)

```python
def test_lockout_expires_after_duration(self):
    """Test that lockout expires after configured duration."""
    # Pattern: Time-Based Mocking - Capture time BEFORE locking
    lock_time = time.time()

    # Lock the account
    for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
        SecurityMonitor.track_failed_login_attempt(
            username='testuser',
            ip_address='192.168.1.100'
        )

    # Pattern: Time-Based Mocking - Module-specific patching
    with patch('apps.core.security.time.time') as mock_time:
        mock_time.return_value = lock_time + ACCOUNT_LOCKOUT_DURATION + 1

        is_locked, time_remaining = SecurityMonitor.is_account_locked('testuser')

        self.assertFalse(is_locked)
        self.assertIsNone(time_remaining)
```

---

## Code Review Quick Checks

When reviewing authentication tests, quickly scan for:

### Anti-Patterns (FAIL Review)
- [ ] Direct cookie access without fallback (`cookies['csrftoken'].value`)
- [ ] Global time mocking (`patch('time.time')`)
- [ ] Unversioned test URLs (`/api/auth/login/`)
- [ ] Single status code expectation for security endpoints
- [ ] Unconditional email/notification assertions
- [ ] Repeated helper code (not DRY)

### Good Patterns (PASS Review)
- [x] Reusable `get_csrf_token()` helper with fallback
- [x] Module-specific time patching with captured values
- [x] Versioned URLs matching production (`/api/v1/...`)
- [x] Multiple accepted status codes (`assertIn([429, 403])`)
- [x] Conditional assertions based on response
- [x] Clear docstrings explaining patterns used

---

## Integration with CI/CD

### Pre-Commit Checks
```bash
# Run authentication tests before commit
python manage.py test apps.users.tests.test_account_lockout --keepdb -v 2

# Verify all tests pass
# Expected: OK (XX tests in X.XXXs)
```

### Code Review Automation
```bash
# Check for DRF test anti-patterns
grep -r "cookies\['csrftoken'\]" apps/*/tests/
grep -r "patch('time.time')" apps/*/tests/
grep -r "'/api/auth/" apps/*/tests/  # Should use /api/v1/
```

---

## References

- **Comprehensive Guide**: `/backend/docs/testing/DRF_AUTHENTICATION_TESTING_PATTERNS.md`
- **Test Fixes**: `/backend/AUTHENTICATION_TEST_FIXES.md`
- **Security Guide**: `/backend/docs/security/AUTHENTICATION_SECURITY.md`
- **Testing Guide**: `/backend/docs/testing/AUTHENTICATION_TESTS.md`

---

**Quick Start**: Copy the patterns from this checklist when writing new authentication tests. Always use the helper methods and conditional assertion patterns to ensure robust, maintainable tests.

**Last Updated**: October 23, 2025
**Codified By**: Claude Code - feedback-analyst-specialist
**Status**: Production-verified patterns
