# Authentication Security Research Summary

**Quick Reference Guide for Django/DRF Authentication Implementation**

**Research Date**: October 23, 2025

---

## Key Takeaways

### 1. JWT Token Configuration (Industry Standards)

```python
# settings.py
SIMPLE_JWT = {
    # Access tokens - SHORT lived
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Standard: 15-60 min

    # Refresh tokens - LONG lived
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),     # Standard: 7-30 days

    # Remember me - EXTENDED
    'REMEMBER_ME_REFRESH_TOKEN_LIFETIME': timedelta(days=30),

    # Security - REQUIRED
    'ROTATE_REFRESH_TOKENS': True,      # Issue new refresh on use
    'BLACKLIST_AFTER_ROTATION': True,   # Invalidate old refresh
}
```

**Cookie Configuration**:
- HttpOnly: ✅ REQUIRED (prevent JavaScript access)
- Secure: ✅ REQUIRED (HTTPS only)
- SameSite: `Strict` (CSRF protection)

---

### 2. NIST Password Guidelines (2024 Update)

**MAJOR CHANGES FROM OLD STANDARDS**:

| Old Standard | NIST 2024 | Rationale |
|-------------|-----------|-----------|
| 8 char minimum | **15 char recommended** | Length > Complexity |
| Required: Upper/Lower/Number/Symbol | **NO composition rules** | Predictable patterns worse |
| Expire every 90 days | **NO forced expiration** | Encourages weak passwords |
| No spaces allowed | **Spaces encouraged (passphrases)** | Easier to remember |
| Block dictionary words | **Check breach databases instead** | Real threat data |
| Security questions | **PROHIBITED** | Easily obtainable info |

**Required Implementations**:
```python
# 1. Minimum 15 characters (no maximum < 64)
min_length = 15

# 2. Check against HaveIBeenPwned
check_breached_passwords = True

# 3. NO composition requirements
# (remove uppercase/number/symbol validators)

# 4. Support password managers
# (allow paste, autofill, long passwords)
```

---

### 3. Rate Limiting Configuration (OWASP)

**Multi-Dimensional Approach** (prevent bypass):

| Endpoint | Per IP | Per Username | Global | Window |
|----------|--------|--------------|--------|--------|
| **Login** | 5 | 5 | 1000/hour | 5 min |
| **Password Reset** | 3 | 3/email | 500/hour | 15 min |
| **Registration** | 10 | N/A | 500/hour | 1 hour |
| **Token Refresh** | 20 | 20 | N/A | 5 min |

**OWASP Guideline**: "Credential recovery/forgot password endpoints should be treated as login endpoints in terms of brute force, rate limiting, and lockout protections."

**Implementation**:
```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/5m', method='POST', block=True)
@ratelimit(key='post:username', rate='5/5m', method='POST', block=True)
def login_view(request):
    # Login logic
    pass
```

---

### 4. Account Lockout Standards

| Organization | Threshold | Lockout Duration | Reset Counter |
|-------------|-----------|------------------|---------------|
| **PCI DSS** | 6 attempts | 30 minutes | After lockout |
| **NIST** | 100 attempts | Throttling (no lockout) | N/A |
| **OWASP** | 5 attempts | 15-30 minutes | 15 minutes |
| **Recommended** | **5 attempts** | **30 minutes** | **15 minutes** |

**Hybrid Approach** (defense in depth):
1. Rate limiting (5/5min per IP + username)
2. Exponential backoff (2^n seconds after failures)
3. Account lockout after 10 extreme failures
4. CAPTCHA after 3 failed attempts (optional)

---

### 5. Error Message Security (RFC 7807/9457)

**Standard Structure**:
```json
{
  "type": "https://api.example.com/errors/authentication-failed",
  "title": "Authentication Failed",
  "status": 401,
  "detail": "The username or password is incorrect.",
  "instance": "/api/v1/auth/login",
  "timestamp": "2025-10-23T14:32:15Z"
}
```

**Content-Type**: `application/problem+json`

**Security Rules**:
- ❌ NEVER reveal if username exists
- ❌ NEVER show stack traces in production
- ❌ NEVER expose database errors
- ❌ NEVER include file paths/versions
- ✅ ALWAYS use generic auth error messages
- ✅ ALWAYS log detailed errors server-side only

**Example - Prevent Username Enumeration**:
```python
# BAD - reveals username existence
if not User.objects.filter(username=username).exists():
    return Response({'error': 'Username does not exist'}, status=404)

# GOOD - same response for both cases
if not authenticate(username=username, password=password):
    return Response({
        'detail': 'Invalid credentials.'  # Doesn't reveal which is wrong
    }, status=401)
```

