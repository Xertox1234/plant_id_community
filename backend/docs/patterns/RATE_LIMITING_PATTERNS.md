# Rate Limiting Patterns

**Date:** November 3, 2025
**Library:** `django-ratelimit` 4.1.0
**Applies To:** Django REST Framework ViewSets and Actions

---

## Overview

Rate limiting prevents abuse by restricting the number of requests a user can make within a time window. This document codifies the patterns used for implementing rate limiting in the Plant Community Backend.

---

## Why Rate Limiting?

### Security Benefits

1. **DOS Attack Prevention**: Prevents resource exhaustion from excessive requests
2. **Brute Force Protection**: Slows down automated attack attempts
3. **Cost Control**: Limits expensive operations (file uploads, external API calls)
4. **Fair Usage**: Prevents single users from monopolizing resources

### Common Attack Scenarios

**File Upload Spam:**
```python
# Without rate limiting:
while True:
    upload_large_file()  # Fills disk, exhausts bandwidth, crashes server

# With rate limiting (10/hour):
upload_large_file()  # ✅ Success
...
upload_large_file()  # ✅ 10th upload succeeds
upload_large_file()  # ❌ 403 Forbidden (rate limited)
```

**API Abuse:**
```python
# Without rate limiting:
for i in range(10000):
    expensive_search_query()  # Exhausts database connections

# With rate limiting (100/hour):
# First 100 succeed, rest blocked until next hour
```

---

## Implementation Pattern

### 1. DRF ViewSet Action (Recommended)

**Location**: `apps/forum/viewsets/post_viewset.py:242,360`

**Pattern:**
```python
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

class PostViewSet(viewsets.ModelViewSet):

    @action(detail=True, methods=['POST'], permission_classes=[IsAuthorOrModerator])
    @method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True))
    def upload_image(self, request: Request, pk=None) -> Response:
        """
        Upload an image attachment to a post.

        Rate Limit: 10 uploads per hour per user
        """
        # ... implementation
```

### 2. Key Components Explained

**`@method_decorator`**
- Required for DRF class-based views
- Wraps function-based decorator for use on methods
- **Must be applied AFTER `@action` decorator** (order matters!)

**`ratelimit()` Parameters:**
```python
ratelimit(
    key='user',       # Rate limit key (see Key Strategies below)
    rate='10/h',      # Limit: 10 requests per hour
    method='POST',    # HTTP method to rate limit (None = all methods)
    block=True        # True = return 403, False = set request.limited but allow
)
```

### 3. Decorator Order (CRITICAL)

```python
# ✅ CORRECT - rate limit is innermost decorator
@action(detail=True, methods=['POST'])
@method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True))
def upload_image(self, request, pk=None):
    pass

# ❌ WRONG - rate limit won't work correctly
@method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True))
@action(detail=True, methods=['POST'])
def upload_image(self, request, pk=None):
    pass
```

**Why Order Matters:**
- DRF's `@action` must be outermost to register the action
- `@method_decorator(ratelimit())` must be innermost to intercept the request first
- Wrong order = rate limiting bypassed or not applied

---

## Rate Limit Key Strategies

### User-Based Limiting (Most Common)

```python
ratelimit(key='user', rate='10/h')
```

**When to Use:**
- Authenticated endpoints
- Per-user quotas
- File uploads, expensive operations

**How It Works:**
- Uses `request.user.pk` as key
- Anonymous users get different key (IP-based fallback)

### IP-Based Limiting

```python
ratelimit(key='ip', rate='100/h')
```

**When to Use:**
- Anonymous endpoints
- Public APIs
- Login attempts (before authentication)

**How It Works:**
- Uses client IP address as key
- Beware of proxies/NAT (multiple users same IP)

### Header-Based Limiting

```python
ratelimit(key='header:x-api-key', rate='1000/h')
```

**When to Use:**
- API key authentication
- Partner integrations
- Different quotas per API key

### Custom Key Function

```python
def custom_key(group, request):
    """Custom rate limit key based on user tier."""
    if request.user.is_premium:
        return f'premium:{request.user.pk}'
    return f'free:{request.user.pk}'

ratelimit(key=custom_key, rate='10/h')
```

---

## Rate Format Examples

```python
# Per-second rates
rate='5/s'      # 5 requests per second
rate='10/10s'   # 10 requests per 10 seconds

# Per-minute rates
rate='20/m'     # 20 requests per minute
rate='100/5m'   # 100 requests per 5 minutes

# Per-hour rates (most common for expensive operations)
rate='10/h'     # 10 requests per hour
rate='1000/h'   # 1000 requests per hour

# Per-day rates
rate='50/d'     # 50 requests per day
```

---

## Testing Rate Limits

### Test Pattern (Required for All Rate-Limited Endpoints)

**Location**: `apps/forum/tests/test_post_viewset.py:341-475`

```python
def test_upload_image_rate_limiting(self):
    """Verify rate limiting on image upload endpoint (10/hour)."""
    from django.core.cache import cache

    # CRITICAL: Clear rate limit cache before test
    cache.clear()

    # Authenticate as test user
    self.client.force_authenticate(user=self.author)

    # Make N successful requests (where N = rate limit)
    for i in range(10):
        response = self.client.post(
            f'/api/v1/forum/posts/{self.post.id}/upload_image/',
            {'image': create_test_image()},
            format='multipart'
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Upload {i+1} should succeed"
        )

    # N+1 request should be rate limited (403 Forbidden)
    response = self.client.post(
        f'/api/v1/forum/posts/{self.post.id}/upload_image/',
        {'image': create_test_image()},
        format='multipart'
    )
    self.assertEqual(
        response.status_code,
        status.HTTP_403_FORBIDDEN,
        "11th upload should be rate limited (django-ratelimit returns 403)"
    )
```

### Key Testing Considerations

1. **Cache Clearing**: Always `cache.clear()` at start to prevent test pollution
2. **Expected Status**: `django-ratelimit` returns `403 Forbidden` (not 429)
3. **Per-User Limits**: Test with authenticated user to ensure user-based keys work
4. **Test Isolation**: Each test should use separate resources (posts, threads, etc.)

---

## Common Pitfalls & Solutions

### Pitfall 1: Rate Limit Not Applied

**Symptom**: Tests pass with unlimited requests

**Causes:**
1. Wrong decorator order
2. Missing `@method_decorator`
3. `block=False` (rate limit recorded but not enforced)

**Solution:**
```python
# ✅ CORRECT
@action(detail=True, methods=['POST'])
@method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True))
def my_action(self, request, pk=None):
    pass
```

### Pitfall 2: Cache Not Configured

**Symptom**: Rate limiting doesn't persist between requests

**Cause**: Redis not configured, using in-memory cache (process-specific)

**Solution:**
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
    }
}
```

### Pitfall 3: Anonymous Users Not Rate Limited

**Symptom**: Anonymous requests bypass rate limiting

**Cause**: Using `key='user'` for unauthenticated endpoints

**Solution:**
```python
# Use 'ip' key for anonymous endpoints
@ratelimit(key='ip', rate='100/h')
def public_endpoint(request):
    pass
```

### Pitfall 4: Tests Fail Intermittently

**Symptom**: Rate limit tests pass/fail randomly

**Cause**: Cache not cleared between tests, previous test's rate limits persist

**Solution:**
```python
def test_rate_limiting(self):
    from django.core.cache import cache
    cache.clear()  # ALWAYS clear cache at test start
    # ... test logic
```

---

## Production Configuration

### Redis Requirement

Rate limiting **requires Redis** for production:

```bash
# .env
REDIS_URL=redis://localhost:6379/1

# Docker Compose
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

**Why Redis?**
- Shared state across multiple app servers
- Fast key-value lookups (<1ms)
- Automatic expiration (no manual cleanup)
- Atomic increment operations

### Rate Limit Monitoring

**CloudWatch/DataDog Metrics:**
```python
# In custom middleware
if getattr(request, 'limited', False):
    metrics.increment('rate_limit.blocked', tags=['endpoint:upload_image'])
```

**Log Analysis:**
```bash
# Find rate-limited requests
grep "Ratelimited" /var/log/app.log

# Count by endpoint
grep "Ratelimited" /var/log/app.log | awk '{print $8}' | sort | uniq -c
```

---

## Recommended Rate Limits by Operation Type

| Operation Type | Recommended Rate | Reasoning |
|---|---|---|
| File Upload | 10/hour | Expensive (disk, bandwidth) |
| File Delete | 20/hour | Less expensive than upload, allows cleanup |
| Search Query | 100/hour | Database-intensive |
| Login Attempt | 5/minute | Brute force protection |
| Password Reset | 3/hour | Email costs, abuse prevention |
| API Read | 1000/hour | Cheap operations, generous limit |
| API Write | 100/hour | Database writes, moderate cost |
| External API Call | 50/hour | Third-party rate limits |