---

### 6. Session Management Best Practices

#### Token Lifetime by Application Type

| Type | Access Token | Refresh Token | Inactivity Timeout | Absolute Timeout |
|------|-------------|---------------|-------------------|------------------|
| **Consumer** | 1 hour | 30 days | 5 days | 30 days |
| **High-Security** | 5 minutes | 24 hours | 30 minutes | 24 hours |
| **Mobile** | 1 hour | 180 days | None | 180 days |

#### Refresh Token Rotation (REQUIRED)

**Pattern**: Every refresh generates NEW refresh token and invalidates old one.

**Why**: Prevents replay attacks. If attacker steals old refresh token, it's already invalid.

```python
def refresh_token_view(request):
    old_refresh = RefreshToken(request.data['refresh'])
    new_refresh = old_refresh.rotate()  # Built-in SimpleJWT method

    return Response({
        'access': str(old_refresh.access_token),
        'refresh': str(new_refresh)  # New refresh token
    })
```

#### Multi-Device Session Management

**Track all active sessions**:
```python
class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    refresh_token_jti = models.CharField(max_length=255, unique=True)
    device_fingerprint = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
```

**Features**:
- View all active sessions
- Logout from specific device
- Logout from all devices
- Enforce device limit (e.g., max 5 devices)
- Detect new device logins

---

### 7. Attack Prevention Techniques

#### Timing Attack Protection

**Problem**: Response times reveal if username exists.

**Solution**: Constant-time authentication + random delay.

```python
def timing_safe_authenticate(username, password):
    try:
        user = User.objects.get(username=username)
        password_valid = check_password(password, user.password)
    except User.DoesNotExist:
        # Dummy password check to match timing
        check_password(password, 'pbkdf2_sha256$260000$dummy$placeholder')
        password_valid = False
        user = None

    # Add random delay (300-700ms)
    time.sleep(random.uniform(0.3, 0.7))

    if user and password_valid:
        return user
    return None
```

#### Username Enumeration Prevention

**Password Reset Pattern** (asynchronous):
```python
@api_view(['POST'])
def password_reset_request(request):
    email = request.data.get('email')

    # ALWAYS return success (don't reveal if email exists)
    send_password_reset_email.delay(email)  # Background task

    return Response({
        'detail': 'If that email is in our system, we sent a reset link.'
    })

# Background task
@shared_task
def send_password_reset_email(email):
    try:
        user = User.objects.get(email=email)
        # Send reset email
    except User.DoesNotExist:
        pass  # Silently do nothing
```

#### CAPTCHA Integration (After Failures)

**Pattern**: Require CAPTCHA after 3 failed attempts.

```python
def requires_captcha(identifier):
    attempts = cache.get(f'login_attempts:{identifier}', 0)
    return attempts >= 3

@api_view(['POST'])
def login_with_captcha(request):
    identifier = f"{get_client_ip(request)}:{username}"

    if requires_captcha(identifier):
        if not verify_recaptcha(request.data.get('recaptcha_token')):
            return Response({
                'error': 'CAPTCHA required',
                'captcha_required': True
            }, status=403)

    # Proceed with authentication
```

---

### 8. Testing Best Practices

#### Test with CSRF Enforcement

```python
# Enable CSRF checks for cookie authentication tests
from django.test import Client

def test_csrf_required():
    client = Client(enforce_csrf_checks=True)
    client.login(username='user', password='pass')

    response = client.post('/api/some-action/')
    assert response.status_code == 403  # CSRF check fails
```

#### Mock Redis for Rate Limiting Tests

```python
from unittest.mock import patch
from fakeredis import FakeRedis

@patch('django_redis.cache.RedisCache', FakeRedis)
def test_rate_limiting():
    for i in range(6):
        response = client.post('/api/auth/login/', {...})

    assert response.status_code == 429  # Rate limited
```

#### Test Token Blacklisting

```python
def test_logout_blacklists_refresh_token():
    # Get tokens
    refresh = RefreshToken.for_user(user)

    # Logout (blacklist)
    refresh.blacklist()

    # Try to use blacklisted token
    response = client.post('/api/auth/token/refresh/', {
        'refresh': str(refresh)
    })

    assert response.status_code == 401
    assert 'blacklisted' in response.data['detail'].lower()
```

---

## Implementation Priority