---

## Implementation Checklist

When adding rate limiting to an endpoint:

- [ ] Identify operation type and set appropriate rate
- [ ] Choose correct key strategy (`user`, `ip`, custom)
- [ ] Apply `@method_decorator(ratelimit(...))` AFTER `@action`
- [ ] Set `block=True` to enforce rate limiting
- [ ] Add comprehensive test (N successful + N+1 blocked)
- [ ] Clear cache in test setup (`cache.clear()`)
- [ ] Document rate limit in docstring
- [ ] Add logging/metrics for rate limit violations
- [ ] Ensure Redis configured in production

---

## Real-World Examples from Codebase

### Image Upload (apps/forum/viewsets/post_viewset.py:242)

```python
@action(detail=True, methods=['POST'], permission_classes=[IsAuthorOrModerator])
@method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True))
def upload_image(self, request: Request, pk=None) -> Response:
    """
    Upload an image attachment to a post.

    Rate Limit: 10 uploads per hour per user

    Why: Prevents DOS via disk/bandwidth exhaustion
    """
    # ... implementation
```

**Rationale:**
- File uploads are expensive (disk I/O, bandwidth)
- 10/hour = reasonable user behavior (not automated abuse)
- User-based key = per-user quota, fair distribution

### Image Delete (apps/forum/viewsets/post_viewset.py:360)

```python
@action(detail=True, methods=['DELETE'], permission_classes=[IsAuthorOrModerator],
        url_path='delete_image/(?P<attachment_id>[^/.]+)')
@method_decorator(ratelimit(key='user', rate='20/h', method='DELETE', block=True))
def delete_image(self, request: Request, pk=None, attachment_id=None) -> Response:
    """
    Delete an image attachment from a post.

    Rate Limit: 20 deletes per hour per user

    Why: Less expensive than upload, allows cleanup after upload spree
    """
    # ... implementation
```

**Rationale:**
- Delete is cheaper than upload (no file transfer)
- 20/hour (2x upload limit) allows users to clean up mistakes
- Still prevents automated abuse

---

## Migration Strategy for Existing Endpoints

### Phase 1: Audit Expensive Endpoints

```bash
# Find all POST/PUT/PATCH/DELETE actions without rate limiting
grep -r "@action.*POST" apps/*/viewsets/*.py | grep -v "@method_decorator(ratelimit"
```

### Phase 2: Add Rate Limiting Gradually

**Week 1**: Critical operations (file uploads, external APIs)
**Week 2**: Write operations (POST, PUT, PATCH, DELETE)
**Week 3**: Expensive reads (search, analytics)

### Phase 3: Monitor and Adjust

```python
# Start conservative, adjust based on metrics
rate='5/h'   # Week 1 (too strict?)
rate='10/h'  # Week 2 (adjusted after monitoring)
rate='20/h'  # Week 3 (final value based on 99th percentile usage)
```

---

## Security Considerations

### Rate Limit Bypass Attempts

**IP Rotation:**
- Attacker uses multiple IPs to bypass `key='ip'`
- **Mitigation**: Use `key='user'` for authenticated endpoints

**Account Creation:**
- Attacker creates multiple accounts to bypass `key='user'`
- **Mitigation**: Rate limit account creation endpoint (5/hour per IP)

**Header Spoofing:**
- Attacker spoofs `X-Forwarded-For` header
- **Mitigation**: Trust only your load balancer's IP, validate headers

### Denial of Service via Rate Limiting

**Attack**: Attacker triggers rate limits for legitimate users
- Example: Trigger rate limit on user's behalf (if key leaks)
- **Mitigation**: Use unpredictable keys, log anomalies

---

## References

- **django-ratelimit Documentation**: https://django-ratelimit.readthedocs.io/
- **OWASP Rate Limiting**: https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html
- **Redis Best Practices**: https://redis.io/docs/management/optimization/
- **DRF Method Decorators**: https://www.django-rest-framework.org/api-guide/viewsets/#marking-extra-actions-for-routing

---

**Document Version:** 1.0
**Last Updated:** November 3, 2025
**Maintainer:** Backend Team