### Phase 1: Critical Security (Week 1-2)
1. Configure SimpleJWT with token rotation and blacklisting
2. Implement multi-dimensional rate limiting (IP + username)
3. Add NIST-compliant password validation (15 char min, breach check)
4. Use RFC 7807 error format with generic auth messages

### Phase 2: Attack Prevention (Week 3-4)
5. Implement timing attack protection (constant-time auth + random delay)
6. Prevent username enumeration (same responses, async password reset)
7. Add account lockout (5 attempts, 30 min lockout)
8. Implement CAPTCHA after 3 failures

### Phase 3: Session Management (Week 5-6)
9. Track multi-device sessions with UserSession model
10. Implement "logout from all devices" functionality
11. Add device limit enforcement (max 5 concurrent sessions)
12. Implement inactivity timeout

### Phase 4: Testing & Monitoring (Week 7-8)
13. Write comprehensive test suite (100+ tests)
14. Set up security monitoring (failed logins, rate limits, lockouts)
15. Create alerting for suspicious activity
16. Perform security audit and penetration testing

---

## Quick Reference: Common Mistakes to Avoid

### Authentication
- ❌ Storing tokens in localStorage (use HttpOnly cookies)
- ❌ Not rotating refresh tokens (enables replay attacks)
- ❌ Long-lived access tokens (>1 hour is risky)
- ❌ Missing CSRF protection for cookie auth
- ❌ Not blacklisting tokens on logout

### Rate Limiting
- ❌ Only rate limiting by IP (easily bypassed with proxies)
- ❌ Only rate limiting by username (allows distributed attacks)
- ❌ Same rate limits for all endpoints (login should be stricter)
- ❌ No rate limiting on password reset (enables enumeration)

### Password Security
- ❌ Forcing password complexity rules (NIST prohibits)
- ❌ Mandatory password expiration (NIST prohibits)
- ❌ Not checking against breach databases
- ❌ Blocking paste in password fields (blocks password managers)
- ❌ Short minimum length (<15 characters)

### Error Messages
- ❌ "User 'john@example.com' not found" (enumeration)
- ❌ Showing stack traces in production
- ❌ Different messages for "user not found" vs "wrong password"
- ❌ Exposing database errors to clients

### Session Management
- ❌ Not invalidating sessions on password change
- ❌ No way to view/revoke active sessions
- ❌ Missing inactivity timeout
- ❌ Not detecting logins from new devices

---

## Tools & Libraries

### Required
- **djangorestframework-simplejwt**: JWT authentication with blacklisting
- **django-ratelimit**: Rate limiting with Redis backend
- **django-redis**: Redis cache backend
- **requests**: HTTP client for HaveIBeenPwned API

### Recommended
- **django-ipware**: Robust IP address extraction
- **django-zxcvbn-password-validator**: Password strength estimation
- **fakeredis**: Mock Redis for testing
- **pytest-django**: Django testing utilities

### Optional
- **django-recaptcha**: reCAPTCHA integration
- **celery**: Background tasks (async password reset emails)
- **sentry-sdk**: Error tracking and monitoring

---

## Monitoring Metrics

**Track these metrics for security monitoring**:

1. **Authentication Metrics**:
   - Login success rate (target: >95%)
   - Failed login attempts (alert if >300% spike)
   - Average login duration (baseline: 300-700ms)

2. **Rate Limiting**:
   - Rate limit hits per endpoint (alert if >100/hour from single IP)
   - Top rate-limited IPs
   - Rate limit bypass attempts

3. **Account Security**:
   - Account lockouts (track frequency)
   - Password reset requests (alert if >50/hour)
   - New device detections
   - Concurrent sessions per user

4. **Token Management**:
   - Token refresh success rate
   - Blacklisted token usage attempts
   - Token expiration errors

---

## Resources

### Official Documentation
- **SimpleJWT**: https://django-rest-framework-simplejwt.readthedocs.io/
- **NIST SP 800-63B**: https://pages.nist.gov/800-63-4/sp800-63b.html
- **RFC 9457 (Problem Details)**: https://www.rfc-editor.org/rfc/rfc9457.html

### Security Standards
- **OWASP Authentication**: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- **OWASP API Security**: https://owasp.org/API-Security/
- **HaveIBeenPwned API**: https://haveibeenpwned.com/API/v3

### Full Documentation
See `/backend/docs/development/AUTHENTICATION_TESTING_SECURITY_BEST_PRACTICES.md` for:
- Complete code examples
- Test patterns
- Security attack scenarios
- Multi-device session management
- Exponential backoff implementation
- Device fingerprinting
- And much more...

---

**Last Updated**: October 23, 2025
**Next Review**: January 2026
